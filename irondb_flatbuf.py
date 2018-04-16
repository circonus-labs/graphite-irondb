import flatbuffers

from metrics.MetricSearchResultList import MetricSearchResultList
from metrics.MetricGetResult import MetricGetResult

try:
    from graphite.logger import log
except django.core.exceptions.ImproperlyConfigured:
    print "No graphite logger"

#record types used by irondb in flatbuffer data
#to determine data type
GRAPHITE_RECORD_DATA_POINT_TYPE_NULL = 0
GRAPHITE_RECORD_DATA_POINT_TYPE_DOUBLE = 1

def convert_flatbuffer_metric_find_results(content):
    try:
        array = []
        fb_buf = bytearray(content)
        root = MetricSearchResultList.GetRootAsMetricSearchResultList(fb_buf, 0)
        length = root.ResultsLength()
        for x in range(0, length):
            result = root.Results(x)
            entry = {}
            entry[u"leaf"] = bool(result.Leaf())
            entry[u"name"] = unicode(result.Name(), "utf-8")
            if entry[u"leaf"] == True:
              leaf_dict = {}
              leaf_data = result.LeafData()
              leaf_dict[u"uuid"] = unicode(leaf_data.Uuid(), "utf-8")
              leaf_dict[u"check_name"] = unicode(leaf_data.CheckName(), "utf-8")
              leaf_dict[u"name"] = unicode(leaf_data.MetricName(), "utf-8")
              leaf_dict[u"category"] = unicode(leaf_data.Category(), "utf-8")
              leaf_dict[u"egress_function"] = unicode(leaf_data.EgressFunction(), "utf-8")
              entry[u"leaf_data"] = leaf_dict
            array.append(entry)
        return array
    except Exception as e:
        log.info(e)
    return None

def convert_flatbuffer_metric_get_results(content):
    try:
        return_dict = {}
        fb_buf = bytearray(content)
        root = MetricGetResult.GetRootAsMetricGetResult(fb_buf, 0)
        return_dict[u"from"] = root.FromTime()
        return_dict[u"to"] = root.ToTime()
        return_dict[u"step"] = root.Step()
        length = root.SeriesLength()
        names_dict = {}
        for x in range(0, length):
            series = root.Series(x)
            entry = {}
            name = unicode(series.Name(), "utf-8")
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
        return_dict[u"series"] = names_dict
        return return_dict
    except Exception as e:
        log.info(e)
    return None
