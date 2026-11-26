/* =============================================================================
 * FILE PURPOSE:
 * Implements the core Saturating / Clamped Arithmetic engine for the ClampPVM CPython
 * runtime. Provides initialization from environment variables, runtime boundary
 * management via sys, and typed numeric clamping with balanced reference counts.
 * =============================================================================
 */

#include "Python.h"
#include "pycore_clamp.h"
#include "opcode.h"
#include <stdlib.h>
#include <string.h>

/*
 * =============================================================================
 * SIDE-BY-SIDE ARCHITECTURAL COMPARISON:
 * 
 * [ORIGINAL CPYTHON EVALUATOR BEHAVIOR]
 * In standard CPython, binary arithmetic executes directly in Python/ceval.c:
 * 
 *     PyObject *res_o = _PyEval_BinaryOps[oparg](lhs_o, rhs_o);
 *     if (res_o == NULL) { ERROR_NO_POP(); }
 *     res = PyStackRef_FromPyObjectSteal(res_o);
 * 
 * Any numeric calculation exceeding operational boundaries either overflows,
 * wraps, or produces unbounded values without runtime intervention.
 * 
 * [CLAMPPVM MODIFIED BEHAVIOR]
 * ClampPVM hooks into the result pipeline immediately after computation:
 * 
 *     PyObject *res_o = _PyEval_BinaryOps[oparg](lhs_o, rhs_o);
 *     if (res_o == NULL) { ERROR_NO_POP(); }
 *     if (_Py_Clamp_State.enabled) {
 *         res_o = _Py_Clamp_Apply(oparg, res_o);
 *     }
 *     res = PyStackRef_FromPyObjectSteal(res_o);
 * 
 * If res_o exceeds [clamp_min, clamp_max], res_o is safely DECREF'd, replaced
 * with a cleanly typed bound object, and the telemetry counter is incremented.
 * =============================================================================
 */

_PyClampState _Py_Clamp_State = {
    .enabled = 0,
    .min_val = 0.0,
    .max_val = 100.0,
    .min_obj = NULL,
    .max_obj = NULL,
    .clamped_count = 0,
};

static int _clamp_initialized = 0;

/* Initializes clamp bounds and checks startup environment variables */
void _Py_Clamp_Init(void) {
    if (_clamp_initialized) {
        return;
    }
    _clamp_initialized = 1;

    _Py_Clamp_State.min_val = 0.0;
    _Py_Clamp_State.max_val = 100.0;
    _Py_Clamp_State.min_obj = PyLong_FromLong(0);
    _Py_Clamp_State.max_obj = PyLong_FromLong(100);
    _Py_Clamp_State.clamped_count = 0;
    _Py_Clamp_State.enabled = 0;

    /* Check PVM_CLAMP_MIN environment variable */
    const char *env_min = getenv("PVM_CLAMP_MIN");
    if (env_min != NULL && env_min[0] != '\0') {
        char *endptr = NULL;
        double v = strtod(env_min, &endptr);
        if (endptr != env_min) {
            _Py_Clamp_State.min_val = v;
            Py_XDECREF(_Py_Clamp_State.min_obj);
            if (strchr(env_min, '.') != NULL) {
                _Py_Clamp_State.min_obj = PyFloat_FromDouble(v);
            } else {
                _Py_Clamp_State.min_obj = PyLong_FromLong((long)v);
            }
        }
    }

    /* Check PVM_CLAMP_MAX environment variable */
    const char *env_max = getenv("PVM_CLAMP_MAX");
    if (env_max != NULL && env_max[0] != '\0') {
        char *endptr = NULL;
        double v = strtod(env_max, &endptr);
        if (endptr != env_max) {
            _Py_Clamp_State.max_val = v;
            Py_XDECREF(_Py_Clamp_State.max_obj);
            if (strchr(env_max, '.') != NULL) {
                _Py_Clamp_State.max_obj = PyFloat_FromDouble(v);
            } else {
                _Py_Clamp_State.max_obj = PyLong_FromLong((long)v);
            }
        }
    }

    /* Check PVM_CLAMP environment variable */
    const char *env_clamp = getenv("PVM_CLAMP");
    if (env_clamp != NULL && env_clamp[0] != '\0') {
        if (strcmp(env_clamp, "1") == 0 ||
            strcasecmp(env_clamp, "true") == 0 ||
            strcasecmp(env_clamp, "yes") == 0 ||
            strcasecmp(env_clamp, "on") == 0) {
            _Py_Clamp_State.enabled = 1;
        }
    }
}

/* Enable or disable saturating arithmetic mode */
void _Py_SetClampMode(int enabled) {
    _Py_Clamp_Init();
    _Py_Clamp_State.enabled = (enabled != 0);
}

