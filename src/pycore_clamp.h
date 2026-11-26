/* =============================================================================
 * FILE PURPOSE:
 * Core CPython internal header defining the ClampPVM saturating arithmetic runtime
 * state structure, function prototypes, and inline evaluator mode checks. It is
 * included by Python/ceval.c, Python/sysmodule.c, and Python/clamp.c during build.
 * =============================================================================
 */

#ifndef Py_INTERNAL_CLAMP_H
#define Py_INTERNAL_CLAMP_H

#ifdef __cplusplus
extern "C" {
#endif

#ifndef Py_BUILD_CORE
#  error "this header requires Py_BUILD_CORE define"
#endif

#include "pycore_pystate.h"

/*
 * ClampPVM Runtime State Structure
 * Maintains the saturation arithmetic mode switch, numerical boundary objects,
 * and an atomic telemetry counter for intercepted boundary events.
 */
typedef struct {
    int enabled;               /* 1 if saturating arithmetic is enabled, 0 otherwise */
    double min_val;            /* Numeric lower bound (float representation) */
    double max_val;            /* Numeric upper bound (float representation) */
    PyObject *min_obj;         /* Python object representation of lower bound */
    PyObject *max_obj;         /* Python object representation of upper bound */
    uint64_t clamped_count;    /* Total count of clamped operations since reset */
} _PyClampState;

/* Global clamp runtime state shared across the interpreter */
extern _PyClampState _Py_Clamp_State;

/* Fast inline check queried inside the PVM evaluation loop */
static inline int _Py_GetClampMode(void) {
    return _Py_Clamp_State.enabled;
}

/* Lifecycle and runtime configuration APIs */
void _Py_SetClampMode(int enabled);
int _Py_SetClampBounds(PyObject *min_obj, PyObject *max_obj);
PyObject* _Py_GetClampBounds(void);
PyObject* _Py_GetClampStats(void);
void _Py_ResetClampStats(void);
void _Py_Clamp_Init(void);

/* Interception and clamping engine invoked after binary operations */
PyObject* _Py_Clamp_Apply(int oparg, PyObject *res_o);

#ifdef __cplusplus
}
#endif

#endif /* !Py_INTERNAL_CLAMP_H */
