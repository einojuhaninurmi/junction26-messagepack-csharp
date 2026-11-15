"""Issue-specific parsing and validation; absence never counts as a pass."""
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

STATES = {'passed', 'test_failed', 'observed', 'environment_blocked', 'not_run'}

def parse_trx(path, expected):
    root = ET.parse(path).getroot()
    ns = {'t':'http://microsoft.com/schemas/VisualStudio/TeamTest/2010'}
    methods = {}
    for test in root.findall('.//t:UnitTest', ns):
        method = test.find('t:TestMethod', ns)
        if method is not None:
            methods[test.attrib['id']] = method.attrib['className'].split(',')[0] + '.' + method.attrib['name']
    actual = []
    for result in root.findall('.//t:UnitTestResult', ns):
        actual.append({'name':methods.get(result.attrib['testId'], result.attrib.get('testName')), 'outcome':result.attrib['outcome']})
    names = [x['name'] for x in actual]
    if sorted(names) != sorted(expected) or any(x['outcome'] not in ('Passed','Failed') for x in actual):
        raise ValueError(f'Expected exactly these executed tests: {expected}; actual: {actual}')
    return actual

def parse_probe(text, expected):
    cases = {}
    current = None
    for line in text.splitlines():
        if line.startswith('CASE '):
            current = line[5:]
            if current in cases: raise ValueError('Duplicate probe case')
            cases[current] = {'diagnostics':[], 'exceptions':[], 'generated':[], 'emit':None}
        elif current:
            item = cases[current]
            if re.match(r'^(AD\d+|CS\d+|MsgPack\d+):', line): item['diagnostics'].append(line.split(':')[0])
            for name in ('IndexOutOfRangeException', 'InvalidCastException'):
                if name in line and name not in item['exceptions']: item['exceptions'].append(name)
            if line.startswith('GENERATED '): item['generated'].append(line[10:])
            if line.startswith('EMIT '):
                if item['emit'] is not None: raise ValueError('Duplicate emit result')
                if line[5:] not in ('True','False'): raise ValueError('Invalid emit result')
                item['emit'] = line[5:] == 'True'
    if set(cases) != set(expected) or any(c['emit'] is None for c in cases.values()):
        raise ValueError('Probe cases are missing or incomplete')
    return cases

def compare_probe(cases, side):
    expected = {
        'referenced-library':([],[],True),
        'issue-repro-with-implicit-resolver':(['AD0001','CS8785'],['IndexOutOfRangeException'],False) if side == 'base' else ([],[],True),
        'source-unkeyed-control':(['MsgPack004'],[],True),
        'source-null-key-property':(['MsgPack005'],[],True),
        'source-null-key-positional-record':(['AD0001'],['InvalidCastException'],True) if side == 'base' else ([],[],True),
    }
    comparisons = []
    for name, (diagnostics, exceptions, resolver) in expected.items():
        actual = cases[name]
        want = dict(diagnostics=diagnostics, exceptions=exceptions, resolver=resolver, emit=True)
        got = dict(diagnostics=sorted(set(actual['diagnostics'])), exceptions=sorted(actual['exceptions']), resolver='MessagePack.GeneratedMessagePackResolver.g.cs' in actual['generated'], emit=actual['emit'])
        comparisons.append(dict(id=name, expected=want, actual=got, matches=got == want))
    return comparisons

def _validate_run(r):
    for key in ('schemaVersion','kind','runId','startedAt','finishedAt','base','head','reviewVersion','parentReviewVersion','checkVersion','status','commands','versions','artifacts','contradictions','inputs'):
        if key not in r: raise ValueError(f'Missing run field: {key}')
    if r['schemaVersion'] != 1 or r['kind'] != 'issue-2283-evidence-run': raise ValueError('Unknown run schema')
    if not re.fullmatch(r'[0-9TZ-]+-[0-9a-f]{8}', r['runId']): raise ValueError('Invalid run ID')
    for key in ('base','head'):
        if not re.fullmatch('[0-9a-f]{40}', r[key]): raise ValueError('Invalid commit')
    if r['status'] not in ('reproduced','contradiction','environment_blocked','incomplete'): raise ValueError('Invalid run status')
    if r['reviewVersion'] != r['parentReviewVersion'] + '+run.' + r['runId']: raise ValueError('Run version is not unique')
    for side in ('base','head'):
        for check in ('metadata-regressions-v1','diagnostic-probe-v1'):
            value = r['versions'][side]['checks'][check]
            if value['status'] not in STATES: raise ValueError('Unknown check status')
    for artifact in r['artifacts']:
        if not isinstance(artifact,str) or Path(artifact).is_absolute() or '..' in Path(artifact).parts: raise ValueError('Unsafe artifact path')
    for command in r['commands']:
        if not isinstance(command['argv'],list) or command['log'] not in r['artifacts']: raise ValueError('Missing command provenance')
        if command['status'] not in STATES: raise ValueError('Invalid command status')
        if command['exitCode'] is not None and type(command['exitCode']) is not int: raise ValueError('Invalid exit code')
    return r

def validate_run(r):
    try:
        return _validate_run(r)
    except (KeyError,TypeError,AttributeError) as error:
        raise ValueError('Invalid run structure: '+str(error)) from error

def load_run(path):
    path = Path(path)
    report = validate_run(json.loads(path.read_text()))
    if report['runId'] != path.parent.name: raise ValueError('Run directory identity mismatch')
    for relative in report['artifacts']:
        artifact = (path.parent/relative).resolve()
        if not artifact.is_relative_to(path.parent.resolve()) or not artifact.is_file(): raise ValueError('Missing or unsafe run artifact: '+relative)
    return report
