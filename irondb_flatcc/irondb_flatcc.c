#include "Python.h"

#include "metric_find_verifier.h"
#include "metric_find_reader.h"
#include "metric_get_verifier.h"
#include "metric_get_reader.h"

#define metrics_ns(x) FLATBUFFERS_WRAP_NAMESPACE(metrics, x)
#define GRAPHITE_RECORD_DATA_POINT_TYPE_NULL    0
#define GRAPHITE_RECORD_DATA_POINT_TYPE_DOUBLE  1

#define SET_METRIC_STR(d, m, ns, s) PyDict_SetItem(d, PyUnicode_FromString(#s), PyUnicode_FromString(metrics_ns(ns##_##s(m))))

struct irondb_flatcc_modstate {
    PyObject *error_type;
};

#if PY_MAJOR_VERSION >= 3
#define GETSTATE(m) ((struct irondb_flatcc_modstate*)PyModule_GetState(m))
#else
#define GETSTATE(m) (&_state)
static struct irondb_flatcc_modstate _state;
#endif

static PyObject * metric_find_results(PyObject *m, PyObject *args) {
    struct irondb_flatcc_modstate *st = GETSTATE(m);
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
    free(aligned_buffer);
    return array;
}

static PyObject * metric_get_results(PyObject *m, PyObject *args) {
    struct irondb_flatcc_modstate *st = GETSTATE(m);
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
        return PyErr_Format(st->error_type,
            "Failed to verify MetricGetResult: %s",
            flatcc_verify_error_string(ret));
    }

    metrics_ns(MetricGetResult_table_t) metric_data = metrics_ns(MetricGetResult_as_root(aligned_buffer));
    PyObject *return_dict = PyDict_New();
    PyObject *names_dict = PyDict_New();

    PyDict_SetItem(return_dict, PyUnicode_FromString("from"),
        PyLong_FromLong(metrics_ns(MetricGetResult_from_time(metric_data))));
    PyDict_SetItem(return_dict, PyUnicode_FromString("to"),
        PyLong_FromLong(metrics_ns(MetricGetResult_to_time(metric_data))));
    PyDict_SetItem(return_dict, PyUnicode_FromString("step"),
        PyLong_FromLong(metrics_ns(MetricGetResult_step(metric_data))));

    metrics_ns(MetricGetSeriesData_vec_t) series_data_vec = metrics_ns(MetricGetResult_series(metric_data));
    size_t series_data_len = metrics_ns(MetricGetSeriesData_vec_len(series_data_vec));

    for (size_t i = 0; i < series_data_len; i++) {
        metrics_ns(MetricGetSeriesData_table_t) entry = metrics_ns(MetricGetSeriesData_vec_at(series_data_vec, i));
        metrics_ns(MetricGetSeriesDataPoint_vec_t) datapoint_vec = metrics_ns(MetricGetSeriesData_data(entry));
        size_t datapoint_len = metrics_ns(MetricGetSeriesDataPoint_vec_len(datapoint_vec));
        PyObject *name = PyUnicode_FromString(metrics_ns(MetricGetSeriesData_name(entry)));
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
                py_datapoint = PyFloat_FromDouble(metrics_ns(MetricGetSeriesDataPoint_value(datapoint)));
            }
            else {
                // TODO FIXME
                Py_INCREF(Py_None);
                py_datapoint = Py_None;
            }
            PyList_SET_ITEM(data_array, j, py_datapoint);
        }
        PyDict_SetItem(names_dict, name, data_array);
    }
    PyDict_SetItem(return_dict, PyUnicode_FromString("series"), names_dict);

    free(aligned_buffer);
    return return_dict;
}

static PyMethodDef irondb_flatcc_methods[] = {
    { "metric_find_results", metric_find_results, METH_VARARGS, NULL },
    { "metric_get_results",  metric_get_results,  METH_VARARGS, NULL },
    { NULL, NULL }
};

#if PY_MAJOR_VERSION >= 3

static int irondb_flatcc_traverse(PyObject *m, visitproc visit, void *arg) {
    Py_VISIT(GETSTATE(m)->error_type);
    return 0;
}

static int irondb_flatcc_clear(PyObject *m) {
    Py_CLEAR(GETSTATE(m)->error_type);
    return 0;
}


static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "irondb_flatcc",
    NULL,
    sizeof(struct irondb_flatcc_modstate),
    irondb_flatcc_methods,
    NULL,
    irondb_flatcc_traverse,
    irondb_flatcc_clear,
    NULL
};

#define INITERROR return NULL

PyMODINIT_FUNC
PyInit_irondb_flatcc(void)

#else
#define INITERROR return

void
initirondb_flatcc(void)
#endif
{
#if PY_MAJOR_VERSION >= 3
    PyObject *module = PyModule_Create(&moduledef);
#else
    PyObject *module = Py_InitModule("irondb_flatcc", irondb_flatcc_methods);
#endif

    if (module == NULL)
        INITERROR;
    struct irondb_flatcc_modstate *st = GETSTATE(module);

    st->error_type = PyErr_NewException("irondb_flatcc.Error", NULL, NULL);
    if (st->error_type == NULL) {
        Py_DECREF(module);
        INITERROR;
    }

#if PY_MAJOR_VERSION >= 3
    return module;
#endif
}

