import sys
import flatbuffers
import pprint
import metrics.MetricSearchResultList as MetricSearchResultList
import metrics.MetricSearchResult as MetricSearchResult
import metrics.LeafData as LeafData

from irondb import IronDBFinder, IronDBReader, IronDBMeasurementFetcher

if __name__ == "__main__":
    cmd = sys.argv[1]
    filename = sys.argv[2]

    if cmd == "create_find_data":
        num_entries = int(sys.argv[3])
        leaf_cutoff = num_entries - (num_entries / 10)

        builder = flatbuffers.Builder(1024 * 1024 * 1024)
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
        for x in reversed(xrange(num_entries)):
            builder.PrependUOffsetTRelative(arr[x])
        results = builder.EndVector(num_entries)

        MetricSearchResultList.MetricSearchResultListStart(builder)
        MetricSearchResultList.MetricSearchResultListAddResults(builder, results)
        e = MetricSearchResultList.MetricSearchResultListEnd(builder)

        builder.Finish(e)
        buf = builder.Output()

        f = open(filename, 'w')
        f.write(buf)
        f.close()

        print("Wrote data to " + filename)

    elif cmd == "read_find_data":
        f = open(filename, 'r')
        buf = f.read()
        f.close()

        print("Read data from " + filename)

        array = []
        fb_buf = bytearray(buf)
        root = MetricSearchResultList.MetricSearchResultList.GetRootAsMetricSearchResultList(fb_buf, 0)
        length = root.ResultsLength()
        for x in range(0, length):
            result = root.Results(x)
            if bool(result.Leaf()) == True:
                leaf_data = result.LeafData()
                leaf_dict = {
                    u"uuid": unicode(leaf_data.Uuid(), "utf-8"),
                    u"check_name": unicode(leaf_data.CheckName(), "utf-8"),
                    u"name": unicode(leaf_data.MetricName(), "utf-8"),
                    u"category": unicode(leaf_data.Category(), "utf-8"),
                    u"egress_function": unicode(leaf_data.EgressFunction(), "utf-8"),
                }
                entry = {
                    u"leaf": bool(result.Leaf()),
                    u"name": unicode(result.Name(), "utf-8"),
                    u"leaf_data": leaf_dict,
                }
                array.append(entry)
            else:
                entry = {
                    u"leaf": bool(result.Leaf()),
                    u"name": unicode(result.Name(), "utf-8"),
                }
                array.append(entry)

        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(array)

    else:
        print("Unknown Command")
