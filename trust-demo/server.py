"""Local-only presentation of recorded evidence. Python standard library only."""
import argparse
import json
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / "collector"))
from run_contract import load_run
from ai.pipeline import ReviewService, ReviewError, ID_PATTERN, validate_schema
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent

def validate(value, spec, path='$'):
    """Validate the documented JSON Schema subset used by report.schema.json."""
    types = {'object': dict, 'array': list, 'string': str, 'integer': int}
    if type(value) is not types[spec['type']]:
        raise ValueError(f'{path}: expected {spec["type"]}')
    if 'const' in spec and value != spec['const']:
        raise ValueError(f'{path}: invalid constant')
    if isinstance(value, dict):
        missing = set(spec.get('required', [])) - value.keys()
        extra = value.keys() - spec['properties'].keys()
        if missing or (extra and spec.get('additionalProperties') is False):
            raise ValueError(f'{path}: missing {sorted(missing)}, extra {sorted(extra)}')
        for key, item in value.items():
            validate(item, spec['properties'][key], f'{path}.{key}')
    elif isinstance(value, list):
        if len(value) < spec.get('minItems', 0):
            raise ValueError(f'{path}: empty array')
        for i, item in enumerate(value):
            validate(item, spec['items'], f'{path}[{i}]')
    elif isinstance(value, str):
        if len(value) < spec.get('minLength', 0):
            raise ValueError(f'{path}: empty string')
        if 'pattern' in spec and not re.fullmatch(spec['pattern'], value):
            raise ValueError(f'{path}: invalid pattern')

