from irondb import IRONdbFinder, IRONdbReader, IRONdbMeasurementFetcher
import sys

class Query():
    def __init__(self, pattern):
        self.pattern = pattern

class IRONdbClient():

    def __init__(self, url):
        self.url = url
        self.finder = IRONdbFinder({'irondb': {'url': self.url}})

    def find_metrics(self, query):
        q = Query(query)
        nodes = self.finder.find_nodes(q)
        for node in nodes:
            if node.is_leaf:
                print("Leaf node: " + node.path)
            else:
                print("Branch node: " + node.path)

    def get_data(self, metric, start, end):
        f = IRONdbMeasurementFetcher()
        f.add_leaf(metric)
        r = IRONdbReader(metric, f)
        ti, data = r.fetch(start, end)
        print("Time info: start:" + str(ti[0]) + ", end:" + str(ti[1]) + ", data: " + str(ti[2]))
        for point in data:
            print("Point: " + str(point))
        

if __name__ == "__main__":
    u = sys.argv[1]
    q = sys.argv[2]
    x = IRONdbClient(u)
    if len(sys.argv) == 3:
        print("Querying for: " + q)
        x.find_metrics(q)
    else:
        print("Getting data for: " + q)
        x.get_data(q, int(sys.argv[3]), int(sys.argv[4]))
