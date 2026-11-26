# ClampPVM Architectural Comparison: Standard CPython vs. ClampPVM

This document provides a line-by-line, side-by-side architectural comparison between upstream **CPython (3.16 dev)** and **ClampPVM (Flavor #7)**.

---

## 1. Executive Summary

| Dimension | Standard CPython | ClampPVM (Flavor #7) |
|---|---|---|
| **Arithmetic Model** | Unbounded arbitrary-precision `int`, IEEE 754 `float` | Opt-in saturating / clamped arithmetic mode with dynamic bounds $[min, max]$ |
| **Overflow Handling** | Unbounded growth (memory allocation on integers) | Automatically clamped to upper/lower bound |
| **Developer Ergonomics** | Requires defensive `min(MAX, max(MIN, expr))` on every calculation | Zero code changes: standard `+`, `-`, `*`, `+=`, `-=`, `*=` clamp natively |
| **Specialization Path** | Optimizes to specialized uops (`BINARY_OP_ADD_INT`, etc.) | Safely de-optimizes to `_BINARY_OP` when clamp mode is active |
| **Constant Folding** | Statically folds literal constants at compile-time | Bypasses folding for arithmetic opcodes to honor dynamic runtime mode switches |
| **Telemetry & Observability** | None | Built-in telemetry tracking `clamped_count` via `sys.get_clamp_stats()` |

---

## 2. PVM Bytecode Evaluation Loop (`Python/bytecodes.c`)

### 2.1 The Binary Operation Evaluator (`_BINARY_OP`)

#### 🔴 Original Upstream CPython
```c
op(_BINARY_OP, (lhs, rhs -- res, l, r)) {
    PyObject *lhs_o = PyStackRef_AsPyObjectBorrow(lhs);
    PyObject *rhs_o = PyStackRef_AsPyObjectBorrow(rhs);

    assert(_PyEval_BinaryOps[oparg]);
    PyObject *res_o = _PyEval_BinaryOps[oparg](lhs_o, rhs_o);
    if (res_o == NULL) {
        ERROR_NO_POP();
    }
    res = PyStackRef_FromPyObjectSteal(res_o);
    l = lhs;
    r = rhs;
    DEAD(lhs);
    DEAD(rhs);
}
```

#### 🟢 ClampPVM Modified Version
```c
op(_BINARY_OP, (lhs, rhs -- res, l, r)) {
    PyObject *lhs_o = PyStackRef_AsPyObjectBorrow(lhs);
    PyObject *rhs_o = PyStackRef_AsPyObjectBorrow(rhs);

    assert(_PyEval_BinaryOps[oparg]);
    PyObject *res_o = _PyEval_BinaryOps[oparg](lhs_o, rhs_o);
    if (res_o == NULL) {
        ERROR_NO_POP();
    }
    /* CLAMPPVM: Intercept arithmetic operations when clamp mode is enabled */
    if (_Py_Clamp_State.enabled) {
        res_o = _Py_Clamp_Apply(oparg, res_o);
    }
    res = PyStackRef_FromPyObjectSteal(res_o);
    l = lhs;
    r = rhs;
    DEAD(lhs);
    DEAD(rhs);
}
```

**Architectural Rationale:**
- `_PyEval_BinaryOps[oparg]` produces a newly allocated or referenced Python object (`res_o`).
- If `_Py_Clamp_State.enabled` is active, `_Py_Clamp_Apply` checks whether `oparg` is one of `NB_ADD`, `NB_SUBTRACT`, `NB_MULTIPLY`, `NB_INPLACE_ADD`, `NB_INPLACE_SUBTRACT`, or `NB_INPLACE_MULTIPLY`.
- If `res_o < clamp_min` or `res_o > clamp_max`, `_Py_Clamp_Apply` safely calls `Py_DECREF(res_o)`, creates a fresh typed object matching the bound, and returns it.
- `PyStackRef_FromPyObjectSteal(res_o)` transfers reference ownership to the interpreter stack with **zero reference leaks** and **zero double-frees**.

---

### 2.2 Adaptive Specialization Guard (`_SPECIALIZE_BINARY_OP`)

#### 🔴 Original Upstream CPython
```c
specializing op(_SPECIALIZE_BINARY_OP, (counter/1, lhs, rhs -- lhs, rhs)) {
    #if ENABLE_SPECIALIZATION
    if (ADAPTIVE_COUNTER_TRIGGERS(counter)) {
        next_instr = this_instr;
        _Py_Specialize_BinaryOp(lhs, rhs, next_instr, oparg, LOCALS_ARRAY);
        DISPATCH_SAME_OPARG();
    }
    OPCODE_DEFERRED_INC(BINARY_OP);
    ADVANCE_ADAPTIVE_COUNTER(this_instr[1].counter);
    #endif  /* ENABLE_SPECIALIZATION */
    assert(NB_ADD <= oparg);
    assert(oparg <= NB_OPARG_LAST);
}
```

#### 🟢 ClampPVM Modified Version
```c
specializing op(_SPECIALIZE_BINARY_OP, (counter/1, lhs, rhs -- lhs, rhs)) {
    #if ENABLE_SPECIALIZATION
    /* CLAMPPVM: Suppress specialization while clamped arithmetic mode is active */
    if (!_Py_Clamp_State.enabled && ADAPTIVE_COUNTER_TRIGGERS(counter)) {
        next_instr = this_instr;
        _Py_Specialize_BinaryOp(lhs, rhs, next_instr, oparg, LOCALS_ARRAY);
        DISPATCH_SAME_OPARG();
    }
    OPCODE_DEFERRED_INC(BINARY_OP);
    ADVANCE_ADAPTIVE_COUNTER(this_instr[1].counter);
    #endif  /* ENABLE_SPECIALIZATION */
    assert(NB_ADD <= oparg);
    assert(oparg <= NB_OPARG_LAST);
}
```

**Architectural Rationale:**
- Modern CPython (3.12+) uses adaptive bytecode specialization, replacing general `BINARY_OP` with specialized uops like `BINARY_OP_ADD_INT`.
- ClampPVM suppresses specialization whenever `_Py_Clamp_State.enabled` is active, forcing all operations to execute through the monitored `_BINARY_OP` path.
- When clamping is disabled, specialization runs unmodified with peak baseline performance.

---

### 2.3 Tier-1 / Tier-2 Micro-Op De-optimization (`Python/bytecodes.c`)

#### 🔴 Original Upstream CPython
```c
pure op(_BINARY_OP_ADD_INT, (left, right -- res, l, r)) {
    PyObject *left_o = PyStackRef_AsPyObjectBorrow(left);
    PyObject *right_o = PyStackRef_AsPyObjectBorrow(right);
    assert(PyLong_CheckExact(left_o));
    assert(PyLong_CheckExact(right_o));
    assert(_PyLong_BothAreCompact((PyLongObject *)left_o, (PyLongObject *)right_o));

    STAT_INC(BINARY_OP, hit);
    res = _PyCompactLong_Add((PyLongObject *)left_o, (PyLongObject *)right_o);
    EXIT_IF(PyStackRef_IsNull(res));
    l = left;
    r = right;
    INPUTS_DEAD();
}
```

#### 🟢 ClampPVM Modified Version
```c
pure op(_BINARY_OP_ADD_INT, (left, right -- res, l, r)) {
    /* CLAMPPVM: De-optimize if clamp mode is activated at runtime */
    EXIT_IF(_Py_Clamp_State.enabled);
    PyObject *left_o = PyStackRef_AsPyObjectBorrow(left);
    PyObject *right_o = PyStackRef_AsPyObjectBorrow(right);
    assert(PyLong_CheckExact(left_o));
    assert(PyLong_CheckExact(right_o));
    assert(_PyLong_BothAreCompact((PyLongObject *)left_o, (PyLongObject *)right_o));

    STAT_INC(BINARY_OP, hit);
    res = _PyCompactLong_Add((PyLongObject *)left_o, (PyLongObject *)right_o);
    EXIT_IF(PyStackRef_IsNull(res));
    l = left;
    r = right;
    INPUTS_DEAD();
}
```

**Architectural Rationale:**
- If bytecode was already specialized before `sys.set_clamp_mode(True)` was called, executing the specialized opcode checks `EXIT_IF(_Py_Clamp_State.enabled)`.
- The opcode immediately de-optimizes back to the generic `BINARY_OP` handler, ensuring clamping is never bypassed by cached or tier-2 compiled traces.

---

## 3. Flowgraph Compiler Constant-Folding Bypass (`Python/flowgraph.c`)

### 🔴 Original Upstream CPython
```c
static PyObject *
eval_const_binop(PyObject *left, int op, PyObject *right)
{
    assert(left != NULL && right != NULL);
    assert(op >= 0 && op <= NB_OPARG_LAST);

    PyObject *result = NULL;
    switch (op) {
        case NB_ADD:
            result = PyNumber_Add(left, right);
            break;
        case NB_SUBTRACT:
            result = PyNumber_Subtract(left, right);
            break;
        case NB_MULTIPLY:
            result = const_folding_safe_multiply(left, right);
            break;
        case NB_TRUE_DIVIDE:
            result = PyNumber_TrueDivide(left, right);
            break;
        /* ... */
    }
    return result;
}
```

### 🟢 ClampPVM Modified Version
```c
static PyObject *
eval_const_binop(PyObject *left, int op, PyObject *right)
{
    assert(left != NULL && right != NULL);
    assert(op >= 0 && op <= NB_OPARG_LAST);

    PyObject *result = NULL;
    switch (op) {
        /* CLAMPPVM: Inhibit compile-time constant folding for arithmetic.
         * Forces the compiler to emit runtime BINARY_OP bytecodes so that
         * runtime clamp mode activations apply accurately to literal math.
         */
        case NB_ADD:
            return NULL;
        case NB_SUBTRACT:
            return NULL;
        case NB_MULTIPLY:
            return NULL;
        case NB_TRUE_DIVIDE:
            result = PyNumber_TrueDivide(left, right);
            break;
        /* ... */
    }
    return result;
}
```

**Architectural Rationale:**
- In standard CPython, expressions like `80 + 50` are evaluated during AST/flowgraph optimization and replaced with `LOAD_SMALL_INT 130`.
- If constant-folded at compile time, code executing inside `with clamp_scope(0, 100):` would load the pre-computed `130` instead of dynamically saturating to `100`.
- Returning `NULL` instructs the compiler to omit constant folding and emit regular `BINARY_OP` bytecode, ensuring full runtime flexibility.

---

## 4. System Module Extensions (`Python/sysmodule.c`)

### 🔴 Original Upstream CPython
No clamp methods present in `sys_methods[]`.

### 🟢 ClampPVM Added Methods
```c
static PyMethodDef sys_methods[] = {
    {"set_clamp_mode", sys_set_clamp_mode, METH_O, set_clamp_mode_doc},
    {"get_clamp_mode", sys_get_clamp_mode, METH_NOARGS, get_clamp_mode_doc},
    {"set_clamp_bounds", sys_set_clamp_bounds, METH_VARARGS, set_clamp_bounds_doc},
    {"get_clamp_bounds", sys_get_clamp_bounds, METH_NOARGS, get_clamp_bounds_doc},
    {"get_clamp_stats", sys_get_clamp_stats, METH_NOARGS, get_clamp_stats_doc},
    {"reset_clamp_stats", sys_reset_clamp_stats, METH_NOARGS, reset_clamp_stats_doc},
    /* ... standard sys methods ... */
};
```

---

## 5. Version Banner & Platform Compatibility

### 5.1 Python Version String (`Python/getversion.c`)
- **Original:** `3.16.0a2+dev (heads/main...)`
- **ClampPVM:** `3.16.0a2+dev [ClampPVM] (heads/main...)`

### 5.2 Platform Parser (`Lib/platform.py`)
- **Original:** Expects standard version identifier immediately preceding build info.
- **ClampPVM:** Updated regex `r'(?:\[ClampPVM\]\s+)?'` ensures compatibility with `pip`, `ensurepip`, and third-party tools inspecting `platform.python_version()`.
