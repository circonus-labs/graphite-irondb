#include "Python.h"

#include "metric_find_verifier.h"
#include "metric_find_reader.h"
#define metrics_ns(x) FLATBUFFERS_WRAP_NAMESPACE(metrics, x)
#define SET_METRIC_STR(d, m, ns, s) PyDict_SetItem(d, PyUnicode_FromString(#s), PyUnicode_FromString(metrics_ns(ns##_##s(m))))

struct irondb_flatbuf_modstate {
    PyObject *error_type;
};

#if PY_MAJOR_VERSION >= 3
#define GETSTATE(m) ((struct irondb_flatbuf_modstate*)PyModule_GetState(m))
#else
#define GETSTATE(m) (&_state)
static struct irondb_flatbuf_modstate _state;
#endif

static PyObject * metric_find_results(PyObject *m, PyObject *args) {
    struct irondb_flatbuf_modstate *st = GETSTATE(m);
    PyObject *content;
    Py_buffer buffer;
    if (!PyArg_ParseTuple(args, "O", &content))
        return NULL;
    if (PyObject_GetBuffer(content, &buffer, PyBUF_SIMPLE) != 0)
        return NULL;

    int ret = metrics_ns(MetricSearchResultList_verify_as_root(buffer.buf, buffer.len));
    if (ret != 0) {
        return PyErr_Format(st->error_type,
            "Failed to verify MetricSearchResultList: %s",
            flatcc_verify_error_string(ret));
    }

    metrics_ns(MetricSearchResultList_table_t) metric_list = metrics_ns(MetricSearchResultList_as_root(buffer.buf));
    metrics_ns(MetricSearchResult_vec_t) vec = metrics_ns(MetricSearchResultList_results(metric_list));
    size_t num_results = metrics_ns(MetricSearchResult_vec_len(vec));

    PyObject *array = PyList_New(num_results);
    for (size_t i = 0; i < num_results; i++) {
        metrics_ns(MetricSearchResult_table_t) m = metrics_ns(MetricSearchResult_vec_at(vec, i));
        PyObject *entry = PyDict_New();
        SET_METRIC_STR(entry, m, MetricSearchResult, name);

        int leaf = metrics_ns(MetricSearchResult_leaf(m));
        PyDict_SetItem(entry, PyUnicode_FromString("leaf"), PyBool_FromLong(leaf));

        if (leaf && metrics_ns(MetricSearchResult_leaf_data_is_present(m))) {
            metrics_ns(LeafData_table_t) ld = metrics_ns(MetricSearchResult_leaf_data(m));
            PyObject *leaf_dict = PyDict_New();

            SET_METRIC_STR(leaf_dict, ld, LeafData, uuid);
            SET_METRIC_STR(leaf_dict, ld, LeafData, check_name);
            PyDict_SetItem(leaf_dict, PyUnicode_FromString("name"),
                PyUnicode_FromString(metrics_ns(LeafData_metric_name(ld))));
            SET_METRIC_STR(leaf_dict, ld, LeafData, category);
            SET_METRIC_STR(leaf_dict, ld, LeafData, egress_function);

            PyDict_SetItem(entry, PyUnicode_FromString("leaf_data"), leaf_dict);
        }
        PyList_SET_ITEM(array, i, entry);
    }
    PyBuffer_Release(&buffer);
    return array;
}

static PyMethodDef irondb_flatbuf_methods[] = {
    { "metric_find_results", metric_find_results, METH_VARARGS, NULL },
    { NULL, NULL }
};

#if PY_MAJOR_VERSION >= 3

static int irondb_flatbuf_traverse(PyObject *m, visitproc visit, void *arg) {
    Py_VISIT(GETSTATE(m)->error_type);
    return 0;
}

static int irondb_flatbuf_clear(PyObject *m) {
    Py_CLEAR(GETSTATE(m)->error_type);
    return 0;
}


static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "irondb_flatbuf",
    NULL,
    sizeof(struct irondb_flatbuf_modstate),
    irondb_flatbuf_methods,
    NULL,
    irondb_flatbuf_traverse,
    irondb_flatbuf_clear,
    NULL
};

#define INITERROR return NULL

PyMODINIT_FUNC
PyInit_irondb_flatbuf(void)

#else
#define INITERROR return

void
initirondb_flatbuf(void)
#endif
{
#if PY_MAJOR_VERSION >= 3
    PyObject *module = PyModule_Create(&moduledef);
#else
    PyObject *module = Py_InitModule("irondb_flatbuf", irondb_flatbuf_methods);
#endif

    if (module == NULL)
        INITERROR;
    struct irondb_flatbuf_modstate *st = GETSTATE(module);

    st->error_type = PyErr_NewException("irondb_flatbuf.Error", NULL, NULL);
    if (st->error_type == NULL) {
        Py_DECREF(module);
        INITERROR;
    }

#if PY_MAJOR_VERSION >= 3
    return module;
#endif
}

