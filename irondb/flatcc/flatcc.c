#include "Python.h"

#include "metric_find_verifier.h"
#include "metric_find_reader.h"
#include "metric_get_verifier.h"
#include "metric_get_reader.h"

#include <math.h>

#define metrics_ns(x) FLATBUFFERS_WRAP_NAMESPACE(metrics, x)
#define GRAPHITE_RECORD_DATA_POINT_TYPE_NULL    0
#define GRAPHITE_RECORD_DATA_POINT_TYPE_DOUBLE  1

#define _FB_METRIC(m, ns, s)                    metrics_ns(ns##_##s(m))
#define SET_METRIC_BOOL(d, m, ns, s)            _pydict_set(d, #s, PyBool_FromLong(_FB_METRIC(m, ns, s)))
#define SET_METRIC_LONG_ALT(d, alt_s, m, ns, s) _pydict_set(d, #alt_s, PyLong_FromLong(_FB_METRIC(m, ns, s)))
#define SET_METRIC_LONG(d, m, ns, s)            SET_METRIC_LONG_ALT(d, s, m, ns, s)
#define SET_METRIC_STR_ALT(d, alt_s, m, ns, s)  _pydict_set(d, #alt_s, PyUnicode_FromString(_FB_METRIC(m, ns, s)))
#define SET_METRIC_STR(d, m, ns, s)             SET_METRIC_STR_ALT(d, s, m, ns, s)

static void _pydict_set(PyObject *dict, const char *strkey, PyObject *pyval) {
    PyObject *pykey = PyUnicode_FromString(strkey);
    PyDict_SetItem(dict, pykey, pyval);
    Py_DECREF(pykey);
    Py_DECREF(pyval);
}

struct flatcc_modstate {
    PyObject *error_type;
};

#if PY_MAJOR_VERSION >= 3
#define GETSTATE(m) ((struct flatcc_modstate*)PyModule_GetState(m))
#else
#define GETSTATE(m) (&_state)
static struct flatcc_modstate _state;
#endif

static PyObject * flatcc_metric_find_results(PyObject *m, PyObject *args) {
    struct flatcc_modstate *st = GETSTATE(m);
    char *buffer;
    int buffer_len;
    if (!PyArg_ParseTuple(args, "s#", &buffer, &buffer_len))
        return NULL;
    // TODO FIXME
    // Copy data for memory alignment for flatcc
    // Python data is not memory aligned!
    char *aligned_buffer = (char *)malloc(buffer_len);
    memcpy(aligned_buffer, buffer, buffer_len);

    int ret = metrics_ns(MetricSearchResultList_verify_as_root(aligned_buffer, buffer_len));
    if (ret != 0) {
        free(aligned_buffer);
        return PyErr_Format(st->error_type,
            "Failed to verify MetricSearchResultList: %s",
            flatcc_verify_error_string(ret));
    }

    metrics_ns(MetricSearchResultList_table_t) metric_list = metrics_ns(MetricSearchResultList_as_root(aligned_buffer));
    metrics_ns(MetricSearchResult_vec_t) vec = metrics_ns(MetricSearchResultList_results(metric_list));
    size_t num_results = metrics_ns(MetricSearchResult_vec_len(vec));

    PyObject *array = PyList_New(num_results);
    for (size_t i = 0; i < num_results; i++) {
        metrics_ns(MetricSearchResult_table_t) m = metrics_ns(MetricSearchResult_vec_at(vec, i));
        PyObject *entry = PyDict_New();
        SET_METRIC_STR(entry, m, MetricSearchResult, name);
        SET_METRIC_BOOL(entry, m, MetricSearchResult, leaf);

        if (metrics_ns(MetricSearchResult_leaf(m)) && metrics_ns(MetricSearchResult_leaf_data_is_present(m))) {
            metrics_ns(LeafData_table_t) ld = metrics_ns(MetricSearchResult_leaf_data(m));
            PyObject *leaf_dict = PyDict_New();

            SET_METRIC_STR(leaf_dict, ld, LeafData, uuid);
            SET_METRIC_STR(leaf_dict, ld, LeafData, check_name);
            SET_METRIC_STR_ALT(leaf_dict, name, ld, LeafData, metric_name);
            SET_METRIC_STR(leaf_dict, ld, LeafData, category);
            SET_METRIC_STR(leaf_dict, ld, LeafData, egress_function);

            _pydict_set(entry, "leaf_data", leaf_dict);
        }
        PyList_SET_ITEM(array, i, entry);
    }
    free(aligned_buffer);
    return array;
}

