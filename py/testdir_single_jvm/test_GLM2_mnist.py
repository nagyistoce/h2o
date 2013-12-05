import unittest, random, sys, time
sys.path.extend(['.','..','py'])
import h2o, h2o_cmd, h2o_hosts, h2o_browse as h2b, h2o_import as h2i, h2o_glm, h2o_util


DO_HDFS = False
DO_ALL_DIGITS = False
class Basic(unittest.TestCase):
    def tearDown(self):
        h2o.check_sandbox_for_errors()

    @classmethod
    def setUpClass(cls):
        # assume we're at 0xdata with it's hdfs namenode
        global localhost
        localhost = h2o.decide_if_localhost()
        if (localhost):
            h2o.build_cloud(1)
        else:
            # all hdfs info is done thru the hdfs_config michal's ec2 config sets up?
            h2o_hosts.build_cloud_with_hosts()

    @classmethod
    def tearDownClass(cls):
        h2o.tear_down_cloud()

    def test_GLM2_mnist(self):
        h2o.beta_features = True
        if DO_HDFS:
            importFolderPath = "mnist"
            bucket = None
            schema = 'hdfs'
        else:
            importFolderPath = "mnist"
            bucket = 'home-0xdiag-datasets'
            schema = 'local'

        csvFilelist = [
            ("mnist_training.csv.gz", "mnist_testing.csv.gz",    600), 
        ]

        trial = 0
        for (trainCsvFilename, testCsvFilename, timeoutSecs) in csvFilelist:
            trialStart = time.time()

            # PARSE test****************************************
            testKey = testCsvFilename + "_" + str(trial) + ".hex"
            csvPathname = importFolderPath + "/" + testCsvFilename
            start = time.time()

            parseResult = h2i.import_parse(bucket=bucket, path=csvPathname, schema=schema, hex_key=testKey, timeoutSecs=timeoutSecs)
            
            elapsed = time.time() - start
            print "parse end on ", testCsvFilename, 'took', elapsed, 'seconds',\
                "%d pct. of timeout" % ((elapsed*100)/timeoutSecs)
            print "parse result:", parseResult['destination_key']

            print "We won't use this pruning of x on test data. See if it prunes the same as the training"
            y = 'C0' # first column is pixel value
            print "y:"
            ignoreX = h2o_glm.goodXFromColumnInfo(y, key=parseResult['destination_key'], timeoutSecs=300, forRF=True)

            # PARSE train****************************************
            trainKey = trainCsvFilename + "_" + str(trial) + ".hex"
            csvPathname = importFolderPath + "/" + testCsvFilename
            start = time.time()
            parseResult = h2i.import_parse(bucket=bucket, path=csvPathname, schema=schema, hex_key=trainKey, timeoutSecs=timeoutSecs)
            elapsed = time.time() - start
            print "parse end on ", trainCsvFilename, 'took', elapsed, 'seconds',\
                "%d pct. of timeout" % ((elapsed*100)/timeoutSecs)
            print "parse result:", parseResult['destination_key']

            # GLM****************************************
            print "This is the pruned x we'll use"
            ignoreX = h2o_glm.goodXFromColumnInfo(y, key=parseResult['destination_key'], timeoutSecs=300, forRF=True)
            print "ignoreX:", ignoreX 

            params = {
                'ignored_cols': ignoreX, 
                'response': y,
                'case_mode': '=',
                'case_val': 0,
                'family': 'binomial',
                'lambda': 0.5,
                'alpha': 1e-4,
                'max_iter': 5,
                ## 'thresholds': 0.5,
                ## 'weight': 1.0,
                'n_folds': 1,
                'beta_epsilon': 1.0E-4,
                }

            if DO_ALL_DIGITS:
                cases = [0,1,2,3,4,5,6,7,8,9]
            else:
                cases = [8]

            for c in cases:
                kwargs = params.copy()
                print "Trying binomial with case:", c
                kwargs['case_val'] = c

                timeoutSecs = 1800
                start = time.time()
                glm = h2o_cmd.runGLM(parseResult=parseResult, timeoutSecs=timeoutSecs, pollTimeoutSecs=60, **kwargs)
                elapsed = time.time() - start
                print "GLM completed in", elapsed, "seconds.", \
                    "%d pct. of timeout" % ((elapsed*100)/timeoutSecs)

                h2o_glm.simpleCheckGLM(self, glm, None, noPrint=True, **kwargs)
                modelKey = glm['glm_model']['_selfKey']

                start = time.time()
                glmScore = h2o_cmd.runGLMScore(key=testKey, model_key=modelKey, thresholds="0.5", timeoutSecs=60)
                elapsed = time.time() - start
                print "GLMScore in",  elapsed, "secs", \
                    "%d pct. of timeout" % ((elapsed*100)/timeoutSecs)
                h2o_glm.simpleCheckGLMScore(self, glmScore, **kwargs)

if __name__ == '__main__':
    h2o.unit_main()
