"""Narrow, opt-in S1 transport. Importing this module performs no remote work."""
from pathlib import Path
import argparse
import hashlib
import importlib
import json
import math
import os
import sys
import tempfile
import time
import traceback
import zipfile

PACKAGE_DIGEST = 'f13e098e790f52159d5f34d5b1d608f8da1829a9b10ae84c4413beaebdba4fa6'
REVISION = 'cdbee75f17c01a7cc42f958dc650907174af0554'
RUNTIME = dict(python_version='3.12.10', torch_version='2.8.0', transformers_version='4.57.6',
               tokenizers_version='0.22.1', safetensors_version='0.6.2',
               huggingface_hub_version='0.36.0', cuda_version='12.8')
ENV = dict(HF_HOME='/cache/huggingface', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
           HF_HUB_DISABLE_TELEMETRY='1')
AUTHORIZATION = ('I authorize memory-probe-v1 S1 using package-v2 manifest '+PACKAGE_DIGEST+
 ': one Modal A10 worker, at most one Qwen weight load from the existing read-only cache, '
 'actual cached-tokenizer preflight before loading, Q0 qualification, then D00-D01 only if Q0 passes; '
 'startup cap 600 seconds, execution cap 7200 seconds, soft deadline 6900 seconds, zero configured retries, '
 'at most 1070 model requests. No test-family inference, model/dependency downloads, installations, or S2. '
 "Collect and verify this run's evidence and shut down its App afterward. Do not retry or resubmit an interrupted run.")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    # The frozen experiment's convention, including default JSON separators.
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    with path.open('x') as f:
        json.dump(value, f, indent=1, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def verify_package(package, source=None):
    package = Path(package)
    manifest = read(package/'manifest.json')
    if manifest['manifest_sha256'] != PACKAGE_DIGEST or digest({k:v for k,v in manifest.items() if k!='manifest_sha256'}) != PACKAGE_DIGEST:
        raise ValueError('package manifest digest differs')
    for n, h in read(package/'package-files-sha256.json').items():
        if sha(package/n) != h:
            raise ValueError('package file hash differs: '+n)
    if sha(package/'source.zip') != manifest['source_zip_sha256']:
        raise ValueError('source archive hash differs')
    with zipfile.ZipFile(package/'source.zip') as z:
        if sorted(z.namelist()) != sorted(manifest['source_files']):
            raise ValueError('archive inventory differs')
        for n,h in manifest['source_files'].items():
            if Path(n).is_absolute() or '..' in Path(n).parts or hashlib.sha256(z.read(n)).hexdigest()!=h:
                raise ValueError('archive source differs: '+n)
            if source is not None and sha(Path(source)/n)!=h:
                raise ValueError('current source differs: '+n)
    return manifest


def verify_packet(packet, plan, expected_plan_sha256=None):
    packet = Path(packet)
    frozen = read(packet/'transport-manifest.json')
    if digest(plan) != frozen.get('plan_sha256', expected_plan_sha256):
        raise ValueError('plan hash differs')
    for n,h in frozen['files'].items():
        if sha(packet/n)!=h:
            raise ValueError('transport hash differs: '+n)
    if plan['stage']!='s1' or plan['package_digest']!=PACKAGE_DIGEST or plan['remote_output']!='/results/'+plan['run_id']:
        raise ValueError('invalid S1 plan')
    return frozen


def reserve(packet, plan, authorization):
    if Path(authorization).read_text().strip()!=AUTHORIZATION:
        raise ValueError('separately supplied execution authorization required; template is not authorization')
    frozen = verify_packet(packet, plan)
    save(Path(packet)/'submission-reservation.json', dict(run_id=plan['run_id'],
         package_digest=PACKAGE_DIGEST, transport=frozen, state='reserved; never resubmit'))


def verified_import(package, destination):
    manifest = verify_package(package)
    with zipfile.ZipFile(Path(package)/'source.zip') as z:
        z.extractall(destination)
    verify_package(package, destination)
    # The transport is loaded as a top-level module; refuse preloaded study modules.
    if any(n=='game_memory' or n.startswith('game_memory.') for n in sys.modules):
        raise RuntimeError('study already imported before verified extraction')
    sys.path.insert(0, str(destination))
    mp = importlib.import_module('game_memory.memory_probe')
    tm = importlib.import_module('game_memory.transformers_model')
    for n, mod in list(sys.modules.items()):
        if n=='game_memory' or n.startswith('game_memory.'):
            path = Path(mod.__file__).resolve()
            if not path.is_relative_to(Path(destination).resolve()):
                raise RuntimeError('shadowed frozen module: '+n)
            relative = str(path.relative_to(Path(destination).resolve()))
            if relative not in manifest['source_files'] or sha(path)!=manifest['source_files'][relative]:
                raise RuntimeError('unverified study module: '+n)
    return mp, tm


def runtime_and_cache(tm, config, cache):
    runtime = tm.runtime_metadata(config)
    if any(runtime.get(k)!=v for k,v in RUNTIME.items()) or runtime.get('gpu') not in ('NVIDIA A10','NVIDIA A10G'):
        raise RuntimeError('pinned runtime differs')
    cache = Path(cache)
    cfg = read(cache/'config.json')
    if cfg.get('model_type')!='qwen3' or cfg.get('max_position_embeddings',0)<8192 or type(cfg.get('vocab_size')) is not int or cfg['vocab_size']<1:
        raise ValueError('incompatible cached model configuration')
    names = ['config.json','tokenizer.json','tokenizer_config.json']
    index = cache/'model.safetensors.index.json'
    weights = sorted(set(read(index)['weight_map'].values())) if index.exists() else ['model.safetensors']
    if not weights:
        raise ValueError('empty weight inventory')
    inventory = {}
    for n in names+weights:
        if Path(n).name!=n or not (cache/n).is_file() or (cache/n).stat().st_size<=0:
            raise ValueError('missing cached asset: '+n)
        inventory[n] = dict(bytes=(cache/n).stat().st_size, resolved_path=str((cache/n).resolve()))
    return dict(runtime=runtime, executable=sys.executable, package_environment='/opt/memory/.venv', cache_path=str(cache), revision=REVISION,
                config_sha256=sha(cache/'config.json'), inventory=inventory), cfg


def cached_tokenizer(cache):
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(str(cache), local_files_only=True, trust_remote_code=False)


class RequestLimit:
    """Pass through exact inputs and results; count attempts before delegation."""
    def __init__(self, model, deadline, clock=time.monotonic):
        self.model, self.deadline, self.clock = model, deadline, clock
        self.calls = 0

    @property
    def metadata(self):
        return self.model.metadata

    def count_tokens(self, text):
        return self.model.count_tokens(text)

    def _check(self):
        if self.clock() >= self.deadline:
            raise TimeoutError('soft deadline before request')
        if self.calls >= 1070:
            raise RuntimeError('S1 request ceiling exhausted')
        self.calls += 1

    def generate(self, messages, *, purpose):
        self._check()
        return self.model.generate(messages, purpose=purpose)

    def score_choices(self, messages, *, labels):
        self._check()
        return self.model.score_choices(messages, labels=labels)


def worker(plan, packet, package, results, *, clock=time.monotonic,
           importer=verified_import, assets=runtime_and_cache, tokenizer_loader=cached_tokenizer, entry_started=None, expected_plan_sha256=None):
    started = clock() if entry_started is None else entry_started
    deadline = started+6900
    root = Path(plan['remote_output'])
    root.mkdir(exist_ok=False)  # Re-entry refuses before any scientific work.
    outcome = dict(classification='infrastructure_timeout_incomplete_failure')
    original = None
    bounded = None
    try:
        save(root/'execution-entry.json', dict(plan=plan, entered_monotonic=started))
        results.commit()  # Mandatory durable entry before tokenizer or weights.
        verify_packet(packet, plan, expected_plan_sha256)
        verify_package(package)
        with tempfile.TemporaryDirectory(prefix='probe-source-') as tmp:
            mp, tm = importer(package, Path(tmp))
            config = tm.TransformersConfig(revision=REVISION, dtype='float16', device='cuda',
                context_limit=8192, generation_seed=0, memory_max_new_tokens=1024, local_files_only=True)
            cache = Path('/cache/huggingface/hub/models--Qwen--Qwen3-4B-Instruct-2507/snapshots')/REVISION
            identity, cfg = assets(tm, config, cache)
            save(root/'runtime-cache.json', identity)
            def check():
                if clock()>=deadline:
                    raise TimeoutError('soft deadline before loading/work')
            check()
            tokenizer = tokenizer_loader(cache)
            preflight = mp.actual_preflight(Path(package), tokenizer, vocab_size=cfg['vocab_size'],
                context_limit=8192, writer_cap=1024, evidence='actual_cached_tokenizer')
            save(root/'actual-tokenizer-preflight.json', preflight)
            results.commit()
            if preflight.get('passed') is not True or preflight.get('reader_prompts')!=76:
                raise ValueError('actual tokenizer preflight failed')
            check()
            load_started = clock()
            model = tm.TransformersModel(config)
            outcome['model_load_wall_seconds'] = clock()-load_started
            save(root/'model.json', model.metadata)
            bounded = RequestLimit(model, deadline, clock)
            check()
            status = mp.run_stage('s1', Path(package), root/'stage', bounded,
                                  commit=results.commit, deadline=deadline, clock=clock)
            outcome.update(classification=('valid_research_stop' if status['outcome']=='valid_research_stop'
                                           else 'completed_pilot'), stage=status)
    except BaseException as e:
        original = e
        outcome.update(error=repr(e), traceback=traceback.format_exc())
        raise
    finally:
        outcome.update(worker_seconds=clock()-started, attempted_physical_requests=bounded.calls if bounded else 0)
        try:
            save(root/'worker-outcome.json', outcome)
            results.commit()
        except BaseException as cleanup:
            if original is None:
                raise
            try:
                save(root/'cleanup-error.json',dict(error=repr(cleanup),traceback=traceback.format_exc()))
                results.commit()
            except BaseException:
                pass  # Never replace the scientific/transport failure with cleanup failure.
    return outcome


def local_experiment(package, source):
    """Verify the declared checkout before importing its frozen audit implementation."""
    source = Path(source).resolve()
    manifest = verify_package(package, source)
    sys.path.insert(0, str(source))
    mp = importlib.import_module('game_memory.memory_probe')
    for name, module in list(sys.modules.items()):
        relative = name.replace('.', '/')+'.py'
        if name=='game_memory':
            relative = 'game_memory/__init__.py'
        if relative in manifest['source_files']:
            if Path(module.__file__).resolve()!=(source/relative).resolve():
                raise RuntimeError('shadowed local study module: '+name)
    return mp


def collect_verify(root, package, *, real=True, source=None):
    """Audit raw units independently of the saved stage decision; partial runs fail closed."""
    mp = local_experiment(package, source if source is not None else Path(__file__).resolve().parents[1])
    root = Path(root)
    splits = mp.load_splits(Path(package))
    stage = root/'stage'
    gate = mp.qualification_gate(stage/'qualification', splits['qualification'], real=real)
    report = dict(qualification=gate, evidence='real_required' if real else 'synthetic_cpu_fixture')
    if gate['passed']:
        pilot = mp.pilot_decision([stage/f['family_id'] for f in splits['dev']], splits['dev'], real=real)
        if pilot.get('complete') is not True:
            raise ValueError('incomplete pilot: '+str(pilot.get('reason')))
        report['pilot'] = pilot
        rows = [r for f in splits['dev'] for r in mp._jsonl(stage/f['family_id']/'assessments.jsonl')]
        report['per_cell'] = {}
        for r in rows:
            key = '/'.join(str(r.get(k)) for k in ('kind','condition','format','allowance','probe'))
            cell = report['per_cell'].setdefault(key,dict(correct=0,abstained=0,total=0))
            cell['total']+=1; cell['correct']+=r['correct']; cell['abstained']+=r['abstained']
        if real and (root/'model.json').exists():
            load = read(root/'model.json')['load_seconds']
            longest = max(read(stage/f['family_id']/'summary.json')['wall_seconds'] for f in splits['dev'])
            report['planning'] = dict(L=load,R=longest,**{f'T({n})':max(600,math.ceil(1.5*(load+n*longest)+300)) for n in (8,4)},
                                      unpiloted_128=pilot.get('low')==128)
    saved = read(stage/'stage-status.json')
    outcome = read(root/'worker-outcome.json')
    stopped = not gate['passed'] or report['pilot']['stop'] is True
    expected = 'valid_research_stop' if stopped else 'completed_pilot'
    expected_stage = 'valid_research_stop' if stopped else 'pilot_complete'
    if outcome.get('classification')!=expected or saved.get('outcome')!=expected_stage or saved.get('qualification')!=gate or ('pilot' in report and saved.get('pilot')!=report['pilot']):
        raise ValueError('final outcome incomplete or disagrees with raw evidence')
    if real:
        preflight = read(root/'actual-tokenizer-preflight.json')
        if preflight.get('passed') is not True or preflight.get('reader_prompts')!=76 or preflight.get('evidence')!='actual_cached_tokenizer' or preflight.get('package_manifest_sha256')!=PACKAGE_DIGEST:
            raise ValueError('missing actual preflight identity')
    report['classification'] = expected
    report['worker_seconds'] = outcome['worker_seconds']
    report['family_seconds'] = {f['family_id']:read(stage/f['family_id']/'summary.json')['wall_seconds'] for f in splits['dev'] if (stage/f['family_id']/'completion.json').exists()}
    report['reconciliation'] = reconcile(stage)
    return report


def reconcile(stage):
    from game_memory import memory_probe as mp
    writes = [r for p in Path(stage).glob('*/writes.jsonl') for r in mp._jsonl(p)]
    events = [r for p in Path(stage).glob('*/events.jsonl') for r in mp._jsonl(p)]
    assessments = [r for p in Path(stage).glob('*/assessments.jsonl') for r in mp._jsonl(p)]
    requests = [r for r in events if r['event']=='model_request']
    responses = [r for r in events if r['event']=='model_response']
    denied = sum(r['event']=='model_error' and r.get('error_message') in ('S1 request ceiling exhausted','soft deadline before request') for r in events)
    return dict(physical_requests=len(requests)-denied, refused_before_delegation=denied,
                request_records=len(requests), responses=len(responses), usage_complete=len(requests)-denied==len(responses),
                primary_updates=len(writes), fallbacks=sum('memory_fallback:previous_valid_memory' in r['update_events'] for r in writes),
                logical_assessments=len(assessments), reuse_sources=[r for r in assessments if r['reused']],
                repair_requests=sum(r.get('purpose')=='memory_repair' for r in requests),
                known_input_tokens=sum(r['input_tokens'] for r in responses),
                known_output_tokens=sum(r['output_tokens'] for r in responses),
                known_inference_seconds=sum(r['elapsed_seconds'] for r in responses),
                known_forward_seconds=sum(r['elapsed_seconds'] for r in responses if r.get('purpose')=='action'),
                known_generation_seconds=sum(r['elapsed_seconds'] for r in responses if r.get('purpose')!='action'),
                unknown_usage_requests=len(requests)-denied-len(responses))


def sdk(plan):
    try:
        import modal
    except ModuleNotFoundError:
        sys.path.append(plan['local_sdk_site_packages'])
        import modal
    if modal.__version__!='1.6.4':
        raise RuntimeError('reviewed SDK 1.6.4 required')
    return modal


def launch(packet, authorization):
    packet = Path(packet).resolve()
    plan = read(packet/'plan.json')
    reserve(packet, plan, authorization)  # No SDK object before authorization + exclusive fsync.
    modal = sdk(plan)
    package = Path(plan['local_package']).resolve()
    verify_package(package, Path.cwd())
    image = (modal.Image.from_id(plan['parent_image'])
             .env({**ENV, 'VIRTUAL_ENV':'/opt/memory/.venv', 'PATH':'/opt/memory/.venv/bin:/usr/local/bin:/usr/bin:/bin'})
             .add_local_dir(package, '/opt/probe/package', copy=True)
             .add_local_file(packet/'worker_transport.py','/opt/probe/worker_transport.py',copy=True)
             .add_local_file(packet/'image-transport-hashes.json','/opt/probe/transport-manifest.json',copy=True)
             .add_local_file(packet/'launcher.py','/opt/probe/launcher.py',copy=True))
    results = modal.Volume.from_name('memory-research-results',create_if_missing=False)
    cache = modal.Volume.from_name('memory-research-cache',create_if_missing=False)
    app = modal.App('memory-probe-v1-'+plan['run_id'])
    @app.function(image=image,gpu='A10',cpu=4,memory=32768,startup_timeout=600,timeout=7200,
                  min_containers=0,max_containers=1,max_inputs=1,retries=0,scaledown_window=2,
                  volumes={'/cache':cache.read_only(),'/results':results},serialized=True,include_source=False)
    def execute(invocation):
        import time
        entry_started = time.monotonic()
        import importlib.util
        import sys
        from pathlib import Path
        # Use the parent's validated venv packages in this same Modal process.
        venv_site = '/opt/memory/.venv/lib/python3.12/site-packages'
        if not Path(venv_site).is_dir():
            raise RuntimeError('validated image environment missing')
        sys.path.insert(0, venv_site)
        spec = importlib.util.spec_from_file_location('probe_transport','/opt/probe/worker_transport.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.worker(invocation['plan'],Path('/opt/probe'),Path('/opt/probe/package'),results,
                          entry_started=entry_started,expected_plan_sha256=invocation['plan_sha256'])
    with modal.enable_output(), app.run(detach=True):
        save(packet/'app-reference.json',dict(app_id=app.app_id))
        save(packet/'image-reference.json',dict(image_id=image.object_id))
        # An exception/interrupt here leaves the reservation and partial IDs intact: never resubmit.
        call = execute.spawn(dict(plan=plan,plan_sha256=digest(plan)))
        save(packet/'call-reference.json',dict(call_id=call.object_id,function_id=execute.object_id,app_id=app.app_id))


def inspect_call(packet):
    packet = Path(packet)
    plan = read(packet/'plan.json')
    modal = sdk(plan)
    reference = packet/'call-reference.json'
    if not reference.exists():
        raise RuntimeError('unknown submission acknowledgement; inspect saved App and run records; never resubmit')
    return modal.FunctionCall.from_id(read(reference)['call_id']).get(timeout=0)


def main(packet=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['launch','status','collect','shutdown'])
    parser.add_argument('--authorization')
    args = parser.parse_args()
    packet = Path(packet) if packet else Path(__file__).resolve().parent
    if args.action=='launch':
        if not args.authorization:
            parser.error('--authorization is required; preparation template is not authorization')
        launch(packet,args.authorization)
    elif args.action=='status':
        print(json.dumps(inspect_call(packet),indent=1))
    elif args.action=='collect':
        collect(packet)
    else:
        shutdown(packet)


def modal_command(plan, arguments, **kwargs):
    import subprocess
    return subprocess.run([sys.executable,'-m','modal',*arguments],
        env={**os.environ,'PYTHONPATH':plan['local_sdk_site_packages']}, **kwargs)


def collect(packet):
    packet = Path(packet)
    plan = read(packet/'plan.json')
    source = Path(plan['local_source']).resolve()
    package = source/plan['local_package']
    local_experiment(package, source)
    # Each retrieval is independent; preserve partial bytes and never resubmit inference.
    attempt = Path(tempfile.mkdtemp(prefix='collection-', dir=packet))
    destination = attempt/'download'
    destination.mkdir()
    try:
        try:
            save(attempt/'call-status.json',dict(result=inspect_call(packet)))
        except Exception as e:
            save(attempt/'call-status.json',dict(error=repr(e),traceback=traceback.format_exc()))
        modal = sdk(plan)
        volume = modal.Volume.from_name('memory-research-results',create_if_missing=False)
        for entry in volume.iterdir(plan['run_id'],recursive=True):
            if entry.type.name!='FILE':
                continue
            relative = Path(entry.path).relative_to(plan['run_id'])
            if '..' in relative.parts:
                raise ValueError('unsafe collection path')
            target = destination/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as f:
                for chunk in volume.read_file(entry.path):
                    f.write(chunk)
        app_id = read(packet/'app-reference.json')['app_id']
        with (attempt/'provider-logs.stdout').open('xb') as out, (attempt/'provider-logs.stderr').open('xb') as err:
            logs = modal_command(plan,['app','logs',app_id,'--since',plan['prepared_utc'],
                '--timestamps','--show-function-call-id'],stdout=out,stderr=err)
        save(attempt/'provider-logs-exit.json',dict(returncode=logs.returncode))
        report = collect_verify(destination, package, source=source)
        if logs.returncode:
            raise RuntimeError('provider log collection failed; raw results retained')
        save(attempt/'collection-verification.json',report)
    except BaseException as e:
        error = dict(error=repr(e),traceback=traceback.format_exc(),complete=False,budget_decision=None)
        try:
            error['reconciliation'] = reconcile(destination/'stage')
        except Exception as secondary:
            error['reconciliation_error'] = repr(secondary)
        save(attempt/'collection-error.json',error)
        raise
    print('Verified collection:',attempt)
    return attempt


def shutdown(packet):
    packet = Path(packet)
    plan = read(packet/'plan.json')
    app_id = read(packet/'app-reference.json')['app_id']
    attempt = Path(tempfile.mkdtemp(prefix='shutdown-', dir=packet))

    def inventory(name):
        result = modal_command(plan,['app','list','--json'],capture_output=True,text=True)
        save(attempt/name,dict(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
        if result.returncode:
            raise RuntimeError('App inventory failed')
        return json.loads(result.stdout)

    try:
        verify_shutdown(inventory('before.json'),app_id)
    except (RuntimeError, ValueError):
        # The execution authorization already covers stopping this saved App only.
        try:
            result = modal_command(plan,['app','stop',app_id,'--yes'],capture_output=True,text=True)
            save(attempt/'stop.json',dict(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
        except Exception as e:
            save(attempt/'stop-error.json',dict(error=repr(e),traceback=traceback.format_exc()))
        # An already-stopped race/nonzero stop is harmless only if final state proves it.
        verify_shutdown(inventory('after.json'),app_id)
    save(attempt/'verified.json',dict(app_id=app_id,state='stopped',tasks=0))
    print('Saved App verified stopped with zero tasks:',attempt)
    return attempt


def verify_shutdown(inventory, app_id):
    matches = [r for r in inventory if r.get('app_id')==app_id]
    if len(matches)!=1 or matches[0].get('state','').lower()!='stopped' or str(matches[0].get('tasks'))!='0':
        raise RuntimeError('saved App has not been verified stopped with zero tasks; inspect status, never resubmit')
