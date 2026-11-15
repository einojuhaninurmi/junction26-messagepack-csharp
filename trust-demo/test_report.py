"""Dependency-free report validation checks: python3 trust-demo/test_report.py."""
import copy
import json
import unittest
from server import ROOT, load_report, validate

class ReportTests(unittest.TestCase):
    def setUp(self):
        self.report = load_report()
        self.schema = json.loads((ROOT / 'report.schema.json').read_text())

    def test_report_and_references(self):
        self.assertEqual(len(self.report['criteria']), 4)
        self.assertEqual(self.report['reviewVersion'], '2283-review-1')

    def test_required_field(self):
        del self.report['change']['head']
        with self.assertRaises(ValueError): validate(self.report, self.schema)

    def test_sha_format(self):
        self.report['change']['base'] = 'master'
        with self.assertRaises(ValueError): validate(self.report, self.schema)

    def test_wrong_type(self):
        self.report['criteria'] = 'all pass'
        with self.assertRaises(ValueError): validate(self.report, self.schema)

    def test_unknown_field(self):
        self.report['trustPercentage'] = 100
        with self.assertRaises(ValueError): validate(self.report, self.schema)

if __name__ == '__main__': unittest.main(verbosity=2)
