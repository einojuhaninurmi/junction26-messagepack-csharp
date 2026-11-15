"""Collect only the frozen issue #2283 comparison; no AI or approval actions."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import uuid
import re

sys.path.insert(0, str(Path(__file__).resolve().parent / 'collector'))
from run_contract import parse_trx, parse_probe, compare_probe, validate_run

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
RUNS = ROOT / 'runs'
TEST_ID = 'metadata-regressions-v1'
PROBE_ID = 'diagnostic-probe-v1'
OLD = '<MicrosoftCodeAnalysisVersion Condition="\'$(IsAnalyzerProject)\'==\'true\'">4.12.0</MicrosoftCodeAnalysisVersion>'
NEW = OLD.replace('4.12.0','4.11.0')

def now(): return datetime.now(timezone.utc).isoformat()
def digest(data): return hashlib.sha256(data).hexdigest()

class Collector:
    def __init__(self, dotnet='dotnet', timeout=600):
        frozen = json.loads((ROOT/'report.json').read_text())
        self.manifest = json.loads((ROOT/'collector/checks.json').read_text())
        self.dotnet, self.timeout = dotnet, timeout
        self.id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
        self.output = RUNS/self.id
        self.output.mkdir(parents=True)
        self.report = dict(schemaVersion=1,kind='issue-2283-evidence-run',runId=self.id,startedAt=now(),finishedAt='',base=frozen['change']['base'],head=frozen['change']['head'],parentReviewVersion=frozen['reviewVersion'],reviewVersion=frozen['reviewVersion']+'+run.'+self.id,checkVersion=self.manifest['version'],status='incomplete',commands=[],versions={},artifacts=[],contradictions=[],inputs={},tools={'python':sys.version,'platform':platform.platform()},limits=['Targeted regressions and diagnostic probe only; no full solution suite, runtime round-trip, Windows or NativeAOT validation.','Both sides require the separate conditional Roslyn 4.11.0 correction.','Base uses the head test-file overlay. This is not an untouched-base build.','No AI assessment or human approval is performed.'])
        for side in ('base','head'):
            self.report['versions'][side] = dict(commit=self.report[side],checks={k:dict(status='not_run',reason='Prerequisites not yet executed',commandIds=[]) for k in (TEST_ID,PROBE_ID)})
        for name, data in [('inputs/checks.json',(ROOT/'collector/checks.json').read_bytes()),('inputs/Probe.cs',(REPO/self.manifest['probeSource']).read_bytes()),('inputs/collector.py',Path(__file__).read_bytes()),('inputs/run_contract.py',(ROOT/'collector/run_contract.py').read_bytes())]: self.artifact(name,data)

    def artifact(self, name, data):
        path = self.output/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data if isinstance(data,bytes) else data.encode())
        if name not in self.report['artifacts']: self.report['artifacts'].append(name)
        return path

    def command(self, label, argv, cwd, test=False):
        ident = f'{len(self.report["commands"])+1:02d}-{label}'
        log = 'commands/'+ident+'.log'
        item = dict(id=ident,argv=[str(a) for a in argv],cwd=str(cwd),startedAt=now(),finishedAt='',exitCode=None,status='environment_blocked',log=log)
        self.report['commands'].append(item)
        print(f'[{self.id}] {label}',flush=True)
        try:
            result = subprocess.run(item['argv'],cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=self.timeout)
            output = result.stdout
            item['exitCode'] = result.returncode
            item['status'] = 'passed' if result.returncode == 0 else 'test_failed' if test else 'environment_blocked'
        except (OSError,subprocess.TimeoutExpired) as error:
            output = getattr(error,'stdout',None) or b''
            if isinstance(output,str): output=output.encode()
            output += ('\nEXECUTION ERROR: '+str(error)).encode()
            item['executionError'] = str(error)
        item['finishedAt']=now()
        self.artifact(log,output)
        return item,output.decode(errors='replace')

    def require(self,label,argv,cwd):
        cmd,text=self.command(label,argv,cwd)
        if cmd['status'] != 'passed': raise RuntimeError(f'{label} failed: see {cmd["log"]}')
        return text

    def collect_side(self,side,tree,temporary,test_bytes,probe_bytes):
        v=self.report['versions'][side]
        try:
            actual = self.require(side+'-commit',['git','rev-parse','HEAD'],tree).strip()
            if actual != self.report[side]: raise RuntimeError('Worktree HEAD mismatch')
            path=tree/'Directory.Packages.props'
            text=path.read_text()
            if text.count(OLD) != 1: raise RuntimeError('Expected exactly one unmodified conditional Roslyn 4.12.0 property')
            path.write_text(text.replace(OLD,NEW))
            (tree/self.manifest['testFile']).write_bytes(test_bytes)
            patch=self.require(side+'-setup-diff',['git','diff','--','Directory.Packages.props'],tree)
            self.artifact(side+'/setup.patch',patch)
            self.artifact(side+'/test-overlay.patch',self.require(side+'-test-diff',['git','diff','--',self.manifest['testFile']],tree))
            v['inputHashes']=dict(testFile=digest((tree/self.manifest['testFile']).read_bytes()),probeSource=digest(probe_bytes),setupPatch=digest(patch.encode()))
            info = self.require(side+'-sdk-info',[self.dotnet,'--info'],tree)
            v['tools'] = {'dotnetInfo':info}
            match = re.search(r'Base Path:\s*([^\r\n]+)', info)
            if not match: raise RuntimeError('Cannot locate selected SDK compiler')
            compiler = Path(match.group(1).strip())/'Roslyn/bincore/csc.dll'
            v['tools']['compiler'] = self.require(side+'-compiler-version',[self.dotnet,compiler,'-version'],tree).strip()
            self.require(side+'-build',[self.dotnet,'build',self.manifest['project'],'-c','Debug'],tree)
            expected=self.manifest['tests']
            filter_value='|'.join('FullyQualifiedName='+name for name in expected)
            common=[self.dotnet,'test',self.manifest['project'],'-c','Debug','--no-build','--no-restore','--filter',filter_value]
            discovery,discovery_text=self.command(side+'-discover',common+['--list-tests'],tree)
            if discovery['exitCode'] != 0 or any(name not in discovery_text for name in expected):
                v['checks'][TEST_ID]=dict(status='environment_blocked',reason='Discovery did not confirm all three required test identities',commandIds=[discovery['id']])
            else:
                result_dir=self.output/side/'results';result_dir.mkdir(parents=True,exist_ok=True)
                cmd,test_text=self.command(side+'-regressions',common+['--logger','trx;LogFileName=targeted.trx','--results-directory',result_dir],tree,test=True)
                check=dict(status='environment_blocked',reason='Missing or invalid TRX',commandIds=[discovery['id'],cmd['id']])
                trx=result_dir/'targeted.trx'
                if trx.exists():
                    self.artifact(side+'/results/targeted.trx',trx.read_bytes())
                    try:
                        executed=parse_trx(trx,expected)
                        failed=sum(t['outcome']=='Failed' for t in executed)
                        if cmd['exitCode'] not in (0,1) or (cmd['exitCode']==0) != (failed==0): raise ValueError('Exit code conflicts with test outcomes')
                        check.update(status='test_failed' if failed else 'passed',reason='Exactly the same three tests executed',tests=executed,passed=len(executed)-failed,failed=failed)
                        # Confirm the previously observed exception, not merely a red test result.
                        matches=(failed==3 and all(x in test_text for x in ('AD0001','CS8785','IndexOutOfRangeException'))) if side=='base' else failed==0
                        check['matchesPreviousObservation']=matches
                        if not matches:self.report['contradictions'].append(side+': regression outcomes differ from recorded observations')
                    except Exception as error:
                        check['reason']=str(error)
                v['checks'][TEST_ID]=check
            # Build an identical probe project outside repository imports, against this side's fresh binaries.
            probe_dir=temporary/(side+'-probe');probe_dir.mkdir()
            (probe_dir/'Program.cs').write_bytes(probe_bytes)
            names=['Microsoft.CodeAnalysis','Microsoft.CodeAnalysis.CSharp','MessagePack.SourceGenerator','MessagePack','MessagePack.Annotations']
            project='<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable></PropertyGroup><ItemGroup>'+''.join(f'<Reference Include="{n}"><HintPath>$(EvidenceBin)/{n}.dll</HintPath></Reference>' for n in names)+'</ItemGroup></Project>'
            (probe_dir/'Probe.csproj').write_text(project)
            self.artifact('inputs/Probe.csproj',project)
            v['inputHashes']['probeProject']=digest(project.encode())
            bins=tree/'bin/MessagePack.SourceGenerator.Tests/Debug/net8.0'
            cmd,_=self.command(side+'-probe-build',[self.dotnet,'build',probe_dir/'Probe.csproj','-c','Debug',f'-p:EvidenceBin={bins}'],tree)
            if cmd['exitCode'] != 0:
                v['checks'][PROBE_ID]=dict(status='environment_blocked',reason='Probe harness build failed',commandIds=[cmd['id']])
            else:
                cmd,output=self.command(side+'-probe',[self.dotnet,probe_dir/'bin/Debug/net8.0/Probe.dll'],tree)
                check=dict(status='environment_blocked',reason='Probe did not complete',commandIds=[cmd['id']])
                if cmd['exitCode']==0:
                    try:
                        cases=parse_probe(output,self.manifest['probeCases'])
                        comparisons=compare_probe(cases,side)
                        check.update(status='observed',reason='All five probe cases completed; harness exit is not a product verdict',cases=cases,comparisons=comparisons,matchesPreviousObservation=all(c['matches'] for c in comparisons))
                        for c in comparisons:
                            if not c['matches']:self.report['contradictions'].append(side+': '+c['id']+' differs from recorded observations')
                    except ValueError as error:check['reason']=str(error)
                v['checks'][PROBE_ID]=check
            self.artifact(side+'/worktree.patch',self.require(side+'-final-diff',['git','diff','--binary'],tree))
        except Exception as error:
            v['environmentError']=str(error)
            for check in v['checks'].values():
                if check['status']=='not_run':check['reason']='Not executed: '+str(error)

    def run(self):
        trees=[]
        try:
            self.require('git-version',['git','--version'],REPO)
            for side in ('base','head'):
                actual=self.require(side+'-resolve',['git','rev-parse',self.report[side]+'^{commit}'],REPO).strip()
                if actual != self.report[side]:raise RuntimeError('Commit resolution mismatch')
            self.require('parent-check',['git','merge-base','--is-ancestor',self.report['base'],self.report['head']],REPO)
            cmd,_=self.command('test-source',['git','show',self.report['head']+':'+self.manifest['testFile']],REPO)
            if cmd['exitCode'] != 0:raise RuntimeError('Cannot read shared test source')
            test_bytes=(self.output/cmd['log']).read_bytes()
            self.artifact('inputs/GenericsFormatterTests.cs',test_bytes)
            probe_bytes=(self.output/'inputs/Probe.cs').read_bytes()
            self.report['inputs']=dict(testSourceCommit=self.report['head'],testFileSha256=digest(test_bytes),probeSha256=digest(probe_bytes),manifestSha256=digest((ROOT/'collector/checks.json').read_bytes()),setupChange='Only IsAnalyzerProject conditional MicrosoftCodeAnalysisVersion: 4.12.0 -> 4.11.0')
            with tempfile.TemporaryDirectory(prefix='earned-trust-2283-') as folder:
                temporary=Path(folder)
                try:
                    for side in ('base','head'):
                        tree=temporary/side
                        # Register the path before add so cleanup also handles partial failures.
                        trees.append(tree)
                        self.require(side+'-worktree-add',['git','worktree','add','--detach',str(tree),self.report[side]],REPO)
                        self.collect_side(side,tree,temporary,test_bytes,probe_bytes)
                    hashes=[self.report['versions'][side].get('inputHashes') for side in ('base','head')]
                    self.report['inputs']['identicalAcrossVersions']=hashes[0] is not None and hashes[0]==hashes[1] and 'probeProject' in hashes[0]
                    if all(h and 'probeProject' in h for h in hashes) and hashes[0] != hashes[1]:self.report['contradictions'].append('Harness/setup inputs differ between versions')
                finally:
                    for tree in trees:
                        cmd,_=self.command('cleanup-'+tree.name,['git','worktree','remove','--force',str(tree)],REPO)
                        if cmd['exitCode'] != 0:self.report.setdefault('cleanupErrors',[]).append(cmd['log'])
        except Exception as error:self.report['environmentError']=str(error)
        checks=[c for v in self.report['versions'].values() for c in v['checks'].values()]
        if any(c['status'] in ('not_run','environment_blocked') for c in checks) or self.report.get('environmentError') or self.report.get('cleanupErrors'):
            self.report['status']='environment_blocked'
        elif self.report['contradictions']:self.report['status']='contradiction'
        else:self.report['status']='reproduced'
        self.report['finishedAt']=now()
        validate_run(self.report)
        target=self.output/'report.json'
        temp=target.with_suffix('.tmp');temp.write_text(json.dumps(self.report,indent=2)+'\n');temp.replace(target)
        print(f'Run {self.id}: {self.report["status"]}\nReport: {target}',flush=True)
        return 0 if self.report['status']=='reproduced' else 1 if self.report['status']=='contradiction' else 2

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dotnet',default='dotnet',help='dotnet executable; override to exercise environment failure handling')
    parser.add_argument('--timeout',type=int,default=600,help='Maximum seconds per command')
    args=parser.parse_args()
    sys.exit(Collector(args.dotnet,args.timeout).run())
