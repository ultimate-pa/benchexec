/*
 * This file is part of BenchExec, a framework for reliable benchmarking:
 * https://github.com/sosy-lab/benchexec
 *
 * SPDX-FileCopyrightText: 2026 Manuel Bentele
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <assert.h>
#include <errno.h>
#include <sched.h>
#include <signal.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <sys/types.h>
#include <unistd.h>

/**
 * Helper macro to add an integer constant to a Python module.
 *
 * @param module Python module object.
 * @param name Name of the integer constant.
 */
#define PY_MOD_ADD_INT_CONST(module, name)                  \
    do {                                                    \
        if (PyModule_AddIntConstant(module, #name, name)) { \
            return -1;                                      \
        }                                                   \
    } while (0)

/**
 * Default size for stack allocation (1 MB).
 */
#define DEFAULT_STACK_SIZE (1024 * 1024)

/**
 * Documentation string for the 'ose' Python extension module.
 */
PyDoc_STRVAR(ose_doc,
             "This module provides access to operating system functionality that is standardized by the C Standard and "
             "the POSIX standard (a thinly disguised Unix interface).  Refer to the library manual and corresponding "
             "Unix manual entries for more information on calls.");

/**
 * Sets a Python OSError based on errno and returns NULL.
 *
 * @return NULL after setting the error.
 */
static inline PyObject *
ose_error(void)
{
    return PyErr_SetFromErrno(PyExc_OSError);
}

/**
 * Retrieves the system's page size.
 *
 * @return The page size in bytes.
 */
static inline long
ose_page_size(void)
{
    const long page_size = sysconf(_SC_PAGESIZE);
    assert(page_size > 0);
    return page_size;
}

/**
 * Structure representing a stack object.
 */
typedef struct {
    /* clang-format off */
    PyObject_HEAD
    /** Base address of the allocated stack memory. */
    void *base;
    /** Size of the allocated stack memory. */
    size_t size;
    /* clang-format on */
} StackObject;

/**
 * Gets the module object associated with a type.
 *
 * @param type Python type object.
 *
 * @return Python module object.
 */
static inline PyObject *
ose_stack_get_module(PyTypeObject *type)
{
    PyObject *module = PyType_GetModule(type);
    assert(module != NULL);
    return module;
}

/**
 * Deinitializes a stack object, releasing allocated stack memory.
 *
 * @param self Pointer to the stack object.
 */
static void
ose_stack_deinit(StackObject *self)
{
    if (self->base) {
        munmap(self->base, self->size + ose_page_size());
        self->base = NULL;
        self->size = 0;
    }
}

/**
 * Deallocates a stack object.
 *
 * @param self Pointer to the stack object.
 */
static void
ose_stack_dealloc(StackObject *self)
{
    ose_stack_deinit(self);
    Py_TYPE(self)->tp_free((PyObject *)self);
}

/**
 * Creates a new stack object.
 *
 * @param type Python type object.
 * @param args Positional arguments.
 * @param kwds Keyword arguments.
 *
 * @return New stack object.
 */
static PyObject *
ose_stack_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    StackObject *self;

    self = (StackObject *)type->tp_alloc(type, 0);
    if (self) {
        self->base = NULL;
        self->size = 0;
    }

    return (PyObject *)self;
}

/**
 * Initializes a stack object with optional size parameter.
 *
 * @param self Pointer to the stack object.
 * @param args Positional arguments.
 * @param kwds Keyword arguments.
 *
 * @return 0 on success, -1 on failure.
 */
static int
ose_stack_init(StackObject *self, PyObject *args, PyObject *kwds)
{
    const long page_size = ose_page_size();
    Py_ssize_t stack_size = DEFAULT_STACK_SIZE;

    static char *kwlist[] = {"size", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|n", kwlist, &stack_size)) {
        return -1;
    }

    if (stack_size <= 0) {
        PyErr_SetString(PyExc_ValueError, "stack size must be positive");
        return -1;
    }

    /* Allow reinitialization without leaking the old mapping */
    ose_stack_deinit(self);

    /* Allocate the stack memory of the configured size with one additional guard page */
    self->size = stack_size;
    self->base = mmap(NULL,
                      self->size + page_size,
                      PROT_READ | PROT_WRITE,
                      MAP_GROWSDOWN | MAP_STACK | MAP_PRIVATE | MAP_ANONYMOUS,
                      -1,
                      0);
    if (self->base == MAP_FAILED) {
        ose_error();
        self->base = NULL;
        self->size = 0;
        return -1;
    }

    /* Configure guard page that crashes the application when it is written to (on stack overflow) */
    if (mprotect(self->base, page_size, PROT_NONE) < 0) {
        ose_error();
        ose_stack_deinit(self);
        return -1;
    }

    return 0;
}

