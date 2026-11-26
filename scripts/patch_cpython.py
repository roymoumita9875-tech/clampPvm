# =============================================================================
# FILE PURPOSE:
# Automated CPython source tree patcher for Flavor #7: ClampPVM.
# Injects the saturating arithmetic C engine, internal header, bytecode hooks,
# flowgraph constant-folding bypass, and sysmodule bindings into any CPython tree.
# Usage: python3 scripts/patch_cpython.py [path/to/cpython-src]
# =============================================================================

import os
import sys
import shutil
import re

def patch_cpython(cpython_dir: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    src_dir = os.path.join(repo_root, "src")

    print(f"[*] Patching CPython source at: {cpython_dir}")

    # 1. Copy pycore_clamp.h
    target_header = os.path.join(cpython_dir, "Include", "internal", "pycore_clamp.h")
    shutil.copyfile(os.path.join(src_dir, "pycore_clamp.h"), target_header)
    print("  [+] Installed Include/internal/pycore_clamp.h")

    # 2. Copy clamp.c
    target_clamp_c = os.path.join(cpython_dir, "Python", "clamp.c")
    shutil.copyfile(os.path.join(src_dir, "clamp.c"), target_clamp_c)
    print("  [+] Installed Python/clamp.c")

    # 3. Update Include/internal/pycore_ceval.h
    ceval_h_path = os.path.join(cpython_dir, "Include", "internal", "pycore_ceval.h")
    with open(ceval_h_path, "r") as f:
        ceval_h = f.read()
    if '#include "pycore_clamp.h"' not in ceval_h:
        ceval_h = ceval_h.replace('#include "pycore_pystate.h"', '#include "pycore_pystate.h"\n#include "pycore_clamp.h"')
        with open(ceval_h_path, "w") as f:
            f.write(ceval_h)
        print("  [+] Included pycore_clamp.h in pycore_ceval.h")

    # 4. Update Makefile.pre.in and Makefile
    for mf_name in ["Makefile.pre.in", "Makefile"]:
        mf_path = os.path.join(cpython_dir, mf_name)
        if os.path.exists(mf_path):
            with open(mf_path, "r") as f:
                mf_content = f.read()
            if "Python/clamp.o" not in mf_content:
                mf_content = mf_content.replace("Python/ceval.o \\", "Python/ceval.o \\\n\t\tPython/clamp.o \\")
                with open(mf_path, "w") as f:
                    f.write(mf_content)
                print(f"  [+] Added Python/clamp.o to {mf_name}")

    # 5. Update Python/getversion.c
    gv_path = os.path.join(cpython_dir, "Python", "getversion.c")
    with open(gv_path, "r") as f:
        gv = f.read()
    if "[ClampPVM]" not in gv:
        gv = gv.replace('const char *buildinfo_format = "%.80s (%.80s) %.80s";',
                        'const char *buildinfo_format = "%.80s [ClampPVM] (%.80s) %.80s";')
        gv = gv.replace('const char *buildinfo_format = "%.80s free-threading build (%.80s) %.80s";',
                        'const char *buildinfo_format = "%.80s free-threading build [ClampPVM] (%.80s) %.80s";')
        with open(gv_path, "w") as f:
            f.write(gv)
        print("  [+] Tagged Python/getversion.c with [ClampPVM]")

    # 6. Update Python/sysmodule.c
    sys_path = os.path.join(cpython_dir, "Python", "sysmodule.c")
    with open(sys_path, "r") as f:
        sys_src = f.read()

    clamp_methods = """
/* ClampPVM sys methods */
static PyObject *
sys_set_clamp_mode(PyObject *module, PyObject *arg)
{
    int enabled = PyObject_IsTrue(arg);
    if (enabled < 0) {
        return NULL;
    }
    _Py_SetClampMode(enabled);
    Py_RETURN_NONE;
}

PyDoc_STRVAR(set_clamp_mode_doc,
"set_clamp_mode(enabled) -> None\\n\\
\\n\\
Enable or disable saturating / clamped arithmetic mode in the PVM.");

static PyObject *
sys_get_clamp_mode(PyObject *module, PyObject *Py_UNUSED(ignored))
{
    return PyBool_FromLong(_Py_GetClampMode());
}

PyDoc_STRVAR(get_clamp_mode_doc,
"get_clamp_mode() -> bool\\n\\
\\n\\
Return whether saturating / clamped arithmetic mode is enabled.");

static PyObject *
sys_set_clamp_bounds(PyObject *module, PyObject *args)
{
    PyObject *min_obj, *max_obj;
    if (!PyArg_ParseTuple(args, "OO:set_clamp_bounds", &min_obj, &max_obj)) {
        return NULL;
    }
    if (_Py_SetClampBounds(min_obj, max_obj) < 0) {
        return NULL;
    }
    Py_RETURN_NONE;
}

PyDoc_STRVAR(set_clamp_bounds_doc,
"set_clamp_bounds(min_val, max_val) -> None\\n\\
\\n\\
Set the numeric lower and upper bounds for saturating / clamped arithmetic.");

static PyObject *
sys_get_clamp_bounds(PyObject *module, PyObject *Py_UNUSED(ignored))
{
    return _Py_GetClampBounds();
}

PyDoc_STRVAR(get_clamp_bounds_doc,
"get_clamp_bounds() -> tuple\\n\\
\\n\\
Return (min_val, max_val) bounds configured for clamped arithmetic.");

static PyObject *
sys_get_clamp_stats(PyObject *module, PyObject *Py_UNUSED(ignored))
{
    return _Py_GetClampStats();
}

PyDoc_STRVAR(get_clamp_stats_doc,
"get_clamp_stats() -> dict\\n\\
\\n\\
Return clamp telemetry dictionary {'clamped_count': N}.");

static PyObject *
sys_reset_clamp_stats(PyObject *module, PyObject *Py_UNUSED(ignored))
{
    _Py_ResetClampStats();
    Py_RETURN_NONE;
}

PyDoc_STRVAR(reset_clamp_stats_doc,
"reset_clamp_stats() -> None\\n\\
\\n\\
Reset the clamped count telemetry counter to 0.");
"""

    if '#include "pycore_clamp.h"' not in sys_src:
        sys_src = sys_src.replace('#include "pycore_sysmodule.h"', '#include "pycore_sysmodule.h"\n#include "pycore_clamp.h"')
        sys_src = sys_src.replace(
            "static PyMethodDef sys_methods[] = {",
            clamp_methods + "\nstatic PyMethodDef sys_methods[] = {\n    {\"set_clamp_mode\", sys_set_clamp_mode, METH_O, set_clamp_mode_doc},\n    {\"get_clamp_mode\", sys_get_clamp_mode, METH_NOARGS, get_clamp_mode_doc},\n    {\"set_clamp_bounds\", sys_set_clamp_bounds, METH_VARARGS, set_clamp_bounds_doc},\n    {\"get_clamp_bounds\", sys_get_clamp_bounds, METH_NOARGS, get_clamp_bounds_doc},\n    {\"get_clamp_stats\", sys_get_clamp_stats, METH_NOARGS, get_clamp_stats_doc},\n    {\"reset_clamp_stats\", sys_reset_clamp_stats, METH_NOARGS, reset_clamp_stats_doc},"
        )
        sys_src = sys_src.replace(
            "_PySys_Create(PyThreadState *tstate, PyObject **sysmod_p)\n{",
            "_PySys_Create(PyThreadState *tstate, PyObject **sysmod_p)\n{\n    _Py_Clamp_Init();"
        )
        with open(sys_path, "w") as f:
            f.write(sys_src)
        print("  [+] Added Clamp sys bindings to Python/sysmodule.c")

    # 7. Update Python/bytecodes.c
    bc_path = os.path.join(cpython_dir, "Python", "bytecodes.c")
    with open(bc_path, "r") as f:
        bc = f.read()

    specialized_uops = [
        "_BINARY_OP_MULTIPLY_INT",
        "_BINARY_OP_ADD_INT",
        "_BINARY_OP_SUBTRACT_INT",
        "_BINARY_OP_ADD_INT_INPLACE",
        "_BINARY_OP_SUBTRACT_INT_INPLACE",
        "_BINARY_OP_MULTIPLY_INT_INPLACE",
        "_BINARY_OP_ADD_INT_INPLACE_RIGHT",
        "_BINARY_OP_SUBTRACT_INT_INPLACE_RIGHT",
        "_BINARY_OP_MULTIPLY_INT_INPLACE_RIGHT",
        "_BINARY_OP_MULTIPLY_FLOAT",
        "_BINARY_OP_ADD_FLOAT",
        "_BINARY_OP_SUBTRACT_FLOAT",
        "_BINARY_OP_ADD_FLOAT_INPLACE",
        "_BINARY_OP_SUBTRACT_FLOAT_INPLACE",
        "_BINARY_OP_MULTIPLY_FLOAT_INPLACE",
        "_BINARY_OP_ADD_FLOAT_INPLACE_RIGHT",
        "_BINARY_OP_MULTIPLY_FLOAT_INPLACE_RIGHT",
        "_BINARY_OP_SUBTRACT_FLOAT_INPLACE_RIGHT",
    ]

    for uop in specialized_uops:
        pattern = rf"(op\({uop},[^{{]+\{{\n)"
        replacement = rf"\1            EXIT_IF(_Py_Clamp_State.enabled);\n"
        if f"EXIT_IF(_Py_Clamp_State.enabled);" not in bc:
            bc = re.sub(pattern, replacement, bc)

    target_spec = """        specializing op(_SPECIALIZE_BINARY_OP, (counter/1, lhs, rhs -- lhs, rhs)) {
            #if ENABLE_SPECIALIZATION
            if (ADAPTIVE_COUNTER_TRIGGERS(counter)) {"""
    repl_spec = """        specializing op(_SPECIALIZE_BINARY_OP, (counter/1, lhs, rhs -- lhs, rhs)) {
            #if ENABLE_SPECIALIZATION
            if (!_Py_Clamp_State.enabled && ADAPTIVE_COUNTER_TRIGGERS(counter)) {"""
    if target_spec in bc:
        bc = bc.replace(target_spec, repl_spec, 1)

    target_binop = """        op(_BINARY_OP, (lhs, rhs -- res, l, r)) {
            PyObject *lhs_o = PyStackRef_AsPyObjectBorrow(lhs);
            PyObject *rhs_o = PyStackRef_AsPyObjectBorrow(rhs);

            assert(_PyEval_BinaryOps[oparg]);
            PyObject *res_o = _PyEval_BinaryOps[oparg](lhs_o, rhs_o);
            if (res_o == NULL) {
                ERROR_NO_POP();
            }
            res = PyStackRef_FromPyObjectSteal(res_o);"""

    repl_binop = """        op(_BINARY_OP, (lhs, rhs -- res, l, r)) {
            PyObject *lhs_o = PyStackRef_AsPyObjectBorrow(lhs);
            PyObject *rhs_o = PyStackRef_AsPyObjectBorrow(rhs);

            assert(_PyEval_BinaryOps[oparg]);
            PyObject *res_o = _PyEval_BinaryOps[oparg](lhs_o, rhs_o);
            if (res_o == NULL) {
                ERROR_NO_POP();
            }
            if (_Py_Clamp_State.enabled) {
                res_o = _Py_Clamp_Apply(oparg, res_o);
            }
            res = PyStackRef_FromPyObjectSteal(res_o);"""
    if target_binop in bc:
        bc = bc.replace(target_binop, repl_binop, 1)

    with open(bc_path, "w") as f:
        f.write(bc)
    print("  [+] Injected VM interception into Python/bytecodes.c")

    # 8. Update Python/flowgraph.c
    fg_path = os.path.join(cpython_dir, "Python", "flowgraph.c")
    with open(fg_path, "r") as f:
        fg = f.read()
    fg_target = """    switch (op) {
        case NB_ADD:
            result = PyNumber_Add(left, right);
            break;
        case NB_SUBTRACT:
            result = PyNumber_Subtract(left, right);
            break;
        case NB_MULTIPLY:
            result = const_folding_safe_multiply(left, right);
            break;"""
    fg_repl = """    switch (op) {
        case NB_ADD:
            return NULL;
        case NB_SUBTRACT:
            return NULL;
        case NB_MULTIPLY:
            return NULL;"""
    if fg_target in fg:
        fg = fg.replace(fg_target, fg_repl, 1)
        with open(fg_path, "w") as f:
            f.write(fg)
        print("  [+] Bypassed constant folding in Python/flowgraph.c")

    # 9. Update Lib/platform.py
    plat_path = os.path.join(cpython_dir, "Lib", "platform.py")
    with open(plat_path, "r") as f:
        plat = f.read()
    plat_target = """        cpython_sys_version_parser = re.compile(
            r'([\\w.+]+)\\s*'  # \"version<space>\"
            r'(?:free-threading build\\s+)?' # \"free-threading-build<space>\"
            r'\\(#?([^,]+)'  # \"(#buildno\""""
    plat_repl = """        cpython_sys_version_parser = re.compile(
            r'([\\w.+]+)\\s*'  # \"version<space>\"
            r'(?:free-threading build\\s+)?' # \"free-threading-build<space>\"
            r'(?:\\[ClampPVM\\]\\s+)?'
            r'\\(#?([^,]+)'  # \"(#buildno\""""
    if plat_target in plat:
        plat = plat.replace(plat_target, plat_repl, 1)
        with open(plat_path, "w") as f:
            f.write(plat)
        print("  [+] Updated version regex in Lib/platform.py")

    print("[*] All ClampPVM patches successfully applied!")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "/home/subha/pvm-clamp/cpython-src"
    patch_cpython(target)
