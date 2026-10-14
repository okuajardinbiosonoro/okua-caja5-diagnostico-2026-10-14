"""Summarize complete, untouched baseline. Preserve native scales and limitations."""
import collections
import json
import statistics
from datetime import datetime, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'captura_completa'
rows=[]
with (DATA/'signals.jsonl').open(encoding='utf-8') as stream:
    for line in stream:
        try: row=json.loads(line)
        except json.JSONDecodeError: continue
        rows.append(row)
start=next(datetime.fromisoformat(r['at_utc']) for r in rows if r['kind']=='started')
end=start+timedelta(seconds=300)
window=[r for r in rows if start<=datetime.fromisoformat(r['at_utc'])<end]
output={'start_utc':start.isoformat(),'end_utc':end.isoformat(),'duration_s':300,'nodes':{},
        'label':'Untouched baseline declared by operator; glass installed, black tips free',
        'limitations':['Native scales differ by firmware; no cross-node calibrated voltage comparison.',
                       'ADC code zero is not proof of exactly zero signed analogue voltage.',
                       'MIDI is not independently verified audible output.',
                       'ED5 has runtime and MIDI only, no detailed sensor telemetry.']}
def summary(values):
    if not values:return None
    values=sorted(values)
    return {'min':values[0],'median':statistics.median(values),'p95':values[int(.95*(len(values)-1))], 'max':values[-1]}

for node_id,label,channel in [(21,'EB5',6),(22,'EC5',7),(23,'ED5',8),(24,'EE5',9),(25,'EF5',10)]:
    sensors=[r for r in window if r['kind']=='sensor' and r['node_id']==node_id]
    midi=[r for r in window if r['kind']=='midi' and r['channel']==channel]
    runtime=[r['runtime'] for r in window if r['kind']=='ckv2' and r['node_id']==node_id]
    ons=[r for r in midi if r['message']['type']=='note_on' and r['message'].get('velocity',0)>0]
    offs=[r for r in midi if r['message']['type']=='note_off' or (r['message']['type']=='note_on' and r['message'].get('velocity',0)==0)]
    result={'sensor_frames':len(sensors),'firmware_strings':sorted(set(r['values'].get('fw','unknown') for r in sensors)),
            'midi_note_ons':len(ons),'midi_note_offs':len(offs),'midi_pitches':sorted(set(r['message']['note'] for r in ons)),
            'runtime_samples':len(runtime), 'runtime_last':runtime[-1] if runtime else None,
            'metrics':{}, 'activation_windows':[]}
    active_start=None
    for r in sensors:
        active=r['values'].get('plant_active')=='1'
        if active and active_start is None: active_start=r['at_utc']
        elif not active and active_start is not None:
            result['activation_windows'].append({'from_utc':active_start,'to_utc':r['at_utc']})
            active_start=None
    if active_start is not None:result['activation_windows'].append({'from_utc':active_start,'to_utc':None})
    result['active_frame_fraction']=sum(r['values'].get('plant_active')=='1' for r in sensors)/len(sensors) if sensors else None
    result['zero_raw_frame_fraction']=sum(float(r['values'].get('raw',-1))==0 for r in sensors)/len(sensors) if sensors else None
    for key in ['raw','filt','base','threshold','noise_p95','rms_mean','occupancy','occupancy_base','score','samples','span_ms','adc_peak','transition_resets']:
        values=[float(r['values'][key]) for r in sensors if key in r['values']]
        if values: result['metrics'][key]=summary(values)
    output['nodes'][label]=result
(ROOT/'baseline_summary.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
protocol=json.loads((ROOT/'methodology.json').read_text(encoding='utf-8'))
protocol['stages'][0]['start_utc']=start.isoformat()
protocol['stages'][0]['expected_end_utc']=end.isoformat()
(ROOT/'methodology.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
print(json.dumps({'start_utc':start.isoformat(),'end_utc':end.isoformat(), 'nodes':{
    k:{'frames':v['sensor_frames'],'firmware':v['firmware_strings'],'active_fraction':v['active_frame_fraction'],
       'windows':len(v['activation_windows']),'note_ons':v['midi_note_ons'],'notes':v['midi_pitches']}
    for k,v in output['nodes'].items()}},indent=2))
