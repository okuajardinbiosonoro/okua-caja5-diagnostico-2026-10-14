"""Exercise startup HTTP state with a deliberately delayed worker, using isolated logs."""
import importlib.util
import json
import tempfile
import threading
import time
from pathlib import Path
from urllib.request import Request,urlopen

root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('isolated_timer',root/'controller.py')
timer=importlib.util.module_from_spec(spec)
spec.loader.exec_module(timer)
with tempfile.TemporaryDirectory(prefix='okua-timer-startup-') as scratch:
    timer.ROOT=Path(scratch)
    timer.TRACE=timer.ROOT/'test_markers.jsonl'
    timer.assert_capture_ready=lambda:None
    # No sensor collector, MIDI interface or real trial is used in this test.
    timer.run_trial=lambda config:time.sleep(.05)
    timer.STATE['baseline_done']=True
    server=timer.ThreadingHTTPServer(('127.0.0.1',0),timer.Handler)
    worker=threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    base=f'http://127.0.0.1:{server.server_address[1]}'
    def request(route,payload=None):
        req=Request(base+route,data=json.dumps(payload).encode() if payload is not None else None,
                    headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=3) as response:return json.load(response)
    def check(state):
        assert state['mode']=='running'
        assert state['phase']=='preparation'
        assert state['trial'] is not None and state['armed'] is None
        assert state['phase_instructions'][state['phase']]['instruction']
        assert state['repetition']==0
    try:
        for i in range(25):
            armed=request('/arm',{'trial_id':f'isolated-startup-{i}','plant_node':'EB5',
                                 'black_node':'EC5','condition':'cross_pair','contact_order':'black_first'})
            check(request('/start',{'operator_id':'isolated-test-operator','ui_revision':timer.UI_REVISION,'footwear':'shoes'}))
            check(request('/status'))
            request('/abort',{'operator_id':'isolated-test-operator','reason':'Isolated test ends before any contact phase'})
            request('/report',{'completed_repetitions':0,'followed_cues':False})
        print(json.dumps({'isolated_http_startups':25,'all_running_states_had_preparation':True,
                          'real_trial_started':False,'sensor_or_MIDI_access':False}))
    finally:
        server.shutdown();server.server_close()
