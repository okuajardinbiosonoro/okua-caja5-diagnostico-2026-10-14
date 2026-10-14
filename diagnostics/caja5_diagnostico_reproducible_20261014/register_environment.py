"""Record human-reported conditions without changing the original sensor data."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
def save(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')

now=datetime.now(timezone.utc).isoformat(timespec='milliseconds')
common={
    'floor_material':'synthetic_grass',
    'floor_moisture':'slightly_damp',
    'moisture_source':'Direct operator observation; not a measured moisture value',
    'footwear':'unknown',
    'body_to_earth_impedance':'not_measured',
    'electrical_isolation':'not_verified',
    'weather_context_file':'weather_context.json'
}
historical={}
for path in sorted((ROOT/'trials').glob('*/analysis.json')):
    analysis=json.loads(path.read_text(encoding='utf-8'))
    # These are the five human trials actually run so far, including the voided one.
    if analysis['trial_id'] not in (
        'B-EB5-own-black-first-01','B-EB5-own-plant-first-01',
        'B-EB5-plant-only-01','B-EB5-black-only-01',
        'B-EB5-cross-EC5-black-first-01'):
        continue
    environment={**common,'posture':'seated_on_floor_through_trousers',
                 'clothing_contact':'Trousers in contact with synthetic grass',
                 'source':'Operator retrospective report in chat',
                 'recorded_at_utc':now,'onset_or_change_during_trial':'not_independently_instrumented'}
    historical[analysis['trial_id']]=environment
    analysis['operator_environment']=environment
    limitation='Reported floor contact and footwear are environmental labels, not a measured body-to-earth impedance or proof of electrical isolation.'
    if limitation not in analysis['limitations']:analysis['limitations'].append(limitation)
    save(path,analysis)

context={
    'recorded_at_utc':now,
    'source':'Direct human clarification in current chat',
    'reported_statements':[
        'Todos los ensayos los he realizado estando sentado en el piso, a través del pantalón.',
        'Esto lo puedo hacer para las plantas EB5 y EC5 pero para las otras obligado debo estar de pie. El piso es un pasto sintético, levemente húmedo.'
    ],
    'current_environment':common,
    'next_trial_postures':{'EB5':'seated_on_floor_through_trousers','EC5':'seated_on_floor_through_trousers',
                           'ED5':'standing','EE5':'standing','EF5':'standing'},
    'retrospective_trials':historical,
    'scope':'Completed human contact trials only. Do not infer operator posture for initial untouched reference.',
    'unknowns':['Footwear during completed trials','Actual skin/floor contact impedance','Earth bonding of underlying floor'],
    'restriction':'Standing-only plants cannot serve as a posture control for seated EB5/EC5; compare posture within the same accessible plant.'
}
save(ROOT/'operator_environment.json',context)
method_path=ROOT/'methodology.json'
method=json.loads(method_path.read_text(encoding='utf-8'))
archive=ROOT/'methodology_v3_before_context.json'
if not archive.exists():archive.write_text(method_path.read_text(encoding='utf-8'),encoding='utf-8')
method['protocol']='caja5-contactos-v4'
method['operator_environment']={
    'metadata':'operator_environment.json',
    'ground_claim':'Record physical posture/material/moisture only. Clothing or footwear do not prove conductive grounding or complete electrical isolation.',
    'posture_conditions':['seated_on_floor_through_trousers','standing'],
    'footwear_conditions':['shoes','socks','barefoot','unknown'],
    'current_constraints':'EB5 and EC5 accessible seated or standing; EE5, EF5 and ED5 require standing.',
    'sequence':'Finish corrected cross-pair trial seated with same footwear. Complete the comparable EB5/EC5 contact conditions in that posture. Then use a selected identical contact subset within EB5/EC5 while standing; collect untouched rest after posture changes.',
    'control':'Keep same operator, plant contact location, contact order, pressure and timings. Change one planned factor per comparison. Alternate or repeat the posture order to check time drift.',
    'footwear_extension':'Shoes, socks and barefoot are distinct conditions. Compare only feasible volunteered conditions; do not assume socks and barefoot equivalent.',
    'weather':'Use time-stamped station observations as context with source, location and gaps; forecasts do not confirm rain. Operator reports local floor wetness; never infer it from a distant station alone.'
}
save(method_path,method)
with (ROOT/'captura_completa'/'markers.jsonl').open('a',encoding='utf-8') as stream:
    stream.write(json.dumps({'kind':'operator_environment_amendment','at_utc':now,
                            'host_monotonic_ns':time.monotonic_ns(),
                            'metadata_file':'operator_environment.json',
                            'affected_trials':list(historical),
                            'original_sensor_and_report_records':'unchanged'},ensure_ascii=False)+'\n')
print(json.dumps({'environment_recorded':True,'retrospective_trials':list(historical),'footwear':'unknown'}))
