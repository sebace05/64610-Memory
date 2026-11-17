"""Offline transport evidence only; no real tokenizer, model, or Modal calls."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from game_memory import memory_probe as mp
from game_memory import memory_probe_modal as tr
from game_memory.transformers_model import TransformersConfig

# Reuse the accepted synthetic model, rather than copy its audit suite.
spec = importlib.util.spec_from_file_location('accepted_probe_fixtures',Path(__file__).with_name('test_memory_probe.py'))
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
PACKAGE = Path('artifacts/memory-probe-v1/package-v2')


def dump(path,value):
    path.write_text(json.dumps(value))


@pytest.fixture
def packet(tmp_path):
    packet = tmp_path/'packet'; packet.mkdir()
    (packet/'worker_transport.py').write_text('synthetic fixture transport')
    plan = dict(stage='s1',package_digest=tr.PACKAGE_DIGEST,run_id='fixture',remote_output=str(tmp_path/'remote'))
    # Runtime paths are deliberately synthetic; verification uses production-style path below.
    plan['remote_output']='/results/fixture'
    dump(packet/'plan.json',plan)
    dump(packet/'transport-manifest.json',dict(plan_sha256=tr.digest(plan),files={'worker_transport.py':tr.sha(packet/'worker_transport.py')}))
    return packet,plan


def test_package_archive_and_current_source_verified():
    assert tr.verify_package(PACKAGE,Path('.'))['manifest_sha256']==tr.PACKAGE_DIGEST


@pytest.mark.parametrize('name',['manifest.json','source.zip','splits/dev.json'])
def test_bad_package_fails_closed(tmp_path,name):
    target=tmp_path/'package'; shutil.copytree(PACKAGE,target)
    with (target/name).open('ab') as f:f.write(b'bad')
    with pytest.raises((ValueError,json.JSONDecodeError)):
        tr.verify_package(target)


def test_archive_cannot_be_replaced_by_altered_ledger(tmp_path):
    target=tmp_path/'package'; shutil.copytree(PACKAGE,target)
    (target/'source.zip').write_bytes(b'bad')
    ledger=tr.read(target/'package-files-sha256.json'); ledger['source.zip']=tr.sha(target/'source.zip');dump(target/'package-files-sha256.json',ledger)
    with pytest.raises(ValueError,match='archive hash'):
        tr.verify_package(target)


def test_current_source_differs_before_import(tmp_path):
    with pytest.raises(FileNotFoundError):tr.verify_package(PACKAGE,tmp_path)


def test_authorization_and_duplicate_reservation(packet,tmp_path):
    p,plan=packet; auth=tmp_path/'authorization'
    auth.write_text('TEMPLATE — NOT EXECUTION AUTHORIZATION\n'+tr.AUTHORIZATION)
    with pytest.raises(ValueError,match='authorization'):tr.reserve(p,plan,auth)
    assert not (p/'submission-reservation.json').exists()
    auth.write_text(tr.AUTHORIZATION)
    tr.reserve(p,plan,auth)
    with pytest.raises(FileExistsError):tr.reserve(p,plan,auth)


@pytest.mark.parametrize('change',['plan','transport'])
def test_altered_plan_or_transport(packet,change):
    p,plan=packet
    if change=='plan':plan={**plan,'stage':'s2'}
    else:(p/'worker_transport.py').write_text('altered')
    with pytest.raises(ValueError,match='hash'):tr.verify_packet(p,plan)


def test_import_help_and_no_authorization_have_no_optional_imports(tmp_path):
    code="""import sys