def load_report():
    report = json.loads((ROOT / 'report.json').read_text())
    validate(report, json.loads((ROOT / 'report.schema.json').read_text()))
    for collection in ('artifacts', 'runs', 'criteria'):
        ids = [item['id'] for item in report[collection]]
        if len(ids) != len(set(ids)):
            raise ValueError(f'Duplicate IDs in {collection}')
    artifacts = {item['id'] for item in report['artifacts']}
    runs = {item['id'] for item in report['runs']}
    for criterion in report['criteria']:
        if not set(criterion['tests']) <= runs:
            raise ValueError(f'Unknown run in {criterion["id"]}')
    for item in report['runs'] + [report['finding']]:
        if not set(item['artifacts']) <= artifacts:
            raise ValueError('Unknown artifact reference')
    for artifact in report['artifacts']:
        path = (REPO / artifact['path']).resolve()
        if not path.is_relative_to(REPO / 'evidence') or not path.is_file():
            raise ValueError(f'Missing or invalid artifact: {artifact["path"]}')
    return report

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        route = unquote(urlsplit(self.path).path)
        if route == '/ai/config':
            self.send_json(self.server.review_service.configuration()); return
        if route == '/ai/reviews':
            reviews,errors=[],[]
            for path in sorted(self.server.review_service.output.glob('*/review.json'),reverse=True):
                try:
                    record=json.loads(path.read_text())
                    if not re.fullmatch(ID_PATTERN,record['reviewId']) or record['reviewId']!=path.parent.name:raise ValueError('Invalid review identity')
                    if record['kind']!='issue-2283-ai-review' or record['reviewVersion']!=record['reviewId'] or record['status'] not in ('completed','failed','not_run'):raise ValueError('Invalid review metadata')
                    if record['status']=='completed':
                        validate_schema(record['result'],json.loads((ROOT/'ai/response.schema.json').read_text()))
                        if not isinstance(record['referenceChecks'],list):raise ValueError('Missing reference annotations')
                    reviews.append(record)
                except (ValueError,KeyError,TypeError,OSError) as error:errors.append({'error':'A stored AI review could not be read.'})
            self.send_json({'reviews':reviews,'errors':errors}); return
        if route.startswith('/ai/reviews/'):
            parts=route.strip('/').split('/')
            if len(parts)!=4 or not re.fullmatch(ID_PATTERN,parts[2]) or parts[3] not in ('review.json','input.json','instructions.txt'):
                self.send_error(404); return
            path=self.server.review_service.output/parts[2]/parts[3]
            if not path.is_file():self.send_error(404);return
            if parts[3].endswith('.json'):self.send_json(json.loads(path.read_text()))
            else:
                data=path.read_bytes();self.send_response(200)
                self.send_header('Content-Type','text/plain; charset=utf-8');self.send_header('Content-Length',str(len(data)))
                self.end_headers();self.wfile.write(data)
            return
        if route == '/runs/index.json':
            reports, errors = [], []
            for path in sorted((ROOT/'runs').glob('*/report.json'), reverse=True):
                try:
                    report = load_run(path)
                    reports.append({key:report[key] for key in ('runId','startedAt','finishedAt','status','reviewVersion','base','head','parentReviewVersion')})
                except (ValueError, OSError) as error:
                    errors.append({'path':str(path.relative_to(ROOT)), 'error':str(error)})
            self.send_json({'runs':reports, 'errors':errors})
            return
        if route.startswith('/runs/'):
            parts = route.strip('/').split('/')
            if len(parts) < 3 or not re.fullmatch(r'[0-9TZ-]+-[0-9a-f]{8}', parts[1]):
                self.send_error(404); return
            folder = ROOT/'runs'/parts[1]
            try:
                report = load_run(folder/'report.json')
                relative = '/'.join(parts[2:])
                if relative != 'report.json' and relative not in report['artifacts']:
                    self.send_error(404); return
                path = (folder/relative).resolve()
                if not path.is_relative_to(folder.resolve()) or not path.is_file():
                    self.send_error(404); return
                if relative == 'report.json': self.send_json(report)
                else:
                    data = path.read_bytes()
                    self.send_response(200)
                    self.send_header('Content-Type','text/plain; charset=utf-8')
                    self.send_header('Content-Length',str(len(data)))
                    self.end_headers(); self.wfile.write(data)
            except (ValueError,OSError) as error:
                self.send_json({'error':'Run unavailable or invalid: '+str(error)},500)
            return
        if route.startswith('/evidence/'):
            # Only serve evidence paths explicitly referenced in the validated report.
            allowed = {f'/{a["path"]}' for a in load_report()['artifacts']}
            if route not in allowed:
                self.send_error(404)
                return
            data = (REPO / route.lstrip('/')).read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if route not in ('/', '/index.html', '/app.js', '/style.css', '/report.json', '/report.schema.json'):
            self.send_error(404)
            return
        super().do_GET()

    def do_POST(self):
        # Explicit same-origin JSON requests prevent cross-site form submissions
        # and DNS-rebinding requests from triggering a future paid model call.
        port=self.server.server_address[1]
        allowed={f'127.0.0.1:{port}',f'localhost:{port}'}
        host=self.headers.get('Host','')
        if host not in allowed or self.headers.get('Origin') != 'http://'+host:
            self.send_json({'error':{'code':'origin_rejected','message':'A same-origin request is required.'}},403);return
        if self.path not in ('/ai/reviews','/ai/preflight'):self.send_error(404);return
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':
            self.send_json({'error':{'code':'invalid_request','message':'JSON is required.'}},415);return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=1024:raise ValueError()
            body=json.loads(self.rfile.read(length))
            if not isinstance(body,dict) or set(body) not in ({'runId'},{'runId','quoteId'}):raise ValueError()
            if self.path=='/ai/preflight' and set(body)!={'runId'}:raise ValueError()
        except (ValueError,TypeError):
            self.send_json({'error':{'code':'invalid_request','message':'Provide only an evidence runId.'}},400);return
        try:
            if self.path=='/ai/preflight':
                self.send_json(self.server.review_service.preflight(body['runId']));return
            record,status=self.server.review_service.execute(body['runId'],body.get('quoteId'))
            self.send_json(record,status)
        except ReviewError as error:
            self.send_json({'error':{'code':error.code,'message':error.message,**({'details':error.details} if error.details is not None else {})}},error.http_status)

    def send_json(self, value, status=200):
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(data)))
        self.end_headers(); self.wfile.write(data)

    def do_HEAD(self):
        self.send_error(405)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        super().end_headers()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--port', type=int, default=2283)
    args = parser.parse_args()
    report = load_report()
    print(f'Validated {report["reviewVersion"]}: {len(report["criteria"])} criteria, {len(report["runs"])} runs.', flush=True)
    if not args.check:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
        server.review_service=ReviewService()
        print(f'Earned Trust: http://127.0.0.1:{args.port}', flush=True)
        server.serve_forever()
