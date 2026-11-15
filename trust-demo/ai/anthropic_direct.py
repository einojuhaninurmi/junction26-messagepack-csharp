"""Direct Anthropic Messages API, version 2026-10-21. No SDK retries/proxies.
Official sources and pricing date: ANTHROPIC.md. All network tests inject transport.
"""
import copy
import json
import os
import re
import socket
import ssl
import sys
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler, ProxyHandler
from .contracts import ReviewReply, AdapterFailure

MODEL='claude-sonnet-5-5'
API_VERSION='2026-10-21'
BASE_URL='https://api.anthropic.com'
MAX_OUTPUT=8192
CONTEXT=1_000_000
MARGIN=4096
INPUT_RATE=2.0
OUTPUT_RATE=10.0
MAX_ESTIMATED_USD=1.0

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def verified_tls_context():
    context=ssl.create_default_context()
    # python.org macOS installs can have no OpenSSL CA roots. Use the existing
    # OS bundle only in that exact case; honor explicit CA configuration.
    if (sys.platform=='darwin' and context.cert_store_stats()['x509_ca']==0
            and not any(os.environ.get(k) for k in ('SSL_CERT_FILE','SSL_CERT_DIR'))
            and Path('/etc/ssl/cert.pem').is_file()):
        context.load_verify_locations(cafile='/etc/ssl/cert.pem')
    return context


def network_failure(reason):
    if isinstance(reason,ssl.SSLCertVerificationError):
        metadata={'category':'tls_certificate','verificationEnabled':True}
        if type(getattr(reason,'verify_code',None))is int:metadata['verifyCode']=reason.verify_code
        return AdapterFailure('tls_certificate_error','TLS certificate verification failed. Check the Python CA store or explicit CA configuration; verification was not disabled.',metadata)
    if isinstance(reason,socket.gaierror):return AdapterFailure('dns_error','DNS lookup for the direct Anthropic endpoint failed. No retry was made.',{'category':'dns'})
    if isinstance(reason,TimeoutError):return TimeoutError('Direct Anthropic connection timed out; no retry was made.')
    if isinstance(reason,ssl.SSLError):return AdapterFailure('tls_error','TLS handshake failed. Certificate verification remains enabled.',{'category':'tls'})
    return AdapterFailure('network_error','Direct Anthropic connection failed before an HTTP response. Check connectivity/firewall; ambient proxies are deliberately not used.',{'category':'network','ambientProxyUsed':False})


def http_failure(error):
    # Read only bounded error JSON for classification. Never expose raw text,
    # headers or messages: the provider might echo credentials or request data.
    provider_type=None;billing=False
    try:
        raw=error.read(32769)
        if len(raw)<=32768:
            obj=json.loads(raw).get('error',{})
            known={'invalid_request_error','authentication_error','billing_error','permission_error','not_found_error','rate_limit_error','overloaded_error','api_error','timeout_error'}
            if obj.get('type') in known:provider_type=obj['type']
            text=obj.get('message','')
            billing=isinstance(text,str) and any(marker in text.casefold() for marker in ('credit balance','insufficient credit','spend limit','billing','payment information'))
    except (ValueError,TypeError,AttributeError,OSError):pass
    status=error.code
    if status==401:code,message='authentication_error','Anthropic rejected authentication (HTTP 401). Re-enter the direct API key; do not share it.'
    elif status==402 or (status==400 and (billing or provider_type=='billing_error')):code,message='billing_error',f'Anthropic reported a billing/credit/spend-limit problem (HTTP {status}). Check Claude Console.'
    elif status==403:code,message='permission_error','Anthropic denied access (HTTP 403). Check workspace and resource permissions.'
    elif status==404:code,message='model_unavailable','Anthropic resource/model was not found (HTTP 404). Account model availability is not established.'
    elif status==400:code,message='invalid_request','Anthropic rejected the request (HTTP 400). A spend-limit rejection is also possible when no specific billing signal is provided.'
    elif status in (408,504):code,message='timeout','Anthropic reported a request timeout. No automatic retry was made.'
    elif status==429:code,message='rate_limit_error','Anthropic rate/spend limit reached (HTTP 429). No automatic retry was made.'
    else:code,message='service_error',f'Anthropic returned HTTP {status}. No automatic retry was made.'
    metadata={'requestId':safe_id(error.headers.get('request-id')),'httpStatus':status,'category':code}
    if provider_type:metadata['providerErrorType']=provider_type
    return AdapterFailure(code,message,metadata)


