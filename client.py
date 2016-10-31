from irondb import IronDBFinder, IronDBReader
import sys

class Query():
    def __init__(self, pattern):
        self.pattern = pattern

class IronDBClient():

    def __init__(self):
        self.finder = IronDBFinder({'irondb': {'url': 'http://rberton.dev.circonus.net:8112/graphite/29FB4AAC-189D-4460-9E09-559232663773'}})

    def find_metrics(self, query):
        q = Query(query);
        nodes = self.finder.find_nodes(q)
        for node in nodes:
            if node.is_leaf:
                print "Leaf node: " + node.path
            else:
                print "Branch node: " + node.path

    def get_data(self, metric, start, end):
        r = IronDBReader(metric)
        ti, data = r.fetch(start, end)
        print "Time info: start:" + str(ti[0]) + ", end:" + str(ti[1]) + ", data: " + str(ti[2])
        for point in data:
            print "Point: " + str(point)
        

if __name__ == "__main__":
    x = IronDBClient()
    q = sys.argv[1]
    if len(sys.argv) == 2:
        print "Querying for: " + q
        x.find_metrics(q)
    else:
        print "Getting data for: " + q
        x.get_data(q, int(sys.argv[2]), int(sys.argv[3]))
