"""Dependency-free browser smoke test using Chrome's local DevTools protocol.
Run with the demo server listening. Chrome uses a disposable profile.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import time
from urllib.request import urlopen
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
URL = os.environ.get('TRUST_DEMO_TEST_URL', 'http://127.0.0.1:2283')

class CDP:
    def __init__(self, url):
        u = urlsplit(url)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=20)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f'GET {u.path} HTTP/1.1\r\nHost: {u.netloc}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        header = b''
        while not header.endswith(b'\r\n\r\n'):
            header += self.sock.recv(1)
        assert header.startswith(b'HTTP/1.1 101 '), header
        accept = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
        assert accept in header
        self.ident = 0

    def read(self, n):
        data = b''
        while len(data) < n:
            part = self.sock.recv(n-len(data))
            if not part: raise RuntimeError('Chrome closed connection')
            data += part
        return data

    def receive(self):
        first, second = self.read(2)
        length = second & 127
        if length == 126: length = struct.unpack('!H', self.read(2))[0]
        elif length == 127: length = struct.unpack('!Q', self.read(8))[0]
        mask = self.read(4) if second & 128 else None
        data = self.read(length)
        if mask: data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        if first & 15 == 8: raise RuntimeError('WebSocket closed')
        if first & 15 != 1: raise RuntimeError('Unexpected non-text DevTools frame')
        return json.loads(data)

    def call(self, method, params=None):
        self.ident += 1
        data = json.dumps(dict(id=self.ident, method=method, params=params or {})).encode()
        n = len(data)
        header = bytes([0x81, 0x80 | n]) if n < 126 else bytes([0x81, 0x80 | 126]) + struct.pack('!H', n) if n < 65536 else bytes([0x81, 0x80 | 127]) + struct.pack('!Q', n)
        mask = os.urandom(4)
        self.sock.sendall(header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))
        while True:
            message = self.receive()
            if message.get('id') == self.ident:
                if 'error' in message: raise RuntimeError(message['error'])
                return message.get('result', {})

    def evaluate(self, expression):
        result = self.call('Runtime.evaluate', dict(expression=expression, awaitPromise=True, returnByValue=True))
        if 'exceptionDetails' in result: raise RuntimeError(result['exceptionDetails'])
        return result['result'].get('value')

    def ready(self):
        self.call('Page.navigate', {'url':URL})
        for _ in range(150):
            if self.evaluate("Boolean(document.getElementById('content') && !document.getElementById('content').hidden)"): return
            time.sleep(.1)
        raise RuntimeError('Review did not render')

    def screenshot(self, path):
        layout = self.call('Page.getLayoutMetrics')['cssContentSize']
        shot = self.call('Page.captureScreenshot', {'format':'png', 'captureBeyondViewport':True, 'clip':{'x':0,'y':0,'width':layout['width'],'height':layout['height'],'scale':1}})
        path.write_bytes(base64.b64decode(shot['data']))

with tempfile.TemporaryDirectory(prefix='earned-trust-chrome-') as profile:
    with open(Path(profile)/'chrome.log', 'wb') as log:
        process = subprocess.Popen(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '--headless', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--remote-debugging-port=0', f'--user-data-dir={profile}', 'about:blank'], stdout=log, stderr=log)
        try:
            port_file = Path(profile)/'DevToolsActivePort'
            for _ in range(150):
                if port_file.exists(): break
                if process.poll() is not None: raise RuntimeError('Chrome failed to start')
                time.sleep(.1)
            port = port_file.read_text().splitlines()[0]
            targets = json.load(urlopen(f'http://127.0.0.1:{port}/json'))
            cdp = CDP(next(t['webSocketDebuggerUrl'] for t in targets if t['type'] == 'page'))
            cdp.call('Page.enable')
            cdp.call('Emulation.setDeviceMetricsOverride', dict(width=1440,height=1000,deviceScaleFactor=1,mobile=False))
            cdp.ready()
            if '--design-checks' in __import__('sys').argv:
                output = ROOT/'design-evidence'
                output.mkdir(exist_ok=True)
                assert cdp.evaluate("document.getElementById('decision').getBoundingClientRect().left > document.querySelector('.review-body').getBoundingClientRect().right")
                assert cdp.evaluate("document.querySelectorAll('#evidence th').length === 4 && document.querySelector('#evidence tbody tr').tagName === 'TR'")
                assert cdp.evaluate("Array.from(document.querySelectorAll('.check-passed')).every(el => /^[0-9,]+ passed$/.test(el.textContent))")
                cdp.screenshot(output/'after-desktop.png')
                cdp.call('Emulation.setDeviceMetricsOverride', dict(width=390,height=844,deviceScaleFactor=1,mobile=True))
                assert cdp.evaluate("document.getElementById('decision').getBoundingClientRect().top > document.getElementById('limits').getBoundingClientRect().bottom")
                assert cdp.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                cdp.screenshot(output/'after-mobile.png')
                cdp.call('Emulation.setDeviceMetricsOverride', dict(width=1440,height=1000,deviceScaleFactor=1,mobile=False))
                print('PASS: DESIGN desktop decision sidebar, semantic four-column table, mobile decision after content', flush=True)
                cdp.call('Input.dispatchKeyEvent', dict(type='keyDown',key='Tab',code='Tab',windowsVirtualKeyCode=9))
                cdp.call('Input.dispatchKeyEvent', dict(type='keyUp',key='Tab',code='Tab',windowsVirtualKeyCode=9))
                assert cdp.evaluate("document.activeElement.classList.contains('skip-link') && getComputedStyle(document.activeElement).outlineStyle !== 'none'")
                cdp.evaluate("document.querySelector('#technical > summary').focus()")
                assert cdp.evaluate("document.activeElement === document.querySelector('#technical > summary')")
                cdp.call('Input.dispatchKeyEvent', dict(type='keyDown',key='Enter',code='Enter',windowsVirtualKeyCode=13,text='\r',unmodifiedText='\r'))
                cdp.call('Input.dispatchKeyEvent', dict(type='keyUp',key='Enter',code='Enter',windowsVirtualKeyCode=13))
                for _ in range(20):
                    if cdp.evaluate("document.getElementById('technical').open"): break
                    time.sleep(.05)
                assert cdp.evaluate("document.getElementById('technical').open")
                print('PASS: DESIGN keyboard Tab focus and Enter disclosure activation', flush=True)
                # Verify contrast for actual text colors against the surfaces they use.
                ratios = cdp.evaluate("""(()=>{const lum=hex=>{const v=hex.match(/[0-9a-f]{2}/gi).map(x=>parseInt(x,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return .2126*v[0]+.7152*v[1]+.0722*v[2]};const contrast=(a,b)=>(Math.max(lum(a),lum(b))+.05)/(Math.min(lum(a),lum(b))+.05);return ['#202733','#586273','#205cc0','#9b4c10','#236443'].map(x=>contrast(x,'#ffffff'));})()""")
                assert min(ratios) >= 4.5, ratios
                print('PASS: DESIGN primary, secondary, link, finding and passed-result colors meet 4.5:1 on white', flush=True)
                cdp.call('Emulation.setEmulatedMedia', {'features':[{'name':'prefers-reduced-motion','value':'reduce'}]})
                assert cdp.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches && getComputedStyle(document.getElementById('decision-message')).animationName === 'none'")
                print('PASS: DESIGN reduced-motion mode has no feedback animation', flush=True)
                cdp.ready()
                cdp.evaluate("document.getElementById('owner').value='Design test';document.getElementById('verdict').value='accept';document.getElementById('verdict').dispatchEvent(new Event('change'));document.getElementById('rationale').value='Test only';document.getElementById('risk').value='Test risk';")
                assert cdp.evaluate("!document.getElementById('acceptance-note').hidden && document.getElementById('risk-ack').required && !document.getElementById('risk-ack').checked")
                cdp.evaluate("document.getElementById('decision-form').requestSubmit()")
                assert cdp.evaluate("document.getElementById('decision-status').textContent === 'Pending human review' && localStorage.length === 0")
                cdp.evaluate("document.getElementById('risk-ack').checked=true;document.getElementById('decision-form').requestSubmit()")
                assert cdp.evaluate("JSON.parse(localStorage.getItem(Object.keys(localStorage)[0])).decision.residualRiskAcknowledged === true")
                cdp.ready()
                assert cdp.evaluate("document.getElementById('risk-ack').checked && !document.getElementById('risk-confirmation').hidden")
                cdp.evaluate('localStorage.clear()'); cdp.ready()
                print('PASS: DESIGN acceptance requires explicit residual-risk acknowledgement and restores it', flush=True)
            assert cdp.evaluate("document.getElementById('decision-status').textContent === 'Pending human review' && document.getElementById('owner').value === '' && document.getElementById('export').disabled")
            assert cdp.evaluate("document.querySelectorAll('.evidence-row').length === 4 && document.querySelectorAll('#runs .run').length === 6 && document.querySelectorAll('#limit-cards .card').length === 6")
            print('PASS: initial pending state; criteria, recorded runs, finding and limits rendered', flush=True)
            report = json.loads((ROOT/'report.json').read_text())
            for a in report['artifacts']:
                with urlopen(URL+'/'+a['path']) as response: assert response.status == 200
            from urllib.error import HTTPError
            for forbidden in ['/server.py','/Directory.Packages.props','/evidence/../Directory.Packages.props']:
                try: urlopen(URL+forbidden)
                except HTTPError as error: assert error.code == 404
                else: raise AssertionError('Private path exposed')
            print(f'PASS: all {len(report["artifacts"])} evidence links return 200; unrelated files are not served', flush=True)
            cdp.evaluate("document.querySelector('.run-link').click()")
            time.sleep(.2)
            assert cdp.evaluate("document.getElementById('runs').parentElement.open")
            print('PASS: criterion-to-run navigation opens recorded evidence', flush=True)
            cdp.ready(); cdp.screenshot(ROOT/'preview-desktop.png')
            def fill():
                cdp.evaluate("document.getElementById('owner').value='Browser test — self-declared';document.getElementById('verdict').value='request_changes';document.getElementById('rationale').value='Test-only: address F1 before acceptance.';document.getElementById('risk').value='No release risk accepted by this automated UI check.';")
            fill()
            cdp.evaluate("document.getElementById('decision-form').requestSubmit()")
            assert cdp.evaluate("document.getElementById('decision-status').textContent.includes('saved locally')")
            saved = cdp.evaluate("JSON.parse(localStorage.getItem(Object.keys(localStorage).find(k=>k.startsWith('earned-trust:decision:'))))")
            assert saved['review'] == dict(version=report['reviewVersion'],base=report['change']['base'],head=report['change']['head'])
            cdp.ready()
            assert cdp.evaluate("document.getElementById('owner').value === 'Browser test — self-declared' && document.getElementById('verdict').value === 'request_changes'")
            print('PASS: save/read-back, full SHA/version binding and reload persistence', flush=True)
            cdp.call('Browser.setDownloadBehavior', {'behavior':'allow','downloadPath':profile})
            cdp.evaluate("window.originalCreate=URL.createObjectURL;URL.createObjectURL=function(blob){window.exportedBlob=blob;return window.originalCreate(blob)};document.getElementById('rationale').value='Unsaved edit';document.getElementById('rationale').dispatchEvent(new Event('input',{bubbles:true}));document.getElementById('export').click()")
            exported = json.loads(cdp.evaluate('window.exportedBlob.text()'))
            assert exported == saved
            for _ in range(50):
                downloads = list(Path(profile).glob('earned-trust-*.json'))
                if downloads: break
                time.sleep(.1)
            assert downloads and json.loads(downloads[0].read_text()) == saved
            print('PASS: actual downloaded JSON matches the saved decision; unsaved edits are excluded', flush=True)
            if '--collector-checks' in __import__('sys').argv:
                records=[json.loads(path.read_text()) for path in (ROOT/'runs').glob('*/report.json')]
                good=next(run for run in records if run['status']=='reproduced')
                blocked=next(run for run in records if run['status']=='environment_blocked')
                for _ in range(100):
                    if cdp.evaluate("!document.getElementById('use-run').hidden"):break
                    time.sleep(.1)
                cdp.evaluate("document.getElementById('run-select').value="+json.dumps(blocked['runId'])+";document.getElementById('run-select').dispatchEvent(new Event('change'))")
                for _ in range(100):
                    if cdp.evaluate("document.getElementById('collected-result').textContent.includes('environment blocked') && !document.getElementById('use-run').hidden"):break
                    time.sleep(.1)
                assert cdp.evaluate("document.getElementById('collected-result').textContent.includes('not run') && document.getElementById('collected-result').textContent.includes('environment blocked')")
                cdp.evaluate("document.getElementById('run-select').value="+json.dumps(good['runId'])+";document.getElementById('run-select').dispatchEvent(new Event('change'))")
                for _ in range(100):
                    if cdp.evaluate("document.getElementById('collected-result').textContent.includes('Collection: reproduced') && !document.getElementById('use-run').hidden"):break
                    time.sleep(.1)
                assert cdp.evaluate("document.getElementById('collected-result').textContent.includes('3 passed / 0 failed') && document.getElementById('collected-result').textContent.includes('0 passed / 3 failed')")
                cdp.evaluate("document.getElementById('use-run').click()")
                assert cdp.evaluate("document.getElementById('decision-status').textContent === 'Pending human review' && document.getElementById('owner').value === '' && document.getElementById('export').disabled")
                fill();cdp.evaluate("document.getElementById('owner').value='Execution-only test decision';document.getElementById('decision-form').requestSubmit()")
                cdp.call('Page.navigate', {'url':URL+'/?run='+good['runId']})
                for _ in range(100):
                    if cdp.evaluate("Boolean(document.getElementById('owner') && document.getElementById('owner').value === 'Execution-only test decision')"):break
                    time.sleep(.1)
                assert cdp.evaluate("document.getElementById('decision-status').textContent.includes('saved locally') && document.getElementById('decision-scope').textContent.includes('execution report')")
                assert good['reviewVersion'] in cdp.evaluate("document.getElementById('binding').textContent")
                cdp.evaluate("document.getElementById('original-scope').click()")
                assert cdp.evaluate("document.getElementById('owner').value === 'Browser test — self-declared' && document.getElementById('decision-scope').textContent.includes('original recorded AI assessment')")
                print('PASS: COLLECTOR successful/blocked reports displayed; old decision never inherited; new run decision saves and restores independently',flush=True)
                for command in good['commands']:
                    with urlopen(URL+'/runs/'+good['runId']+'/'+command['log']) as response:assert response.status==200
                print('PASS: COLLECTOR every actual command log is accessible',flush=True)
                mock_source="const originalRunFetch=window.fetch;window.fetch=async function(...args){const response=await originalRunFetch(...args);if(typeof args[0]==='string' && /^\\/runs\\/[^/]+\\/report\\.json$/.test(args[0])){const run=await response.json();if(run.status==='reproduced'){run.status='contradiction';run.contradictions=['Test fixture only: prior observation no longer repeats'];run.versions.head.checks['diagnostic-probe-v1'].matchesPreviousObservation=false;return new Response(JSON.stringify(run),{status:200});}}return response;}"
                mocked=cdp.call('Page.addScriptToEvaluateOnNewDocument', {'source':mock_source})['identifier']
                cdp.ready()
                for _ in range(100):
                    if cdp.evaluate("document.getElementById('collected-result').textContent.includes('Test fixture only')"):break
                    time.sleep(.1)
                assert cdp.evaluate("document.getElementById('collected-result').textContent.includes('Collection: contradiction') && document.getElementById('collected-result').textContent.includes('differs from the previous observation')")
                cdp.call('Page.removeScriptToEvaluateOnNewDocument', {'identifier':mocked})
                cdp.call('Page.navigate', {'url':URL+'/?run=missing-test-report'})
                for _ in range(100):
                    if cdp.evaluate("Boolean(document.getElementById('run-load-error') && !document.getElementById('run-load-error').hidden)"):break
                    time.sleep(.1)
                assert cdp.evaluate("document.getElementById('decision-form').hidden && document.getElementById('decision-status').textContent === 'Pending human review'")
                cdp.ready()
                print('PASS: COLLECTOR simulated contradiction is explicit; missing requested report cannot inherit a decision',flush=True)
                cdp.evaluate("for (const key of Object.keys(localStorage)) if (key.includes('+run.')) localStorage.removeItem(key);")

            if '--ai-checks' in __import__('sys').argv:
                for _ in range(100):
                    if cdp.evaluate("!document.getElementById('use-run').hidden"):break
                    time.sleep(.1)
                cdp.evaluate("document.getElementById('run-ai').click()")
                for _ in range(100):
                    if cdp.evaluate("document.getElementById('ai-status').textContent.includes('missing_configuration')"):break
                    time.sleep(.1)
                assert cdp.evaluate("document.getElementById('ai-status').textContent.includes('missing_configuration') && document.getElementById('decision-status').textContent.includes('saved locally')")
                print('PASS: AI real unconfigured endpoint reports missing configuration; no fake successful assessment',flush=True)
                # The following are BROWSER TEST DOUBLES, never written to the server.
                ai_ids=['ai-20261114T000000Z-000000000001','ai-20261114T000000Z-000000000002']
                fixtures=[]
                for ident in ai_ids:
                    fixtures.append(dict(kind='issue-2283-ai-review',status='completed',reviewId=ident,reviewVersion=ident,base=report['change']['base'],head=report['change']['head'],evidenceRunId='20261114T211745Z-9e9c520a',service='TEST-DOUBLE ONLY',model='TEST-MODEL',inputSha256='a'*64,instructionsSha256='b'*64,result=dict(requirements=[dict(id='R-TEST',title='TEST DOUBLE requirement',status='unverified',rationale='Synthetic UI fixture, no actual model inference.',evidenceIds=['observations'])],findings=[],uncertainties=['TEST DOUBLE ONLY'],unchecked=['No model execution'],humanQuestions=['Test fixture only']),referenceChecks=[dict(owner='R-TEST',kind='evidence',reference='missing-test-reference',status='unverified',explanation='TEST DOUBLE: ID does not exist.')]))
                script="const aiTestReviews="+json.dumps(fixtures)+";const aiTestFetch=window.fetch;window.fetch=async function(...args){if(args[0]==='/ai/reviews'){if(args[1]?.method==='POST'){const code=window.aiFailureCode||'service_error';return new Response(JSON.stringify({status:'failed',error:{code,message:'TEST DOUBLE '+code}}),{status:code==='timeout'?504:code==='invalid_response'?422:502});}return new Response(JSON.stringify({reviews:aiTestReviews,errors:[]}),{status:200});}return aiTestFetch(...args);}"
                injected_ai=cdp.call('Page.addScriptToEvaluateOnNewDocument',{'source':script})['identifier']
                cdp.ready()
                for _ in range(100):
                    if cdp.evaluate("document.querySelectorAll('.ai-use-scope').length === 2"):break
                    time.sleep(.1)
                assert cdp.evaluate("document.getElementById('ai-history').textContent.includes('unverified') && document.getElementById('ai-history').textContent.includes('TEST-DOUBLE ONLY')")
                cdp.evaluate("document.querySelector('[data-review-id=\""+ai_ids[0]+"\"]').click()")
                assert cdp.evaluate("document.getElementById('decision-status').textContent === 'Pending human review' && document.getElementById('owner').value === ''")
                fill();cdp.evaluate("document.getElementById('owner').value='AI TEST FIXTURE DECISION';document.getElementById('decision-form').requestSubmit()")
                cdp.evaluate("window.originalAIExport=URL.createObjectURL;URL.createObjectURL=function(blob){window.aiExport=blob;return window.originalAIExport(blob)};document.getElementById('export').click()")
                ai_export=json.loads(cdp.evaluate('window.aiExport.text()'))
                assert ai_export['review']['aiReviewId']==ai_ids[0]
                assert ai_export['review']['evidenceRunId']=='20261114T211745Z-9e9c520a'
                assert ai_export['review']['base']==report['change']['base'] and ai_export['review']['head']==report['change']['head']
                cdp.evaluate("document.querySelector('[data-review-id=\""+ai_ids[1]+"\"]').click()")
                assert cdp.evaluate("document.getElementById('decision-status').textContent === 'Pending human review' && document.getElementById('owner').value === ''")
                cdp.call('Page.navigate',{'url':URL+'/?aiReview='+ai_ids[0]})
                for _ in range(100):
                    if cdp.evaluate("Boolean(document.getElementById('owner') && document.getElementById('owner').value === 'AI TEST FIXTURE DECISION')"):break
                    time.sleep(.1)
                assert cdp.evaluate("document.getElementById('decision-status').textContent.includes('saved locally') && document.getElementById('binding').textContent.includes('"+ai_ids[0]+"')")
                cdp.evaluate("document.getElementById('original-scope').click()")
                assert cdp.evaluate("document.getElementById('owner').value === 'Browser test — self-declared'")
                print('PASS: AI TEST DOUBLES isolated review IDs, pending new decision, restore, export and unverified-reference display',flush=True)
                for error_code in ('timeout','service_error','invalid_response'):
                    for _ in range(100):
                        if cdp.evaluate("!document.getElementById('use-run').hidden"):break
                        time.sleep(.1)
                    cdp.evaluate("window.aiFailureCode="+json.dumps(error_code)+";document.getElementById('run-ai').click()")
                    for _ in range(100):
                        if cdp.evaluate("document.getElementById('ai-status').textContent.includes('"+error_code+"') && !document.getElementById('run-ai').disabled"):break
                        time.sleep(.1)
                    assert cdp.evaluate("document.getElementById('ai-status').textContent.includes('"+error_code+"') && document.querySelectorAll('.ai-use-scope').length === 2")
                print('PASS: AI TEST DOUBLES timeout, service error and invalid response visible; previous results preserved',flush=True)
                cdp.evaluate("for (const key of Object.keys(localStorage)) if (key.startsWith('earned-trust:decision:ai-')) localStorage.removeItem(key);")
                cdp.call('Page.removeScriptToEvaluateOnNewDocument',{'identifier':injected_ai});cdp.ready()
            if '--anthropic-checks' in __import__('sys').argv:
                # BROWSER TEST DOUBLE ONLY. No Anthropic network request or production record.
                fake_review=dict(kind='issue-2283-ai-review',status='completed',reviewId='ai-20261115T000000Z-000000000099',reviewVersion='ai-20261115T000000Z-000000000099',base=report['change']['base'],head=report['change']['head'],evidenceRunId='20261114T211745Z-9e9c520a',service='TEST-DOUBLE ONLY',model='claude-sonnet-5-5',inputSha256='a'*64,instructionsSha256='b'*64,result=dict(requirements=[dict(id='R-ONLY-TEST',title='Test requirement',status='unverified',rationale='TEST DOUBLE ONLY',evidenceIds=[])],findings=[],uncertainties=['Test only'],unchecked=['No real model run'],humanQuestions=['Test only']),referenceChecks=[],providerMetadata=dict(requestId='req_TEST_ONLY',messageId='msg_TEST_ONLY',stopReason='end_turn',usage={'input_tokens':150000,'output_tokens':1000},actualCostEstimateUSD=.31))
                quote=dict(quoteId='quote-TEST_ONLY',resolvedModel='claude-sonnet-5-5',inputTokens=150000,maxOutputTokens=8192,contextCapacity=1000000,estimatedUSDWithMaxOutput=.38192,estimatedUSDWithMargin=.390112)
                script="window.testPaidCalls=0;window.testTokenCalls=0;window.testSavedReview=null;const testReview="+json.dumps(fake_review)+";const testQuote="+json.dumps(quote)+";const beforeAnthropicTestFetch=window.fetch;window.fetch=async function(...args){if(args[0]==='/ai/config')return new Response(JSON.stringify({configured:true,requiresPreflight:true,missing:[]}));if(args[0]==='/ai/preflight'){window.testTokenCalls++;return new Response(JSON.stringify(testQuote));}if(args[0]==='/ai/reviews'){if(args[1]?.method==='POST'){window.testPaidCalls++;window.testPaidBody=JSON.parse(args[1].body);window.testSavedReview=testReview;return new Response(JSON.stringify(testReview),{status:201});}return new Response(JSON.stringify({reviews:window.testSavedReview?[window.testSavedReview]:[],errors:[]}));}return beforeAnthropicTestFetch(...args);}"
                injected_claude=cdp.call('Page.addScriptToEvaluateOnNewDocument',{'source':script})['identifier']
                cdp.ready()
                for _ in range(100):
                    if cdp.evaluate("!document.getElementById('prepare-ai').hidden && !document.getElementById('use-run').hidden"):break
                    time.sleep(.1)
                assert cdp.evaluate("document.getElementById('run-ai').disabled && window.testPaidCalls===0")
                cdp.evaluate("document.getElementById('prepare-ai').click()")
                for _ in range(100):
                    if cdp.evaluate("!document.getElementById('run-ai').disabled"):break
                    time.sleep(.1)
                assert cdp.evaluate("document.getElementById('ai-cost').textContent.includes('150,000') && document.getElementById('ai-cost').textContent.includes('$0.3819') && window.testPaidCalls===0 && window.testTokenCalls===1")
                cdp.evaluate("document.getElementById('run-ai').click()")
                for _ in range(100):
                    if cdp.evaluate("document.getElementById('ai-history').textContent.includes('No findings returned')"):break
                    time.sleep(.1)
                assert cdp.evaluate("window.testPaidCalls===1 && window.testPaidBody.quoteId==='quote-TEST_ONLY' && document.getElementById('run-ai').disabled")
                assert cdp.evaluate("document.getElementById('ai-history').textContent.includes('No findings returned') && document.getElementById('ai-history').textContent.includes('req_TEST_ONLY') && document.getElementById('ai-history').textContent.includes('150000')")
                assert cdp.evaluate("document.getElementById('decision-scope').textContent.includes('original recorded AI assessment')")
                print('PASS: ANTHROPIC TEST DOUBLE token/cost gate before one generation; usage/IDs and no-findings result shown honestly; no inherited human approval',flush=True)
                cdp.call('Page.removeScriptToEvaluateOnNewDocument',{'identifier':injected_claude});cdp.ready()
            # Simulate receiving a newer recorded report, without changing any repository file.
            injected = cdp.call('Page.addScriptToEvaluateOnNewDocument', {'source':"const originalFetch=window.fetch;window.fetch=async function(...args){const res=await originalFetch(...args);if(args[0]==='/report.json'){const data=await res.json();data.reviewVersion='2283-review-2-test-only';return new Response(JSON.stringify(data),{status:200});}return res;}"})['identifier']
            cdp.ready()
            assert cdp.evaluate("document.getElementById('decision-status').textContent === 'Pending human review' && document.getElementById('owner').value === ''")
            cdp.call('Page.removeScriptToEvaluateOnNewDocument', {'identifier':injected})
            print('PASS: a different review version does not inherit a decision', flush=True)
            cdp.ready()
            cdp.evaluate("const key=Object.keys(localStorage).find(k=>k.startsWith('earned-trust:decision:'));const d=JSON.parse(localStorage.getItem(key));d.review.head='0'.repeat(40);localStorage.setItem(key,JSON.stringify(d));")
            cdp.ready()
            assert cdp.evaluate("document.getElementById('decision-status').textContent === 'Pending human review' && document.getElementById('export').disabled && document.getElementById('decision-message').textContent.includes('invalid')")
            print('PASS: stale SHA binding is rejected; status remains pending', flush=True)
            cdp.call('Emulation.setDeviceMetricsOverride', dict(width=390,height=844,deviceScaleFactor=1,mobile=True))
            assert cdp.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            cdp.screenshot(ROOT/'preview-mobile.png')
            print('PASS: mobile layout without horizontal overflow', flush=True)
            cdp.evaluate('localStorage.clear()')
            denied = cdp.call('Page.addScriptToEvaluateOnNewDocument', {'source':"Storage.prototype.setItem=function(){throw new Error('Simulated storage denial')}"})['identifier']
            cdp.ready(); fill(); cdp.evaluate("document.getElementById('decision-form').requestSubmit()")
            assert cdp.evaluate("document.getElementById('decision-status').textContent === 'Pending human review' && document.getElementById('decision-message').textContent.includes('not saved')")
            print('PASS: storage denial cannot become a saved decision', flush=True)
            cdp.call('Page.removeScriptToEvaluateOnNewDocument', {'identifier':denied})
            cdp.call('Page.addScriptToEvaluateOnNewDocument', {'source':"const originalFetch=window.fetch;window.fetch=async function(...args){const res=await originalFetch(...args);if(args[0]==='/report.json'){const data=await res.json();delete data.change;return new Response(JSON.stringify(data),{status:200});}return res;}"})
            cdp.call('Page.navigate', {'url':URL})
            for _ in range(100):
                if cdp.evaluate("Boolean(document.getElementById('fatal') && !document.getElementById('fatal').hidden)"): break
                time.sleep(.1)
            assert cdp.evaluate("!document.getElementById('fatal').hidden && document.getElementById('content').hidden")
            print('PASS: malformed report fails closed', flush=True)
            cdp.sock.close()
        finally:
            process.terminate()
            process.wait(timeout=20)
print('All Chrome browser checks passed. Disposable test decisions are not human approvals.')