static PyObject * flatcc_metric_get_results(PyObject *m, PyObject *args) {
    struct flatcc_modstate *st = GETSTATE(m);
    char *buffer;
    int buffer_len;
    if (!PyArg_ParseTuple(args, "s#", &buffer, &buffer_len))
        return NULL;
    // TODO FIXME
    // Copy data for memory alignment for flatcc
    // Python data is not memory aligned!
    char *aligned_buffer = (char *)malloc(buffer_len);
    memcpy(aligned_buffer, buffer, buffer_len);

    int ret = metrics_ns(MetricGetResult_verify_as_root(aligned_buffer, buffer_len));
    if (ret != 0) {
        free(aligned_buffer);
        return PyErr_Format(st->error_type,
            "Failed to verify MetricGetResult: %s",
            flatcc_verify_error_string(ret));
    }

    metrics_ns(MetricGetResult_table_t) metric_data = metrics_ns(MetricGetResult_as_root(aligned_buffer));
    PyObject *return_dict = PyDict_New();
    PyObject *names_dict = PyDict_New();

    SET_METRIC_LONG_ALT(return_dict, from, metric_data, MetricGetResult, from_time);
    SET_METRIC_LONG_ALT(return_dict, to, metric_data, MetricGetResult, to_time);
    SET_METRIC_LONG(return_dict, metric_data, MetricGetResult, step);

    metrics_ns(MetricGetSeriesData_vec_t) series_data_vec = metrics_ns(MetricGetResult_series(metric_data));
    size_t series_data_len = metrics_ns(MetricGetSeriesData_vec_len(series_data_vec));

    for (size_t i = 0; i < series_data_len; i++) {
        metrics_ns(MetricGetSeriesData_table_t) entry = metrics_ns(MetricGetSeriesData_vec_at(series_data_vec, i));
        metrics_ns(MetricGetSeriesDataPoint_vec_t) datapoint_vec = metrics_ns(MetricGetSeriesData_data(entry));
        size_t datapoint_len = metrics_ns(MetricGetSeriesDataPoint_vec_len(datapoint_vec));
        const char *name = metrics_ns(MetricGetSeriesData_name(entry));
        PyObject *data_array = PyList_New(datapoint_len);

        for (size_t j = 0; j < datapoint_len; j++) {
            metrics_ns(MetricGetSeriesDataPoint_table_t) datapoint = metrics_ns(MetricGetSeriesDataPoint_vec_at(datapoint_vec, j));
            int datatype = metrics_ns(MetricGetSeriesDataPoint_type(datapoint));
            PyObject *py_datapoint;

            if (datatype == GRAPHITE_RECORD_DATA_POINT_TYPE_NULL) {
                Py_INCREF(Py_None);
                py_datapoint = Py_None;
            }
            else if (datatype == GRAPHITE_RECORD_DATA_POINT_TYPE_DOUBLE) {
                double x = metrics_ns(MetricGetSeriesDataPoint_value(datapoint));
                /* 5 sigdigs */
                x = roundf(x * 10000) / 10000;
                py_datapoint = PyFloat_FromDouble(x);
            }
            else {
                // TODO FIXME
                Py_INCREF(Py_None);
                py_datapoint = Py_None;
            }
            PyList_SET_ITEM(data_array, j, py_datapoint);
        }
        _pydict_set(names_dict, name, data_array);
    }
    _pydict_set(return_dict, "series", names_dict);

    free(aligned_buffer);
    return return_dict;
}

static PyMethodDef flatcc_methods[] = {
    { "metric_find_results", flatcc_metric_find_results, METH_VARARGS, NULL },
    { "metric_get_results",  flatcc_metric_get_results,  METH_VARARGS, NULL },
    { NULL, NULL }
};

#if PY_MAJOR_VERSION >= 3

static int flatcc_traverse(PyObject *m, visitproc visit, void *arg) {
    Py_VISIT(GETSTATE(m)->error_type);
    return 0;
}

static int flatcc_clear(PyObject *m) {
    Py_CLEAR(GETSTATE(m)->error_type);
    return 0;
}


static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "flatcc",
    NULL,
    sizeof(struct flatcc_modstate),
    flatcc_methods,
    NULL,
    flatcc_traverse,
    flatcc_clear,
    NULL
};

#define INITERROR return NULL

PyMODINIT_FUNC
PyInit_flatcc(void)

#else
#define INITERROR return

void
initflatcc(void)
#endif
{
#if PY_MAJOR_VERSION >= 3
    PyObject *module = PyModule_Create(&moduledef);
#else
    PyObject *module = Py_InitModule("flatcc", flatcc_methods);
#endif

    if (module == NULL)
        INITERROR;
    struct flatcc_modstate *st = GETSTATE(module);

    st->error_type = PyErr_NewException("flatcc.Error", NULL, NULL);
    if (st->error_type == NULL) {
        Py_DECREF(module);
        INITERROR;
    }

#if PY_MAJOR_VERSION >= 3
    return module;
#endif
}