from game_memory import memory_probe_modal as tr
assert 'modal' not in sys.modules and 'transformers' not in sys.modules and 'torch' not in sys.modules
sys.argv=['launcher','--help']
tr.main()
"""
    result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
    assert result.returncode==0 and 'launch' in result.stdout
    result=subprocess.run([sys.executable,'-c',code.replace("'--help'","'launch'")],capture_output=True,text=True)
    assert result.returncode!=0 and '--authorization is required' in result.stderr


def test_unknown_submission_never_loads_submit_boundary(packet,monkeypatch):
    p,_=packet
    monkeypatch.setattr(tr,'sdk',lambda plan:SimpleNamespace())
    with pytest.raises(RuntimeError,match='never resubmit'):tr.inspect_call(p)


def test_request_1071_refused_and_delegation_unchanged():
    calls=[]; sentinel=object(); messages=object(); labels=object()
    model=SimpleNamespace(metadata={'is_fake':True},count_tokens=lambda t:7,
        generate=lambda m,**kw: calls.append((m,kw)) or sentinel,
        score_choices=lambda m,**kw:calls.append((m,kw)) or sentinel)
    guard=tr.RequestLimit(model,100,lambda:0)
    assert guard.metadata is model.metadata and guard.count_tokens('x')==7
    assert guard.generate(messages,purpose='memory_repair') is sentinel
    for _ in range(1069):assert guard.score_choices(messages,labels=labels) is sentinel
    assert calls[0]==(messages,{'purpose':'memory_repair'}) and calls[-1]==(messages,{'labels':labels})
    with pytest.raises(RuntimeError,match='ceiling'):guard.score_choices(messages,labels=labels)
    assert len(calls)==1070
    guard=tr.RequestLimit(model,0,lambda:0)
    with pytest.raises(TimeoutError):guard.generate(messages,purpose='memory')
    assert guard.calls==0


@pytest.fixture
def cached(tmp_path):
    cache=tmp_path/'cache';cache.mkdir()
    dump(cache/'config.json',dict(model_type='qwen3',vocab_size=1000,max_position_embeddings=8192))
    for n in ['tokenizer.json','tokenizer_config.json','model.safetensors']:(cache/n).write_text('synthetic')
    return cache


@pytest.mark.parametrize('fault',['runtime','config','tokenizer','weights','empty_index'])
def test_assets_fail_before_tokenizer_or_weights(cached,fault):
    runtime={**tr.RUNTIME,'gpu':'NVIDIA A10G'}
    if fault=='runtime':runtime['torch_version']='wrong'
    elif fault=='config':dump(cached/'config.json',{'vocab_size':1000})
    elif fault=='tokenizer':(cached/'tokenizer.json').unlink()
    elif fault=='weights':(cached/'model.safetensors').write_text('')
    else:dump(cached/'model.safetensors.index.json',{'weight_map':{}})
    with pytest.raises((ValueError,RuntimeError)):
        tr.runtime_and_cache(SimpleNamespace(runtime_metadata=lambda _:runtime),None,cached)


def test_cached_config_vocab_is_recorded(cached):
    identity,cfg=tr.runtime_and_cache(SimpleNamespace(runtime_metadata=lambda _:{**tr.RUNTIME,'gpu':'NVIDIA A10'}),None,cached)
    assert cfg['vocab_size']==1000 and identity['inventory']['model.safetensors']['bytes']>0


@pytest.fixture
def worker_setup(tmp_path,monkeypatch):
    # Hash gates tested separately; orchestration substitutes simple CPU boundaries.
    plan={'remote_output':str(tmp_path/'run')}
    monkeypatch.setattr(tr,'verify_packet',lambda *a:None)
    monkeypatch.setattr(tr,'verify_package',lambda *a:tr.read(PACKAGE/'manifest.json'))
    commits=[]; loads=[]
    results=SimpleNamespace(commit=lambda:commits.append(sorted(p.name for p in Path(plan['remote_output']).iterdir())))
    def load(config):
        assert 'actual-tokenizer-preflight.json' in commits[-1]
        loads.append(config)
        return fixtures.FixtureModel()
    tm=SimpleNamespace(TransformersConfig=TransformersConfig,TransformersModel=load)
    preflight={'passed':True,'reader_prompts':76,'evidence':'synthetic_cpu_fixture'}
    def preflight_call(*a,**kw):
        assert kw['vocab_size']==12345 and kw['writer_cap']==1024
        return preflight
    proxy=SimpleNamespace(actual_preflight=preflight_call,run_stage=mp.run_stage)
    kwargs=dict(importer=lambda *a:(proxy,tm),assets=lambda *a:({'synthetic':True},{'vocab_size':12345}),tokenizer_loader=lambda *a:object())
    return plan,results,commits,loads,preflight,proxy,kwargs


def test_worker_real_stage_callback_and_collection_fixture(worker_setup):
    plan,results,commits,loads,_,_,kwargs=worker_setup
    outcome=tr.worker(plan,Path('.'),PACKAGE,results,**kwargs)
    assert outcome['classification']=='completed_pilot' and len(loads)==1
    assert loads[0].local_files_only and loads[0].dtype=='float16'
    root=Path(plan['remote_output']);stage=root/'stage'
    assert (stage/'D01/completion.json').exists()
    assert len(commits)==7  # entry, preflight, Q0, D00, D01, stage, final
    report=tr.collect_verify(root,PACKAGE,real=False)
    assert report['pilot']['low']==64 and report['evidence']=='synthetic_cpu_fixture'
    assert report['reconciliation']['physical_requests']==outcome['attempted_physical_requests']
    # Real evidence mode must reject the very same synthetic traces.
    with pytest.raises(mp.AuditError):tr.collect_verify(root,PACKAGE)
    (stage/'D01/assessments.jsonl').write_text('')
    with pytest.raises(ValueError,match='incomplete pilot'):tr.collect_verify(root,PACKAGE,real=False)


@pytest.mark.parametrize('fault',['false_preflight','preflight_exception','deadline','bad_plan','commit'])
def test_worker_failures_before_weight_load(worker_setup,monkeypatch,fault):
    plan,results,commits,loads,preflight,proxy,kwargs=worker_setup
    if fault=='false_preflight':preflight['passed']=False
    elif fault=='preflight_exception':proxy.actual_preflight=lambda *a,**kw:(_ for _ in ()).throw(ValueError('fixture preflight error'))
    elif fault=='deadline':
        ticks=iter([0,7000,7001]);kwargs['clock']=lambda:next(ticks)
    elif fault=='bad_plan':monkeypatch.setattr(tr,'verify_packet',lambda *a:(_ for _ in ()).throw(ValueError('plan hash differs')))
    else:results.commit=lambda:(_ for _ in ()).throw(RuntimeError('commit fails'))
    with pytest.raises((ValueError,TimeoutError,RuntimeError)):tr.worker(plan,Path('.'),PACKAGE,results,**kwargs)
    assert not loads


def test_duplicate_remote_run_blocks_before_work(worker_setup):
    plan,results,commits,loads,_,_,kwargs=worker_setup
    Path(plan['remote_output']).mkdir()
    tr.save(Path(plan['remote_output'])/'execution-entry.json',{'previous':'committed'})
    with pytest.raises(FileExistsError):tr.worker(plan,Path('.'),PACKAGE,results,**kwargs)
    assert not loads and not commits


def test_q0_performance_stop_no_dev_family(worker_setup):
    plan,results,commits,loads,_,proxy,kwargs=worker_setup
    original=proxy.run_stage
    def run(*args,**kw):
        args=list(args);args[3]=tr.RequestLimit(fixtures.FixtureModel(reader=lambda m,q,o:mp.ABSTAIN),float('inf'))
        return original(*args,**kw)
    proxy.run_stage=run
    outcome=tr.worker(plan,Path('.'),PACKAGE,results,**kwargs)
    assert outcome['classification']=='valid_research_stop'
    assert not (Path(plan['remote_output'])/'stage/D00').exists()


def test_callback_failure_prevents_next_unit(worker_setup):
    plan,results,commits,loads,_,_,kwargs=worker_setup
    def commit():
        root=Path(plan['remote_output'])
        if (root/'stage/qualification/completion.json').exists():raise RuntimeError('Q0 commit failed')
        commits.append(sorted(p.name for p in root.iterdir()))
    results.commit=commit
    with pytest.raises(RuntimeError,match='Q0 commit failed'):tr.worker(plan,Path('.'),PACKAGE,results,**kwargs)
    root=Path(plan['remote_output'])
    assert not (root/'stage/D00').exists()
    assert 'Q0 commit failed' in (root/'worker-outcome.json').read_text()
    assert (root/'cleanup-error.json').exists()


def test_incomplete_pilot_retains_reason_and_no_decision(worker_setup,monkeypatch):
    plan,results,_,_,_,_,kwargs=worker_setup
    monkeypatch.setattr(mp,'pilot_decision',lambda *a,**kw:dict(complete=False,low=None,stop=None,reason='synthetic missing unit'))
    with pytest.raises(mp.AuditError,match='synthetic missing unit'):tr.worker(plan,Path('.'),PACKAGE,results,**kwargs)
    status=tr.read(Path(plan['remote_output'])/'stage/stage-status.json')
    assert status['pilot']['low'] is None and status['outcome']=='error'
    assert tr.read(Path(plan['remote_output'])/'worker-outcome.json')['classification']=='infrastructure_timeout_incomplete_failure'


def test_verified_import_uses_extracted_modules_in_fresh_process(tmp_path):
    code="""import importlib.util,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('transport', 'game_memory/memory_probe_modal.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
mp,tm=t.verified_import(Path(sys.argv[1]),Path(sys.argv[2]))
assert Path(mp.__file__).is_relative_to(Path(sys.argv[2]))
assert mp.digest({'x':1})==t.digest({'x':1})
"""
    p=subprocess.run([sys.executable,'-c',code,str(PACKAGE),str(tmp_path)],capture_output=True,text=True)
    assert p.returncode==0,p.stderr


@pytest.mark.parametrize('state,tasks',[('running','0'),('stopped','1'),('stopped',None)])
def test_shutdown_requires_saved_app_zero_tasks(state,tasks):
    with pytest.raises(RuntimeError):tr.verify_shutdown([dict(app_id='saved',state=state,tasks=tasks)],'saved')
    with pytest.raises(RuntimeError):tr.verify_shutdown([dict(app_id='unrelated',state='stopped',tasks='0')],'saved')
    tr.verify_shutdown([dict(app_id='saved',state='stopped',tasks='0')],'saved')


def test_unit_commits_precede_later_units(worker_setup):
    plan,results,_,_,_,_,kwargs=worker_setup
    seen=[]
    original_commit=results.commit
    def commit():
        original_commit()
        root=Path(plan['remote_output'])/'stage'
        completed={p.parent.name for p in root.glob('*/completion.json')}
        if 'qualification' in completed and 'qualification' not in seen:
            assert not (root/'D00').exists()
            seen.append('qualification')
        if 'D00' in completed and 'D00' not in seen:
            assert not (root/'D01').exists()
            seen.append('D00')
        if 'D01' in completed and 'D01' not in seen:seen.append('D01')
    results.commit=commit
    tr.worker(plan,Path('.'),PACKAGE,results,**kwargs)
    assert seen==['qualification','D00','D01']


def test_collection_refuses_missing_final_outcome(worker_setup):
    plan,results,_,_,_,_,kwargs=worker_setup
    tr.worker(plan,Path('.'),PACKAGE,results,**kwargs)
    root=Path(plan['remote_output']); (root/'worker-outcome.json').unlink()
    with pytest.raises(FileNotFoundError):tr.collect_verify(root,PACKAGE,real=False)


def test_launch_unauthorized_does_not_construct_sdk(packet,tmp_path,monkeypatch):
    p,_=packet; authorization=tmp_path/'template';authorization.write_text('TEMPLATE — NOT EXECUTION AUTHORIZATION')
    monkeypatch.setattr(tr,'sdk',lambda *a:pytest.fail('unauthorized SDK access'))
    with pytest.raises(ValueError,match='authorization'):tr.launch(p,authorization)


def test_image_hashes_accept_only_matching_runtime_plan_hash(packet):
    p,plan=packet
    frozen=tr.read(p/'transport-manifest.json'); expected=frozen.pop('plan_sha256')
    dump(p/'transport-manifest.json',frozen)
    tr.verify_packet(p,plan,expected)
    with pytest.raises(ValueError,match='plan hash'):tr.verify_packet(p,{**plan,'run_id':'other'},expected)
    with pytest.raises(ValueError,match='plan hash'):tr.verify_packet(p,plan)


def test_passing_q0_then_pilot_stop_preserves_research_outcome(worker_setup):
    plan,results,_,_,_,_,kwargs=worker_setup
    _,tm=kwargs['importer'](None,None)
    load=tm.TransformersModel
    def empty_writer(config):
        model=load(config)
        model.writer=lambda payload,fmt,purpose:'{}' if fmt=='json' else ''
        return model
    tm.TransformersModel=empty_writer
    outcome=tr.worker(plan,Path('.'),PACKAGE,results,**kwargs)
    assert outcome['stage']['qualification']['passed'] is True
    assert outcome['stage']['pilot']['complete'] is True
    assert outcome['stage']['pilot']['stop'] is True
    assert outcome['stage']['pilot']['low'] is None
    assert outcome['classification']==outcome['stage']['outcome']=='valid_research_stop'
    report=tr.collect_verify(Path(plan['remote_output']),PACKAGE,real=False)
    assert report['classification']=='valid_research_stop' and report['pilot']['low'] is None


@pytest.fixture
def collection_setup(worker_setup,tmp_path,monkeypatch):
    plan,results,_,_,_,_,kwargs=worker_setup
    tr.worker(plan,Path('.'),PACKAGE,results,**kwargs)
    remote=Path(plan['remote_output'])
    packet=tmp_path/'retrieval';packet.mkdir()
    plan=dict(run_id='same-run',local_source=str(Path('.').resolve()),local_package=str(PACKAGE),
              local_sdk_site_packages='unused',prepared_utc='2026-11-17T19:46:20Z')
    dump(packet/'plan.json',plan);dump(packet/'call-reference.json',{'call_id':'same-call'})
    dump(packet/'app-reference.json',{'app_id':'saved-app'})
    state=dict(pending=False,interrupt=False,empty=False)
    calls=[]
    class Call:
        def get(self,timeout):
            assert timeout==0
            if state['pending']:raise TimeoutError('synthetic pending call')
            return {'synthetic':'completed'}
    def from_id(call_id):
        calls.append(call_id);return Call()
    class Volume:
        def iterdir(self,run_id,recursive):
            assert run_id=='same-run' and recursive is True
            return [] if state['empty'] else [SimpleNamespace(path='same-run/'+str(f.relative_to(remote)),type=SimpleNamespace(name='FILE')) for f in sorted(remote.rglob('*')) if f.is_file()]
        def read_file(self,path):
            content=(remote/Path(path).relative_to('same-run')).read_bytes()
            yield content[:8]
            if state['interrupt']:raise OSError('synthetic interrupted download')
            yield content[8:]
    def volume(name,create_if_missing):
        assert name=='memory-research-results' and create_if_missing is False
        return Volume()
    monkeypatch.setattr(tr,'sdk',lambda _:SimpleNamespace(FunctionCall=SimpleNamespace(from_id=from_id),Volume=SimpleNamespace(from_name=volume)))
    monkeypatch.setattr(tr,'modal_command',lambda *a,**kw:SimpleNamespace(returncode=0))
    verify=tr.collect_verify
    monkeypatch.setattr(tr,'collect_verify',lambda root,package,**kw:verify(root,package,real=False,**kw))
    return packet,state,calls


@pytest.mark.parametrize('fault',['pending','interrupted'])
def test_collection_retrieval_can_repeat_without_resubmission(collection_setup,fault):
    packet,state,calls=collection_setup
    if fault=='pending':state.update(pending=True,empty=True)
    else:state['interrupt']=True
    with pytest.raises((OSError,mp.AuditError,FileNotFoundError)):tr.collect(packet)
    first=next(packet.glob('collection-*'))
    assert tr.read(first/'collection-error.json')['budget_decision'] is None
    before={str(f.relative_to(first)):tr.sha(f) for f in first.rglob('*') if f.is_file()}
    if fault=='pending':assert 'synthetic pending' in (first/'call-status.json').read_text()
    else:assert list((first/'download').rglob('*.json'))  # Partial file retained.
    state.update(pending=False,empty=False,interrupt=False)
    second=tr.collect(packet)
    assert first!=second and calls==['same-call','same-call']
    assert tr.read(second/'collection-verification.json')['classification']=='completed_pilot'
    assert all(tr.sha(first/n)==h for n,h in before.items())
    assert not (packet/'submission-reservation.json').exists()


@pytest.mark.parametrize('initial,stop_result,final',[
    ('stopped',0,'stopped'), ('running',0,'stopped'),
    ('running',1,'stopped'), ('running','exception','stopped'), ('running',0,'running')])
def test_shutdown_command_path_is_noninteractive_and_checks_state(tmp_path,monkeypatch,initial,stop_result,final):
    packet=tmp_path/'shutdown-packet';packet.mkdir()
    dump(packet/'plan.json',{'local_sdk_site_packages':'unused'})
    dump(packet/'app-reference.json',{'app_id':'saved-app'})
    commands=[];states=iter([initial,final])
    def command(plan,args,**kwargs):
        commands.append(args)
        if args==['app','list','--json']:
            return SimpleNamespace(returncode=0,stderr='',stdout=json.dumps([
                dict(app_id='saved-app',state=next(states),tasks='0'),
                dict(app_id='unrelated',state='running',tasks='3')]))
        assert args==['app','stop','saved-app','--yes']
        if stop_result=='exception':raise OSError('synthetic command failure')
        return SimpleNamespace(returncode=stop_result,stdout='',stderr='synthetic stop status')
    monkeypatch.setattr(tr,'modal_command',command)
    if final=='running':
        with pytest.raises(RuntimeError,match='zero tasks'):tr.shutdown(packet)
    else:
        attempt=tr.shutdown(packet)
        assert tr.read(attempt/'verified.json')['app_id']=='saved-app'
    assert commands==([['app','list','--json']] if initial=='stopped' else
                      [['app','list','--json'],['app','stop','saved-app','--yes'],['app','list','--json']])


def test_local_source_rejects_shadowed_import(tmp_path,monkeypatch):
    monkeypatch.setattr(mp,'__file__',str(tmp_path/'memory_probe.py'))
    with pytest.raises(RuntimeError,match='shadowed local'):tr.local_experiment(PACKAGE,Path('.'))


def test_actual_artifact_launcher_collect_without_pythonpath(worker_setup,tmp_path):
    import os
    plan,results,_,_,_,_,kwargs=worker_setup
    tr.worker(plan,Path('.'),PACKAGE,results,**kwargs)
    remote=Path(plan['remote_output'])
    packet=tmp_path/'artifact';packet.mkdir()
    # Execute the actual launcher file, not python -c; no checkout on initial sys.path.
    shutil.copyfile('artifacts/memory-probe-v1/s1-preparation-20261117T194620Z/launcher.py',packet/'launcher.py')
    shutil.copyfile('game_memory/memory_probe_modal.py',packet/'worker_transport.py')
    fake_sdk=tmp_path/'mock-sdk';fake_sdk.mkdir()
    (fake_sdk/'modal.py').write_text('''
import json, os
from pathlib import Path
from types import SimpleNamespace
__version__='1.6.4'
class FunctionCall:
    @classmethod
    def from_id(cls, call_id):
        assert call_id=='saved-call'
        return cls()
    def get(self, timeout): return {'evidence':'synthetic CPU mock'}
class Volume:
    @classmethod
    def from_name(cls, name, create_if_missing):
        assert not create_if_missing
        return cls()
    def iterdir(self, run_id, recursive):
        root=Path(os.environ['SYNTHETIC_REMOTE'])
        return [SimpleNamespace(path=run_id+'/'+str(p.relative_to(root)),type=SimpleNamespace(name='FILE')) for p in root.rglob('*') if p.is_file()]
    def read_file(self, path):
        yield (Path(os.environ['SYNTHETIC_REMOTE'])/Path(path).relative_to('saved-run')).read_bytes()
if __name__=='__main__': print('synthetic provider log; no Modal contact')
''')
    dump(packet/'plan.json',dict(local_source=str(Path('.').resolve()),local_package=str(PACKAGE),
        local_sdk_site_packages=str(fake_sdk),run_id='saved-run',prepared_utc='2026-11-17T19:46:20Z'))
    dump(packet/'call-reference.json',{'call_id':'saved-call'});dump(packet/'app-reference.json',{'app_id':'saved-app'})
    env={**os.environ,'PYTHONPATH':'','SYNTHETIC_REMOTE':str(remote)}
    result=subprocess.run([sys.executable,str(packet/'launcher.py'),'collect'],cwd=tmp_path,env=env,capture_output=True,text=True)
    assert result.returncode!=0  # Synthetic traces must fail the actual real=True audit.
    attempt=next(packet.glob('collection-*'))
    error=tr.read(attempt/'collection-error.json')
    assert 'real stage evidence is not an actual model forward' in error['error'],result.stderr
    assert 'ModuleNotFoundError' not in error['traceback']
    assert (attempt/'provider-logs.stdout').read_text().startswith('synthetic provider log')
    assert tr.read(attempt/'call-status.json')['result']['evidence']=='synthetic CPU mock'
    assert not (packet/'submission-reservation.json').exists()