class DirectTransport:
    def __call__(self,method,path,body,key,timeout):
        # Fixed direct origin, no ambient proxy, no redirects, exactly one attempt.
        headers={'Authorization':'Bearer '+key,'anthropic-version':API_VERSION,'Content-Type':'application/json'}
        workspace=os.environ.get('TRUST_REVIEW_WORKSPACE_ID')
        if workspace:
            if not re.fullmatch(r'wrkspc_[A-Za-z0-9]+',workspace):raise AdapterFailure('configuration_error','Invalid Anthropic workspace identifier.')
            headers['anthropic-workspace-id']=workspace
        request=Request(BASE_URL+path,data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None,headers=headers,method=method)
        try:
            opener=build_opener(ProxyHandler({}),HTTPSHandler(context=verified_tls_context()),NoRedirect())
            with opener.open(request,timeout=timeout) as response:
                payload=response.read(2_000_001)
                if len(payload)>2_000_000:raise AdapterFailure('invalid_response','Anthropic response exceeded the local size limit.')
                try:data=json.loads(payload)
                except (ValueError,UnicodeError):raise AdapterFailure('invalid_response','Anthropic returned invalid JSON.')
                return data,{name.lower():value for name,value in response.headers.items()}
        except HTTPError as error:
            raise http_failure(error) from None
        except URLError as error:
            raise network_failure(error.reason) from None
        except (TimeoutError,ssl.SSLError,OSError) as error:
            raise network_failure(error) from None



def safe_id(value):
    return value if isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,200}',value) else None


def api_schema(schema):
    """Documented raw-schema adaptation. Original constraints remain locally enforced."""
    result={};removed=[]
    for key,value in schema.items():
        if key=='$schema':continue
        if key in ('minLength','maxLength','maxItems','minimum','maximum'):
            removed.append(f'{key}={value}');continue
        if key=='properties':result[key]={name:api_schema(spec) for name,spec in value.items()}
        elif key=='items':result[key]=api_schema(value)
        else:result[key]=copy.deepcopy(value)
    if removed:result['description']=(result.get('description','')+' Local validation also requires '+', '.join(removed)+'.').strip()
    return result


def body_for(request,model):
    return dict(model=model,max_tokens=MAX_OUTPUT,system=request.instructions,
        messages=[{'role':'user','content':[{'type':'text','text':request.material_json}]}],
        output_config={'effort':'medium','format':{'type':'json_schema','schema':api_schema(request.response_schema)}},
        thinking={'type':'adaptive'},stream=False,service_tier='standard_only')


def usage_projection(raw):
    if not isinstance(raw,dict):return {}
    result={}
    for key in ('input_tokens','output_tokens','cache_creation_input_tokens','cache_read_input_tokens'):
        if key in raw:
            if type(raw[key])is not int or raw[key]<0:raise AdapterFailure('invalid_response','Anthropic returned invalid usage counters.')
            result[key]=raw[key]
    for key,fields in [('cache_creation',('ephemeral_1h_input_tokens','ephemeral_5m_input_tokens')),('output_tokens_details',('thinking_tokens',))]:
        if isinstance(raw.get(key),dict):
            result[key]={field:raw[key][field] for field in fields if type(raw[key].get(field))is int and raw[key][field]>=0}
    for key in ('inference_geo','service_tier','speed'):
        if safe_id(raw.get(key)):result[key]=raw[key]
    return result


def actual_cost(usage):
    if 'input_tokens' not in usage or 'output_tokens' not in usage:return None
    caches=usage.get('cache_creation',{})
    creation=usage.get('cache_creation_input_tokens',0)
    five=caches.get('ephemeral_5m_input_tokens',0);hour=caches.get('ephemeral_1h_input_tokens',0)
    if creation != five+hour:return None
    return round((usage['input_tokens']*INPUT_RATE+usage['output_tokens']*OUTPUT_RATE+usage.get('cache_read_input_tokens',0)*.1+five*2.5+hour*4)/1_000_000,8)

