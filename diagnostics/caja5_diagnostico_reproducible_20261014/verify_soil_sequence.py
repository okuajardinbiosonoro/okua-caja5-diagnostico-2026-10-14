"""Exercise an accelerated soil sequence on an isolated HTTP server and temp logs."""
import importlib.util
import json
import tempfile
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from soil_sequence import configure

root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('isolated_soil_timer',root/'controller.py')
timer=importlib.util.module_from_spec(spec);spec.loader.exec_module(timer)
plan=configure({'trial_id':'plan-check'})
assert sum(s['duration_s'] for s in plan['sequence_steps'])==920
for node in ('EB5','EC5','EE5','EF5'):
    contacts=[s for s in plan['sequence_steps'] if s['plant_node']==node and s['phase'] in ('first_contact','contact')]
    assert [s['phase'] for s in contacts]==(['contact'] if node=='EB5' else ['first_contact','contact'])
    assert all(s['duration_s']==20 for s in contacts)
    assert all(s['ground_state']=='soil_EB5_pot' for s in contacts)
    assert contacts[-1]['black_node']==(None if node=='EB5' else node)

with tempfile.TemporaryDirectory(prefix='okua-soil-sequence-') as scratch:
    timer.ROOT=Path(scratch);timer.TRACE=timer.ROOT/'markers.jsonl'
    timer.assert_capture_ready=lambda:None
    timer.STATE['baseline_done']=True
    def accelerated(config):
        configure(config)
        for s in config['sequence_steps']:s['duration_s']=.04 if s['phase']!='ground_placement' else .4
        return config
    timer.configure_soil_sequence=accelerated
    server=timer.ThreadingHTTPServer(('127.0.0.1',0),timer.Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_address[1]}'
    def request(route,payload=None):
        req=Request(base+route,data=json.dumps(payload).encode() if payload is not None else None,
                    headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=3) as response:return json.load(response)
    def wait_for(predicate,seconds=5):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            state=request('/status')
            if predicate(state):return state
            time.sleep(.01)
        raise AssertionError('Isolated sequence did not reach expected state')
    operator='isolated-soil-operator'
    reports=[{'node':n,'confirmed_contacts':True} for n in ('EB5','EC5','EE5','EF5')]
    try:
        request('/arm',{'trial_id':'isolated-soil-complete','plant_node':'EB5','black_node':'EB5','condition':'soil_sequence'})
        try:
            request('/start',{'operator_id':operator,'ui_revision':timer.UI_REVISION,'footwear':'shoes','all_black_free':False})
            raise AssertionError('Missing initial ground condition was accepted')
        except HTTPError as e:assert e.code==409
        state=request('/start',{'operator_id':operator,'ui_revision':timer.UI_REVISION,'footwear':'shoes','all_black_free':True})
        assert state['phase']=='preparation' and state['active_step']['phase']=='preparation'
        wait_for(lambda s:s['phase']=='ground_placement')
        request('/ground_placed',{'operator_id':operator,'soil_moisture':'slightly_damp','depth_cm':2})
        wait_for(lambda s:s['mode']=='awaiting_report')
        request('/report',{'operator_id':operator,'followed_cues':True,'grounded_black_kept_fixed':True,'completed_repetitions':4,'block_reports':reports})
        rows=[json.loads(l) for l in timer.TRACE.read_text(encoding='utf-8').splitlines()]
        scheduled=[r for r in rows if r['kind']=='scheduled_instruction']
        assert len(scheduled)==len(plan['sequence_steps'])
        assert any(r['kind']=='operator_ground_placed' for r in rows)
        assert any(r['kind']=='trial_completed' for r in rows)
        request('/arm',{'trial_id':'isolated-soil-timeout','plant_node':'EB5','black_node':'EB5','condition':'soil_sequence'})
        request('/start',{'operator_id':operator,'ui_revision':timer.UI_REVISION,'footwear':'shoes','all_black_free':True})
        end=wait_for(lambda s:s['mode']=='awaiting_report')
        assert end['phase']=='aborted'
        print(json.dumps({'single_run_plants':['EB5','EC5','EE5','EF5'],'EB5_black_never_held':True,
                          'other_nodes_plant_then_own_black':True,'max_duration_s':920,
                          'placement_confirmation_advances':True,'unconfirmed_placement_aborts':True,
                          'complete_sequence_report_saved':True,'real_sensor_MIDI_or_trial_access':False}))
    finally:timer.STOP.set();server.shutdown();server.server_close()