/**
 * Entering the stack context (for use with 'with' statement).
 *
 * @param self The stack object.
 *
 * @return The same object.
 */
static PyObject *
ose_stack_enter(PyObject *self, PyObject *args)
{
    Py_INCREF(self);
    return self;
}

/**
 * Exiting the stack context, deinitializing the stack.
 *
 * @param self The stack object.
 *
 * @return False to indicate exception propagation.
 */
static PyObject *
ose_stack_exit(PyObject *self, PyObject *args)
{
    ose_stack_deinit((StackObject *)self);

    /* Do not suppress exceptions */
    Py_RETURN_FALSE;
}

/**
 * Methods for the stack type.
 */
static PyMethodDef ose_stack_methods[] = {
    {"__enter__", (PyCFunction)ose_stack_enter, METH_NOARGS, PyDoc_STR("Enter context manager")},
    {"__exit__", (PyCFunction)ose_stack_exit, METH_VARARGS, PyDoc_STR("Exit context manager")},
    {NULL, NULL},
};

/**
 * Definition of the stack type.
 */
static PyTypeObject StackType = {
    /* clang-format off */
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "ose.Stack",
    .tp_doc = "Stack object for clone()",
    .tp_basicsize = sizeof(StackObject),
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = ose_stack_new,
    .tp_init = (initproc)ose_stack_init,
    .tp_dealloc = (destructor)ose_stack_dealloc,
    .tp_methods = ose_stack_methods,
    /* clang-format on */
};

/**
 * Context structure for clone operation.
 */
typedef struct ose_clone_ctx {
    /** Callable Python function to execute in the child process after clone. */
    PyObject *func;
    /** Arguments for the Pyton function. */
    PyObject *args;
} ose_clone_ctx_t;

/**
 * Function executed in the child process after clone.
 *
 * @param arg Pointer to clone context structure.
 *
 * @return Exit status code.
 */
static int
ose_clone_child_exec_func(void *arg)
{
    ose_clone_ctx_t *ctx = (ose_clone_ctx_t *)arg;
    int ret = EXIT_SUCCESS;

    /* Clobber and reset the import lock to repair broken interpreter child */
    PyOS_AfterFork_Child();

    PyGILState_STATE gstate = PyGILState_Ensure();

    PyObject *res = PyObject_CallObject(ctx->func, ctx->args);

    if (!res) {
        PyErr_Print();
        ret = EXIT_FAILURE;
    }
    else if (!PyLong_Check(res)) {
        PyErr_SetString(PyExc_TypeError, "func must return int");
        Py_DECREF(res);
        ret = EXIT_FAILURE;
    }
    else {
        ret = (int)PyLong_AsLong(res);
        Py_DECREF(res);
    }

    PyGILState_Release(gstate);

    Py_DECREF(ctx->func);
    Py_DECREF(ctx->args);
    free(ctx);

    _exit(ret);
}

/**
 * Creates a clone of the process.
 *
 * @param module Python module object.
 * @param args Positional arguments.
 * @param kwargs Keyword arguments.
 *
 * @return Python integer with PID of child process.
 */