class AnthropicDirect:
    def __init__(self,transport=None):self.transport=transport or DirectTransport()
    def preflight(self,request):
        if request.model!=MODEL:raise AdapterFailure('configuration_error','This issue demo supports only the documented claude-sonnet-5-5 model; no fallback is automatic.')
        deadline=time.monotonic()+request.timeout_seconds
        def remaining():
            value=deadline-time.monotonic()
            if value<=0:raise TimeoutError('Anthropic preflight timed out.')
            return value
        info,model_headers=self.transport('GET','/v1/models/'+MODEL,None,request.api_key,remaining())
        if not isinstance(info,dict):raise AdapterFailure('invalid_response','Models API returned no model object.')
        resolved=info.get('id')
        if not safe_id(resolved) or not (resolved==MODEL or resolved.startswith(MODEL+'-')):raise AdapterFailure('invalid_response','Unexpected resolved Anthropic model identifier.')
        if info.get('capabilities',{}).get('structured_outputs',{}).get('supported') is not True:raise AdapterFailure('unsupported_model','The selected account/model did not report structured-output support.')
        capacity=info.get('max_input_tokens');output_limit=info.get('max_tokens')
        if type(capacity)is not int or capacity<=0 or type(output_limit)is not int or output_limit<MAX_OUTPUT:raise AdapterFailure('unsupported_model','Model API did not provide usable token limits; refusing a paid call.')
        body=body_for(request,resolved)
        count_body={key:value for key,value in body.items() if key not in ('max_tokens','stream','service_tier')}
        counted,count_headers=self.transport('POST','/v1/messages/count_tokens',count_body,request.api_key,remaining())
        if not isinstance(counted,dict):raise AdapterFailure('invalid_response','Token counter returned no count object.')
        count=counted.get('input_tokens')
        if type(count)is not int or count<=0:raise AdapterFailure('invalid_response','Token counter did not return a valid positive count.')
        capacity=min(capacity,CONTEXT)
        if count+MAX_OUTPUT+MARGIN>capacity:raise AdapterFailure('context_exceeded','Full counted input plus output reservation and safety margin exceeds context capacity. Nothing was truncated or generated.')
        estimate=(count*INPUT_RATE+MAX_OUTPUT*OUTPUT_RATE)/1_000_000
        conservative=((count+MARGIN)*INPUT_RATE+MAX_OUTPUT*OUTPUT_RATE)/1_000_000
        if conservative>MAX_ESTIMATED_USD:raise AdapterFailure('cost_limit','Counted request exceeds the demo USD 1.00 estimate limit; no generation was sent.')
        return dict(service='anthropic',requestedModel=MODEL,resolvedModel=resolved,apiVersion=API_VERSION,inputTokens=count,
            contextCapacity=capacity,maxOutputTokens=MAX_OUTPUT,safetyMarginTokens=MARGIN,
            estimatedUSDWithMaxOutput=round(estimate,8),estimatedUSDWithMargin=round(conservative,8),estimateLimitUSD=MAX_ESTIMATED_USD,
            ratesUSDPerMillion={'input':INPUT_RATE,'output':OUTPUT_RATE},pricingCheckedOn='2026-11-15',
            modelRequestId=safe_id(model_headers.get('request-id')),countRequestId=safe_id(count_headers.get('request-id')),
            note='Token-count estimate, not an invoice. No generation yet. Output reservation includes thinking. No caching, batch or fast-mode request.')
    def review(self,request,preflight=None):
        if not preflight:raise AdapterFailure('preflight_required','Count tokens and inspect cost before generation.')
        body=body_for(request,preflight['resolvedModel'])
        data,headers=self.transport('POST','/v1/messages',body,request.api_key,request.timeout_seconds)
        if not isinstance(data,dict):raise AdapterFailure('invalid_response','Anthropic returned a non-object response.',{'requestId':safe_id(headers.get('request-id'))})
        usage=usage_projection(data.get('usage'))
        metadata=dict(model=safe_id(data.get('model')),requestId=safe_id(headers.get('request-id')),messageId=safe_id(data.get('id')),usage=usage,stopReason=safe_id(data.get('stop_reason')),actualCostEstimateUSD=actual_cost(usage))
        if data.get('model')!=preflight['resolvedModel']:raise AdapterFailure('invalid_response','Returned model does not match the counted model.',metadata)
        if not isinstance(data.get('content'),list):raise AdapterFailure('invalid_response','Anthropic returned no content array.',metadata)
        if any(not isinstance(block,dict) or block.get('type') not in ('text','thinking','redacted_thinking') or (block.get('type')=='text' and not isinstance(block.get('text'),str)) for block in data['content']):
            raise AdapterFailure('invalid_response','Unexpected tool or non-text response; nothing was executed.',metadata)
        text=''.join(block.get('text','') for block in data['content'] if block.get('type')=='text')
        return ReviewReply('anthropic',data['model'],text,metadata['requestId'],metadata)
