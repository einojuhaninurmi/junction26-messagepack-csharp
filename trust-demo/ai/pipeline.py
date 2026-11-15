"""Server-only material preparation, validation and review lifecycle; stdlib only."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import queue
import re
import subprocess
import threading
import time
import uuid
from .adapters import PROVIDERS, ReviewRequest, ReviewReply, AdapterFailure
from collector.run_contract import load_run

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent
SHA={'base':'32258fdbee4bcd653c79f51b4376b5103c6f4d27','head':'9df83c38409c8bfad0517aebffe48211eda4a5b4'}
ID_PATTERN=r'ai-[0-9TZ]+-[0-9a-f]{12}'
CONTEXT=[
 'src/MessagePack.SourceGenerator/CodeAnalysis/TypeCollector.cs',
 'src/MessagePack.SourceGenerator/MessagePackGenerator.cs',
 'src/MessagePack.SourceGenerator/Analyzers/MsgPack00xMessagePackAnalyzer.cs',
 'tests/MessagePack.SourceGenerator.Tests/Verifiers/CSharpSourceGeneratorVerifier`1+Test.cs',
 'CONTRIBUTING.md','SECURITY.md','.editorconfig','Directory.Build.props',
 'Directory.Build.targets','Directory.Packages.props',
 'src/MessagePack.SourceGenerator/MessagePack.SourceGenerator.csproj',
]
LIMITS=[
 'Selected collection covers only three metadata regression tests and five diagnostic probe cases per revision.',
 'Both versions use the attached conditional IsAnalyzerProject Roslyn 4.11.0 compatibility correction; this does not establish an untouched-branch build.',
 'No whole-solution run, exact-example runtime round-trip, Windows or NativeAOT publishing was performed by this collection.',
 'The source issue describes a different package/SDK/OS environment.',
 'Probe source and tests can disclose edge cases. This is evidence-assisted review, not a blind test.',
]

def encode(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def sha(data):return hashlib.sha256(data if isinstance(data,bytes) else data.encode()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()

class ReviewError(Exception):
    def __init__(self,code,message,http_status=422,details=None):
        super().__init__(message);self.code=code;self.message=message;self.http_status=http_status;self.details=details


def git(*args):
    child_env={key:value for key,value in os.environ.items() if key!='TRUST_REVIEW_API_KEY'}
    result=subprocess.run(['git',*args],cwd=REPO,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20,env=child_env)
    if result.returncode:raise ReviewError('material_unavailable','Frozen repository material could not be read.')
    return result.stdout.decode('utf-8',errors='replace')


def build_material(run_id):
    if not isinstance(run_id,str) or not re.fullmatch(r'[0-9TZ-]+-[0-9a-f]{8}',run_id):raise ReviewError('invalid_run','Invalid evidence run ID.',400)
    try:run=load_run(ROOT/'runs'/run_id/'report.json')
    except (ValueError,OSError):raise ReviewError('invalid_run','Evidence report or artifacts are missing or invalid.',400)
    if any(run[side]!=SHA[side] for side in SHA):raise ReviewError('invalid_run','This demo only reviews the pinned issue #2283 comparison.',400)
    evidence=[]
    def add(ident,kind,content):
        evidence.append(dict(id=ident,kind=kind,content=content,sha256=sha(content if isinstance(content,str) else encode(content))))
    # Never pass run.status, comparisons, expected, matchesPreviousObservation,
    # contradictions, reason prose, run_contract.py or prior review/report.json.
    observations={}
    for side in SHA:
        version=run['versions'][side]
        checks={}
        for ident,check in version['checks'].items():
            projected={key:check[key] for key in ('status','passed','failed','commandIds') if key in check}
            if 'tests' in check:projected['tests']=[{key:test[key] for key in ('name','outcome')} for test in check['tests']]
            if 'cases' in check:projected['cases']={name:{key:case[key] for key in ('diagnostics','exceptions','generated','emit')} for name,case in check['cases'].items()}
            checks[ident]=projected
        observations[side]=dict(commit=run[side],checks=checks,tools=version.get('tools',{}))
        add('setup:'+side,'setup_patch',(ROOT/'runs'/run_id/side/'setup.patch').read_text())
    add('observations','actual_execution_results',observations)
    suffixes=('-regressions','-probe','-build','-sdk-info','-compiler-version','-discover','-probe-build')
    for command in run['commands']:
        if command['id'].endswith(suffixes):
            path=ROOT/'runs'/run_id/command['log']
            add('command:'+command['id'],'execution_log',dict(argv=command['argv'],exitCode=command['exitCode'],status=command['status'],output=path.read_text(errors='replace')))
    for filename,key in [('Probe.cs','probeSha256'),('GenericsFormatterTests.cs','testFileSha256')]:
        data=(ROOT/'runs'/run_id/'inputs'/filename).read_bytes()
        if sha(data)!=run['inputs'].get(key):raise ReviewError('material_integrity','A recorded harness input hash does not match.')
        add('harness:'+filename,'executed_harness_source',data.decode('utf-8-sig'))
    context=[]
    for revision,commit in SHA.items():
        for path in CONTEXT:
            text=git('show',commit+':'+path)
            context.append(dict(revision=revision,path=path,lineCount=len(text.splitlines()),content='\n'.join(f'{i}: {line}' for i,line in enumerate(text.splitlines(),1))))
    material=dict(issue=2283,base=SHA['base'],head=SHA['head'],evidenceRunId=run_id,
        requirement=json.loads((ROOT/'ai/requirement.json').read_text()),
        diff=git('diff','--no-ext-diff','--no-textconv',SHA['base'],SHA['head'],'--'),
        repositoryContext=context,evidence=evidence,limits=LIMITS,
        reviewDesign='Evidence-assisted, not blind. Prior AI assessments and prepared finding summaries are excluded.')
    serialized=encode(material)
    if len(serialized.encode())>1_500_000:raise ReviewError('material_too_large','Review material exceeds the local size limit; no silent truncation is performed.')
    return material


def validate_schema(value,spec,path='$'):
    kind='object' if type(value)is dict else 'array' if type(value)is list else 'string' if type(value)is str else 'integer' if type(value)is int else 'invalid'
    if kind!=spec['type']:raise ValueError(path+': unexpected type')
    if 'enum'in spec and value not in spec['enum']:raise ValueError(path+': invalid enum')
    if kind=='object':
        if set(value)!=set(spec['properties']):raise ValueError(path+': missing or unexpected fields')
        for key,item in value.items():validate_schema(item,spec['properties'][key],path+'.'+key)
    elif kind=='array':
        if not spec.get('minItems',0)<=len(value)<=spec.get('maxItems',100):raise ValueError(path+': invalid item count')
        for i,item in enumerate(value):validate_schema(item,spec['items'],path+f'[{i}]')
    elif kind=='string':
        if not spec.get('minLength',0)<=len(value)<=spec.get('maxLength',12000) or not value.strip():raise ValueError(path+': invalid string length')
    elif kind=='integer' and 'minimum' in spec and value<spec['minimum']:raise ValueError(path+': invalid integer')


def validate_response(output,material):
    if isinstance(output,str):
        if len(output.encode())>200_000:raise ReviewError('invalid_response','Response exceeds size limit.')
        try:output=json.loads(output)
        except ValueError:raise ReviewError('invalid_response','Provider did not return valid JSON.')
    try:
        if len(encode(output).encode())>200_000:raise ValueError('Response exceeds size limit')
        validate_schema(output,json.loads((ROOT/'ai/response.schema.json').read_text()))
        ids=[x['id'] for group in ('requirements','findings') for x in output[group]]
        if len(ids)!=len(set(ids)):raise ValueError('Duplicate assessment IDs')
    except (ValueError,TypeError):raise ReviewError('invalid_response','Provider response does not match the required review schema.')
    if sum(len(item.get('references',[])) for item in output['findings']) > 100:
        raise ReviewError('invalid_response','Too many source references to validate safely.')
    source_lengths={}
    # References are annotations, never a truth verdict. Invalid ones stay visible.
    known={item['id'] for item in material['evidence']}
    checks=[]
    for group in ('requirements','findings'):
        for item in output[group]:
            for ident in item['evidenceIds']:
                checks.append(dict(owner=item['id'],kind='evidence',reference=ident,status='exists' if ident in known else 'unverified',explanation='Identifier exists in supplied material; claim correctness is not verified.' if ident in known else 'Identifier is not in the supplied evidence.'))
            for ref in item.get('references',[]):
                exists=False
                path=PurePosixPath(ref['path'])
                if ref['revision'] in SHA and not path.is_absolute() and '..'not in path.parts and '\\'not in ref['path'] and not any(ord(ch)<32 for ch in ref['path']) and 1<=ref['lineStart']<=ref['lineEnd']:
                    try:
                        source_key=(ref['revision'],ref['path'])
                        if source_key not in source_lengths:
                            object_id=SHA[ref['revision']]+':'+ref['path']
                            source_lengths[source_key]=len(git('show',object_id).splitlines()) if git('cat-file','-t',object_id).strip()=='blob' else 0
                        exists=ref['lineEnd']<=source_lengths[source_key]
                    except ReviewError:pass
                checks.append(dict(owner=item['id'],kind='source',reference=ref,status='exists' if exists else 'unverified',explanation='File and line range exist at the pinned commit; claim correctness is not verified.' if exists else 'File/revision/line range could not be verified.'))
    return output,checks

class ReviewService:
    def __init__(self,registry=None,output=None,env=None):
        self.registry=PROVIDERS if registry is None else registry
        self.output=ROOT/'ai-reviews' if output is None else Path(output)
        self.env=os.environ if env is None else env
        self.lock=threading.Lock()
        self.active_worker=None
        self.quotes={}

    def configuration(self):
        missing=[name for name in ('TRUST_REVIEW_PROVIDER','TRUST_REVIEW_MODEL','TRUST_REVIEW_API_KEY') if not self.env.get(name)]
        provider=self.env.get('TRUST_REVIEW_PROVIDER','')
        if provider not in self.registry:missing.append('An explicitly implemented adapter for the selected provider')
        return dict(configured=not missing,missing=missing,requiresPreflight=provider=='anthropic',message='No provider-specific integration has been selected or implemented.' if not self.registry else 'Server-side review configuration status.')

    def _request(self,run_id):
        config=self.configuration()
        if not config['configured']:raise ReviewError('missing_configuration','Model service is not configured. Missing: '+', '.join(config['missing']),409)
        material=build_material(run_id)
        instructions=(ROOT/'ai/instructions.txt').read_text()
        provider=self.env['TRUST_REVIEW_PROVIDER'];model=self.env['TRUST_REVIEW_MODEL'];key=self.env['TRUST_REVIEW_API_KEY']
        try:timeout=float(self.env.get('TRUST_REVIEW_TIMEOUT_SECONDS','300' if provider=='anthropic' else '60'))
        except ValueError:raise ReviewError('missing_configuration','Timeout must be a number.',409)
        if not 0<timeout<=300:raise ReviewError('missing_configuration','Timeout must be between 0 and 300 seconds.',409)
        if key and any(key in value for value in (encode(material),instructions,provider,model)):
            raise ReviewError('sensitive_material','Sensitive configuration overlaps review material; request was not sent.')
        request=ReviewRequest(instructions,encode(material),json.loads((ROOT/'ai/response.schema.json').read_text()),model,key,timeout)
        return material,instructions,request

    def _binding(self,request):
        # Credential fingerprint is memory-only; never stored in public metadata.
        return sha(encode([request.material_json,request.instructions,request.response_schema,request.model,request.timeout_seconds,sha(request.api_key),os.environ.get('TRUST_REVIEW_WORKSPACE_ID')]))

    def preflight(self,run_id):
        if not self.lock.acquire(blocking=False):raise ReviewError('busy','Another request is active.',409)
        try:
            if self.active_worker is not None and self.active_worker.is_alive():raise ReviewError('busy','Previous provider request is still terminating.',409)
            material,instructions,request=self._request(run_id)
            provider=self.env['TRUST_REVIEW_PROVIDER']
            if provider!='anthropic':raise ReviewError('preflight_unavailable','This provider has no configured token/cost preflight.',409)
            try:public=self.registry[provider].preflight(request)
            except AdapterFailure as error:
                if request.api_key in encode([error.message,error.metadata]):raise ReviewError('service_error','Anthropic preflight failed; sensitive details were discarded.',502)
                raise ReviewError(error.code,error.message,422,details=error.metadata)
            except TimeoutError:raise ReviewError('timeout','Anthropic token/cost preflight timed out. No generation sent.',504)
            quote_id='quote-'+uuid.uuid4().hex
            public.update(quoteId=quote_id,evidenceRunId=run_id,inputSha256=sha(encode(material)),instructionsSha256=sha(instructions),createdAt=now(),expiresInSeconds=600,generationSent=False)
            if request.api_key in encode(public):raise ReviewError('invalid_response','Sensitive preflight response rejected.')
            self.quotes={key:value for key,value in self.quotes.items() if value['expires']>time.monotonic() and not value['used']}
            self.quotes[quote_id]=dict(binding=self._binding(request),public=public,expires=time.monotonic()+600,used=False)
            return public
        finally:self.lock.release()

    def _store(self,record,material=None,instructions=None):
        folder=self.output/record['reviewId'];folder.mkdir(parents=True,exist_ok=False)
        if material is not None:(folder/'input.json').write_text(encode(material)+'\n')
        if instructions is not None:(folder/'instructions.txt').write_text(instructions)
        temp=folder/'review.tmp';temp.write_text(json.dumps(record,indent=2)+'\n');temp.replace(folder/'review.json')

    def execute(self,run_id,quote_id=None):
        if not self.lock.acquire(blocking=False):raise ReviewError('busy','Another review request is still active.',409)
        try:
            if self.active_worker is not None and self.active_worker.is_alive():raise ReviewError('busy','A timed-out provider request is still terminating.',409)
            return self._execute(run_id,quote_id)
        finally:self.lock.release()

    def _execute(self,run_id,quote_id=None):
        if not isinstance(run_id,str) or not re.fullmatch(r'[0-9TZ-]+-[0-9a-f]{8}',run_id):raise ReviewError('invalid_run','Choose a valid evidence run.',400)
        review_id='ai-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:12]
        record=dict(schemaVersion=1,kind='issue-2283-ai-review',reviewId=review_id,reviewVersion=review_id,
            evidenceRunId=run_id,base=SHA['base'],head=SHA['head'],startedAt=now(),finishedAt=None,
            status='not_run',service=None,model=None,inputSha256=None,instructionsSha256=None,
            responseSchemaSha256=sha((ROOT/'ai/response.schema.json').read_bytes()),evidenceAssisted=True,blindTest=False)
        material=None;instructions=None
        try:
            material,instructions,request=self._request(run_id)
            record.update(inputSha256=sha(encode(material)),instructionsSha256=sha(instructions))
            provider=self.env['TRUST_REVIEW_PROVIDER'];model=request.model;key=request.api_key
            record.update(service=provider,model=model,requestedService=provider,requestedModel=model,status='failed')
            if provider=='anthropic':
                quote=self.quotes.get(quote_id) if isinstance(quote_id,str) else None
                if not quote or quote['used'] or quote['expires']<=time.monotonic() or quote['binding']!=self._binding(request):
                    raise ReviewError('preflight_required','Check tokens and cost for this exact input/settings first. Quotes expire in 10 minutes and can be used only once.',409)
                quote['used']=True
                record['preflight']=dict(quote['public'])
            # The boundary receives data only. No tools, subprocess callback or file handle.
            # Adapter must enforce transport timeouts. Late replies are discarded.
            results=queue.Queue(maxsize=1)
            def invoke():
                try:results.put((True,self.registry[provider].review(request,preflight=record['preflight']) if provider=='anthropic' else self.registry[provider].review(request)))
                except AdapterFailure as error:results.put((False,error))
                except TimeoutError:results.put(('timeout',None))
                except Exception:results.put((False,None)) # Never log provider exceptions: they may include credentials.
            worker=threading.Thread(target=invoke,daemon=True);self.active_worker=worker;worker.start()
            try:ok,reply=results.get(timeout=request.timeout_seconds)
            except queue.Empty:raise ReviewError('timeout','Model service timed out; no review result was accepted.',504)
            if ok == 'timeout':raise ReviewError('timeout','Model service timed out; no review result was accepted.',504)
            if not ok:
                if isinstance(reply,AdapterFailure) and key not in encode([reply.message,reply.metadata]):
                    record['providerTransport']=reply.metadata
                    raise ReviewError(reply.code,reply.message,502)
                raise ReviewError('service_error','Model service failed; provider error details are intentionally not logged.',502)
            if not isinstance(reply,ReviewReply) or any(not isinstance(value,str) or not value.strip() or len(value)>200 for value in (reply.service,reply.model)):raise ReviewError('invalid_response','Adapter returned invalid reply metadata.')
            try:reply_text=encode([reply.service,reply.model,reply.output,reply.provider_request_id,reply.metadata])
            except (TypeError,ValueError):raise ReviewError('invalid_response','Adapter returned a non-JSON reply.')
            if key and key in reply_text:raise ReviewError('invalid_response','Provider reply contained sensitive material and was rejected.')
            if reply.metadata:
                record['providerMetadata']=reply.metadata
                record['providerRequestId']=reply.provider_request_id
                if reply.metadata.get('stopReason')!='end_turn':
                    raise ReviewError('incomplete_response','Anthropic stopped without a complete end_turn (refusal, output/context limit or unexpected stop). Usage is recorded when available; no retry was made.')
            output,references=validate_response(reply.output,material)
            record.update(status='completed',service=reply.service,model=reply.model,result=output,referenceChecks=references)
            # Only adapter-whitelisted IDs/counters are persisted; no thinking text or headers.
        except ReviewError as error:
            record.update(status='not_run' if error.code in ('missing_configuration','invalid_run','material_unavailable','material_integrity','material_too_large','sensitive_material','preflight_required') else 'failed',error=dict(code=error.code,message=error.message))
            record['finishedAt']=now();self._store(record,material,instructions)
            return record,error.http_status
        except Exception:
            record.update(status='failed',error=dict(code='internal_error',message='Review could not be completed; no result was accepted.'))
            record['finishedAt']=now();self._store(record,material,instructions)
            return record,500
        record['finishedAt']=now();self._store(record,material,instructions)
        return record,201