static PyObject *
ose_clone(PyObject *module, PyObject *args, PyObject *kwargs)
{
    const long page_size = ose_page_size();
    PyObject *callable_func = NULL;
    PyObject *callable_args = NULL;
    PyObject *clone_stack = NULL;
    int clone_flags = 0;

    pid_t clone_pid = 0;
    int clone_err = 0;
    void *stack_top = NULL;

    static char *kwlist[] = {"func", "stack", "flags", "args", NULL};

    if (!PyArg_ParseTupleAndKeywords(args,
                                     kwargs,
                                     "OO|iO",
                                     kwlist,
                                     &callable_func,
                                     &clone_stack,
                                     &clone_flags,
                                     &callable_args)) {
        return NULL;
    }

    if (!callable_func || !PyCallable_Check(callable_func)) {
        PyErr_SetString(PyExc_TypeError, "func must be callable");
        return NULL;
    }

    if (!clone_stack || !PyObject_TypeCheck(clone_stack, &StackType)) {
        PyErr_SetString(PyExc_TypeError, "stack must be a Stack object");
        return NULL;
    }
    else {
        StackObject *stack = (StackObject *)clone_stack;
        stack_top = (char *)stack->base + stack->size + page_size;
    }

    if (!callable_args || callable_args == Py_None) {
        callable_args = PyTuple_New(0);
    }
    else if (!PyTuple_Check(callable_args)) {
        PyErr_SetString(PyExc_TypeError, "args must be tuple");
        return NULL;
    }
    else {
        Py_INCREF(callable_args);
    }

    ose_clone_ctx_t *ctx = malloc(sizeof(*ctx));
    if (!ctx) {
        Py_DECREF(callable_args);
        return PyErr_NoMemory();
    }

    Py_INCREF(callable_func);

    ctx->func = callable_func;
    ctx->args = callable_args;

    /* Aquire the import lock to prepare for clone */
    PyOS_BeforeFork();

    /* Clone with SIGCHLD flag set to ensure that waitpid() works normally */
    clone_pid = clone(ose_clone_child_exec_func, stack_top, clone_flags | SIGCHLD, ctx);
    clone_err = errno;

    /* Release the import lock to fix parent after clone */
    PyOS_AfterFork_Parent();

    if (clone_pid < 0) {
        Py_DECREF(callable_func);
        Py_DECREF(callable_args);
        free(ctx);
        errno = clone_err;
        return ose_error();
    }

    return PyLong_FromPid(clone_pid);
}

/**
 * Adds clone-related constants to the module.
 *
 * @param module Python module object.
 *
 * @return 0 on success, -1 on failure.
 */
static int
ose_add_constants(PyObject *module)
{
    /* Register clone constants */
    PY_MOD_ADD_INT_CONST(module, CLONE_NEWNS);
    PY_MOD_ADD_INT_CONST(module, CLONE_NEWCGROUP);
    PY_MOD_ADD_INT_CONST(module, CLONE_NEWUTS);
    PY_MOD_ADD_INT_CONST(module, CLONE_NEWIPC);
    PY_MOD_ADD_INT_CONST(module, CLONE_NEWUSER);
    PY_MOD_ADD_INT_CONST(module, CLONE_NEWPID);
    PY_MOD_ADD_INT_CONST(module, CLONE_NEWNET);

    return 0;
}

/**
 * Initialization routine for the module.
 *
 * @param module Python module object.
 *
 * @return 0 on success, -1 on failure.
 */
static int
ose_exec(PyObject *module)
{
    /* Register error object type */
    if (PyModule_AddObjectRef(module, "error", PyExc_OSError) < 0) {
        return -1;
    }

    /* Finalize stack object type */
    if (PyType_Ready(&StackType) < 0) {
        return -1;
    }
    /* Register stack object type */
    if (PyModule_AddObjectRef(module, "Stack", (PyObject *)&StackType) < 0) {
        return -1;
    }

    return ose_add_constants(module);
}

/**
 * Module methods.
 */
static PyMethodDef ose_methods[] = {
    {"clone", (PyCFunction)ose_clone, METH_VARARGS | METH_KEYWORDS, PyDoc_STR("Create a child process")},
    {NULL, NULL},
};

/**
 * Module slots for multi-phase initialization.
 */
static PyModuleDef_Slot ose_slots[] = {
    {Py_mod_exec, ose_exec},
    {Py_mod_multiple_interpreters, Py_MOD_PER_INTERPRETER_GIL_SUPPORTED},
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
    {0, NULL},
};

/**
 * Module definition.
 */
static struct PyModuleDef ose_module = {
    PyModuleDef_HEAD_INIT,
    .m_name = "ose",
    .m_doc = ose_doc,
    .m_methods = ose_methods,
    .m_slots = ose_slots,
};

/**
 * Entry point for module initialization.
 *
 * @return Python module object.
 */
PyMODINIT_FUNC
PyInit_ose(void)
{
    return PyModuleDef_Init(&ose_module);
}