/* Update numerical bounds with strict type checking and order validation */
int _Py_SetClampBounds(PyObject *min_obj, PyObject *max_obj) {
    _Py_Clamp_Init();
    if (!PyNumber_Check(min_obj) || !PyNumber_Check(max_obj)) {
        PyErr_SetString(PyExc_TypeError, "clamp bounds must be numeric (int or float)");
        return -1;
    }

    int cmp = PyObject_RichCompareBool(min_obj, max_obj, Py_GT);
    if (cmp > 0) {
        PyErr_SetString(PyExc_ValueError, "clamp_min must be <= clamp_max");
        return -1;
    } else if (cmp < 0) {
        return -1;
    }

    double min_v = PyFloat_AsDouble(min_obj);
    if (min_v == -1.0 && PyErr_Occurred()) {
        return -1;
    }
    double max_v = PyFloat_AsDouble(max_obj);
    if (max_v == -1.0 && PyErr_Occurred()) {
        return -1;
    }

    _Py_Clamp_State.min_val = min_v;
    _Py_Clamp_State.max_val = max_v;

    Py_XDECREF(_Py_Clamp_State.min_obj);
    Py_XDECREF(_Py_Clamp_State.max_obj);
    _Py_Clamp_State.min_obj = Py_NewRef(min_obj);
    _Py_Clamp_State.max_obj = Py_NewRef(max_obj);

    return 0;
}

/* Retrieve currently configured bounds as a Python tuple */
PyObject* _Py_GetClampBounds(void) {
    _Py_Clamp_Init();
    return PyTuple_Pack(2, _Py_Clamp_State.min_obj, _Py_Clamp_State.max_obj);
}

/* Retrieve telemetry statistics dictionary */
PyObject* _Py_GetClampStats(void) {
    _Py_Clamp_Init();
    return Py_BuildValue("{s:K}", "clamped_count", (unsigned long long)_Py_Clamp_State.clamped_count);
}

/* Reset the telemetry counter to 0 */
void _Py_ResetClampStats(void) {
    _Py_Clamp_State.clamped_count = 0;
}

/*
 * Evaluates binary arithmetic result against configured bounds.
 * Clamps integers and floats cleanly, returning a newly owned reference.
 */
PyObject* _Py_Clamp_Apply(int oparg, PyObject *res_o) {
    if (!_Py_Clamp_State.enabled || res_o == NULL) {
        return res_o;
    }

    /* Intercept additions, subtractions, and multiplications (standard & inplace) */
    switch (oparg) {
        case NB_ADD:
        case NB_SUBTRACT:
        case NB_MULTIPLY:
        case NB_INPLACE_ADD:
        case NB_INPLACE_SUBTRACT:
        case NB_INPLACE_MULTIPLY:
            break;
        default:
            return res_o;
    }

    /* Only clamp numeric types (skip strings, lists, tuples, custom classes) */
    if (!PyLong_CheckExact(res_o) && !PyFloat_CheckExact(res_o)) {
        return res_o;
    }

    /* Check if result < clamp_min */
    int cmp_min = PyObject_RichCompareBool(res_o, _Py_Clamp_State.min_obj, Py_LT);
    if (cmp_min < 0) {
        PyErr_Clear();
        return res_o;
    }
    if (cmp_min > 0) {
        PyObject *replacement = NULL;
        if (PyLong_CheckExact(res_o)) {
            if (PyLong_CheckExact(_Py_Clamp_State.min_obj)) {
                replacement = Py_NewRef(_Py_Clamp_State.min_obj);
            } else {
                replacement = PyLong_FromDouble(_Py_Clamp_State.min_val);
            }
        } else {
            if (PyFloat_CheckExact(_Py_Clamp_State.min_obj)) {
                replacement = Py_NewRef(_Py_Clamp_State.min_obj);
            } else {
                replacement = PyFloat_FromDouble(_Py_Clamp_State.min_val);
            }
        }
        if (replacement != NULL) {
            _Py_Clamp_State.clamped_count++;
            Py_DECREF(res_o);
            return replacement;
        }
        PyErr_Clear();
        return res_o;
    }

    /* Check if result > clamp_max */
    int cmp_max = PyObject_RichCompareBool(res_o, _Py_Clamp_State.max_obj, Py_GT);
    if (cmp_max < 0) {
        PyErr_Clear();
        return res_o;
    }
    if (cmp_max > 0) {
        PyObject *replacement = NULL;
        if (PyLong_CheckExact(res_o)) {
            if (PyLong_CheckExact(_Py_Clamp_State.max_obj)) {
                replacement = Py_NewRef(_Py_Clamp_State.max_obj);
            } else {
                replacement = PyLong_FromDouble(_Py_Clamp_State.max_val);
            }
        } else {
            if (PyFloat_CheckExact(_Py_Clamp_State.max_obj)) {
                replacement = Py_NewRef(_Py_Clamp_State.max_obj);
            } else {
                replacement = PyFloat_FromDouble(_Py_Clamp_State.max_val);
            }
        }
        if (replacement != NULL) {
            _Py_Clamp_State.clamped_count++;
            Py_DECREF(res_o);
            return replacement;
        }
        PyErr_Clear();
        return res_o;
    }

    return res_o;
}
