import sys
import flatbuffers
import json
import time

def eprint(msg):
    sys.stderr.write(str(msg) + "\n")
    sys.stderr.flush()

import irondb.metrics.MetricSearchResultList as MetricSearchResultList
import irondb.metrics.MetricSearchResult as MetricSearchResult
import irondb.metrics.LeafData as LeafData
import irondb.metrics.MetricGetResult as MetricGetResult
import irondb.metrics.MetricGetSeriesData as MetricGetSeriesData
import irondb.metrics.MetricGetSeriesDataPoint as MetricGetSeriesDataPoint

GRAPHITE_RECORD_DATA_POINT_TYPE_NULL = 0
GRAPHITE_RECORD_DATA_POINT_TYPE_DOUBLE = 1

if __name__ == "__main__":
    cmd = sys.argv[1]
    filename = sys.argv[2]
    do_output = "-o" in sys.argv or "--output" in sys.argv
    use_flatcc = "-c" in sys.argv or "--flatcc" in sys.argv
    if use_flatcc:
        from irondb import flatcc as irondb_flatbuf
    else:
        #from irondb import flatbuf as irondb_flatbuf
        import irondb.flatbuf as irondb_flatbuf
    if cmd.startswith("read"):
        eprint("Using Flatbuffer module: " + irondb_flatbuf.__name__)

    if cmd == "create_find_data":
        num_entries = int(sys.argv[3])
        leaf_cutoff = num_entries - (num_entries / 10)

        builder = flatbuffers.Builder(0)
        leaf_arr = []
        for x in range(0, num_entries):
            e = None
            if x > leaf_cutoff:
                uuid = builder.CreateString("11111111-1111-1111-1111-111111111111")
                metric = builder.CreateString("dummy metric " + str(x))
                check = builder.CreateString("dummy check " + str(x))
                category = builder.CreateString("graphite")
                egress = builder.CreateString("avg")
                LeafData.LeafDataStart(builder)
                LeafData.LeafDataAddUuid(builder, uuid)
                LeafData.LeafDataAddMetricName(builder, metric)
                LeafData.LeafDataAddCheckName(builder, check)
                LeafData.LeafDataAddCategory(builder, category)
                LeafData.LeafDataAddEgressFunction(builder, egress)
                e = LeafData.LeafDataEnd(builder)
            leaf_arr.append(e)

        arr = []
        for x in range (0, num_entries):
            leaf = 0
            if x > leaf_cutoff:
                leaf = 1
            name = builder.CreateString("dummy name " + str(x))
            MetricSearchResult.MetricSearchResultStart(builder)
            MetricSearchResult.MetricSearchResultAddLeaf(builder, leaf)
            MetricSearchResult.MetricSearchResultAddName(builder, name)
            if x > leaf_cutoff:
                MetricSearchResult.MetricSearchResultAddLeafData(builder, leaf_arr[x])
            e = MetricSearchResult.MetricSearchResultEnd(builder)
            arr.append(e)

        MetricSearchResultList.MetricSearchResultListStartResultsVector(builder, num_entries)
        for x in reversed(list(range(num_entries))):
            builder.PrependUOffsetTRelative(arr[x])
        results = builder.EndVector(num_entries)

        MetricSearchResultList.MetricSearchResultListStart(builder)
        MetricSearchResultList.MetricSearchResultListAddResults(builder, results)
        e = MetricSearchResultList.MetricSearchResultListEnd(builder)

        builder.Finish(e)
        buf = builder.Output()

        f = open(filename, 'wb')
        f.write(buf)
        f.close()

        eprint("Wrote data to " + filename)

    elif cmd == "create_get_data":
        num_entries = int(sys.argv[3])

        builder = flatbuffers.Builder(0)
        dp_array = []
        for x in range(0, num_entries):
            dp_array.append([])

        for x in range(0, num_entries):
            dp_array[x] = []
            for y in range (0, 100):
                MetricGetSeriesDataPoint.MetricGetSeriesDataPointStart(builder)
                if y % 2 == 0:
                    MetricGetSeriesDataPoint.MetricGetSeriesDataPointAddType(builder, 1)
                    MetricGetSeriesDataPoint.MetricGetSeriesDataPointAddValue(builder, y)
                else:
                    MetricGetSeriesDataPoint.MetricGetSeriesDataPointAddType(builder, 0)
                    MetricGetSeriesDataPoint.MetricGetSeriesDataPointAddValue(builder, 0)
                e = MetricGetSeriesDataPoint.MetricGetSeriesDataPointEnd(builder)
                dp_array[x].append(e)

        built_datapoints_array = []
        for x in reversed(list(range(num_entries))):
            MetricGetSeriesData.MetricGetSeriesDataStartDataVector(builder, 100)
            for y in reversed(list(range(100))):
                builder.PrependUOffsetTRelative(dp_array[x][y])
            seriesdata = builder.EndVector(100)
            built_datapoints_array.append(seriesdata)

        data_arr = []
        for x in range(0, num_entries):
            name = builder.CreateString("dummy name " + str(x))
            MetricGetSeriesData.MetricGetSeriesDataStart(builder)
            MetricGetSeriesData.MetricGetSeriesDataAddName(builder, name)
            MetricGetSeriesData.MetricGetSeriesDataAddData(builder, built_datapoints_array[x])
            e = MetricGetSeriesData.MetricGetSeriesDataEnd(builder)
            data_arr.append(e)

        MetricGetResult.MetricGetResultStartSeriesVector(builder, num_entries)
        for x in reversed(list(range(num_entries))):
            builder.PrependUOffsetTRelative(data_arr[x])
        series = builder.EndVector(num_entries)

        MetricGetResult.MetricGetResultStart(builder)
        MetricGetResult.MetricGetResultAddFromTime(builder, 1000)
        MetricGetResult.MetricGetResultAddToTime(builder, 10000)
        MetricGetResult.MetricGetResultAddStep(builder, 10)
        MetricGetResult.MetricGetResultAddSeries(builder, series)
        e = MetricGetResult.MetricGetResultEnd(builder)

        builder.Finish(e)
        buf = builder.Output()

        f = open(filename, 'wb')
        f.write(buf)
        f.close()

        eprint("Wrote data to " + filename)

    elif cmd == "read_find_data":
        f = open(filename, 'rb')
        buf = f.read()
        f.close()

        eprint("Read data from " + filename)

        start_time = time.time()
        array = irondb_flatbuf.metric_find_results(buf)
        end_time = time.time()
        total_time = end_time - start_time

        if array:
            eprint("Total Entries Read: " + str(len(array)))
            eprint("Total Seconds To Run: " + str(total_time))
            eprint("Entries Per Second: " + str(len(array) / total_time))
            if do_output:
                print((json.dumps(array, indent=4, sort_keys=True)))
        else:
            eprint("Failed to parse find data from " + filename)

    elif cmd == "read_get_data":
        f = open(filename, 'rb')
        buf = f.read()
        f.close()

        eprint("Read data from " + filename)

        start_time = time.time()
        datadict = irondb_flatbuf.metric_get_results(buf)
        end_time = time.time()
        total_time = end_time - start_time

        if datadict:
            eprint("Total Entries Read: " + str(len(datadict["series"])))
            eprint("Total Seconds To Run: " + str(total_time))
            eprint("Entries Per Second: " + str(len(datadict["series"]) / total_time))
            if do_output:
                print((json.dumps(datadict, indent=4, sort_keys=True)))
        else:
            eprint("Failed to parse get data from " + filename)

    else:
        eprint("Unknown Command: " + cmd)
        exit(1)
    eprint("")
