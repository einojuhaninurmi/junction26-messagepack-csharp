"""Contract tests for missing checks, contradictions and actual collection provenance."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent/'collector'))
from run_contract import parse_probe, compare_probe, parse_trx, load_run
ROOT=Path(__file__).resolve().parent
MANIFEST=json.loads((ROOT/'collector/checks.json').read_text())

class CollectorTests(unittest.TestCase):
    def setUp(self):
        reports=[load_run(p) for p in (ROOT/'runs').glob('*/report.json')]
        self.good=next(r for r in reports if r['status']=='reproduced')
        self.blocked=next(r for r in reports if r['status']=='environment_blocked')
        self.folder=ROOT/'runs'/self.good['runId']

    def test_real_run_same_inputs_and_exact_tests(self):
        r=self.good
        self.assertTrue(r['inputs']['identicalAcrossVersions'])
        self.assertEqual(r['versions']['base']['inputHashes'],r['versions']['head']['inputHashes'])
        for side in ('base','head'):
            tests=parse_trx(self.folder/side/'results/targeted.trx',MANIFEST['tests'])
            self.assertEqual(len(tests),3)

    def test_two_real_runs_repeat_the_same_observations(self):
        successful=[load_run(p) for p in (ROOT/'runs').glob('*/report.json') if load_run(p)['status']=='reproduced']
        self.assertGreaterEqual(len(successful),2)
        first,second=successful[:2]
        self.assertNotEqual(first['runId'],second['runId'])
        for side in ('base','head'):
            first_checks=copy.deepcopy(first['versions'][side]['checks'])
            second_checks=copy.deepcopy(second['versions'][side]['checks'])
            # xUnit/TRX enumeration order is not an observation; identities and outcomes are.
            for checks in (first_checks,second_checks):
                checks['metadata-regressions-v1']['tests'].sort(key=lambda test:test['name'])
            self.assertEqual(first_checks,second_checks)
            self.assertEqual(first['versions'][side]['inputHashes'],second['versions'][side]['inputHashes'])
            self.assertEqual(first['versions'][side]['tools']['compiler'],second['versions'][side]['tools']['compiler'])

    def test_failure_is_not_a_pass(self):
        self.assertEqual(self.blocked['status'],'environment_blocked')
        for v in self.blocked['versions'].values():
            self.assertTrue(all(c['status']=='not_run' for c in v['checks'].values()))
        failures=[c for c in self.blocked['commands'] if c['status']=='environment_blocked']
        self.assertTrue(failures)
        self.assertTrue(all(c['exitCode'] is None for c in failures))

    def test_missing_probe_case_is_rejected(self):
        with self.assertRaises(ValueError):parse_probe('CASE referenced-library\nEMIT True\n',MANIFEST['probeCases'])

    def test_missing_executed_test_is_rejected(self):
        with self.assertRaises(ValueError):parse_trx(self.folder/'head/results/targeted.trx',MANIFEST['tests']+['Missing.Test'])

    def test_skipped_test_is_not_a_pass(self):
        text=(self.folder/'head/results/targeted.trx').read_text().replace('outcome="Passed"','outcome="NotExecuted"',1)
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'test.trx';p.write_text(text)
            with self.assertRaises(ValueError):parse_trx(p,MANIFEST['tests'])

    def test_non_reproducing_finding_is_explicit(self):
        cases=copy.deepcopy(self.good['versions']['head']['checks']['diagnostic-probe-v1']['cases'])
        cases['source-null-key-positional-record']['diagnostics']=['MsgPack005']
        comparisons=compare_probe(cases,'head')
        difference=next(c for c in comparisons if c['id']=='source-null-key-positional-record')
        self.assertFalse(difference['matches'])
        self.assertEqual(difference['actual']['diagnostics'],['MsgPack005'])
        self.assertEqual(difference['expected']['diagnostics'],[])

if __name__=='__main__':unittest.main(verbosity=2)
