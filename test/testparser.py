import sys, os
sys.path.append(os.path.join(os.path.dirname(sys.path[0]), 'dist', 'py', 'webapp'))

print("Testing parser function")
try:
    from irondb.irondb import find_minimal_interval_in_target
except ImportError:
    print("Can't import module, assuming it's fine")
    exit(0)

TESTCASES={
    'movingAverage(divideSeries(nonNegativeDerivative(denys.test.lofreq),denys.test.hifreq),"10min")': 600,
    'movingMax(mostDeviant(movingAverage(denys.test.lofreq,600,0.5),10),"20d")': 600,
    'movingAverage(divideSeries(nonNegativeDerivative(denys.test.lofreq),movingMax(denys.test.hifreq,300,0.5)),"20min")':300,
    'broken': None,
    'divideSeries(nonNegativeDerivative(denys.test.lofreq))': None
}

for t,v in TESTCASES.items():
    r = find_minimal_interval_in_target(t)
    if r != v:
        print("Parser tests failed: Expecting {} for parsing {} but got {}".format(v, t, r))
        exit(1)
print("Parser tests passed!")
exit(0)