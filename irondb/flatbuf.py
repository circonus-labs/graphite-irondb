import flatbuffers

from metrics.MetricSearchResultList import MetricSearchResultList
from metrics.MetricGetResult import MetricGetResult

try:
    from django.core.exceptions import ImproperlyConfigured
except ImportError:
    ImproperlyConfigured = ImportError

try:
    from graphite.logger import log
except ImproperlyConfigured:
    class Log(object):
        def info(self, msg):
            print(msg)
    log = Log()

#record types used by irondb in flatbuffer data
#to determine data type
GRAPHITE_RECORD_DATA_POINT_TYPE_NULL = 0
GRAPHITE_RECORD_DATA_POINT_TYPE_DOUBLE = 1

def metric_find_results(content):
    try:
        array = []
        fb_buf = bytearray(content)
        root = MetricSearchResultList.GetRootAsMetricSearchResultList(fb_buf, 0)
        length = root.ResultsLength()
        for x in range(0, length):
            result = root.Results(x)
            entry = {}
            entry["leaf"] = bool(result.Leaf())
            entry["name"] = result.Name()
            if entry["leaf"] == True:
              leaf_dict = {}
              leaf_data = result.LeafData()
              leaf_dict["uuid"] = leaf_data.Uuid()
              leaf_dict["check_name"] = leaf_data.CheckName()
              leaf_dict["name"] = leaf_data.MetricName()
              leaf_dict["category"] = leaf_data.Category()
              leaf_dict["egress_function"] = leaf_data.EgressFunction()
              entry["leaf_data"] = leaf_dict
            array.append(entry)
        return array
    except Exception as e:
        log.info(e)
    return None

def metric_get_results(content):
    try:
        return_dict = {}
        fb_buf = bytearray(content)
        root = MetricGetResult.GetRootAsMetricGetResult(fb_buf, 0)
        return_dict["from"] = root.FromTime()
        return_dict["to"] = root.ToTime()
        return_dict["step"] = root.Step()
        length = root.SeriesLength()
        names_dict = {}
        for x in range(0, length):
            series = root.Series(x)
            entry = {}
            name = series.Name()
            data_length = series.DataLength()
            data_array = []
            for y in range(0, data_length):
                datapoint = series.Data(y)
                datatype = datapoint.Type()
                if datatype == GRAPHITE_RECORD_DATA_POINT_TYPE_NULL:
                    data_array.append(None)
                elif datatype == GRAPHITE_RECORD_DATA_POINT_TYPE_DOUBLE:
                    data_array.append(datapoint.Value())
                else:
                    data_array.append(None)
            names_dict[name] = data_array
        return_dict["series"] = names_dict
        return return_dict
    except Exception as e:
        log.info(e)
    return None
