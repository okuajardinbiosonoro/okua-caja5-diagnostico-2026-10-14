"""Correct derived metric names; preserve original telemetry and archived reports."""
import json
import time
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
now=datetime.now(timezone.utc).isoformat(timespec='milliseconds')
schema={
    'recorded_at_utc':now,
    'verified_firmware':'1.1.13-box5-touch-pilot',
    'applicable_nodes':['EB5','EC5'],
    'source_files':['diagnostics/eb5_touch_pilot_20261012/pilot.patch','diagnostics/eb5_touch_pilot_20261012/adaptive_touch_pilot.h'],
    'verified_assignments':{
        'rms_mean':'g_pilotMean = g_pilotAcquisition.mean: arithmetic ADC-window mean',
        'filt':'g_plantSmoothV = feature.rms: ADC-window RMS used by the detector',
        'base':'g_plantBaselineV = g_pilotDetector.referenceRms: RMS reference',
        'threshold':'g_pilotDetector.thresholdRms',
        'score':'g_pilotDetector.amplitudeScore: absolute RMS-reference difference / RMS threshold',
        'noise_p95':'g_pilotDetector.noiseRms',
        'occupancy':'fraction of acquired ADC samples above zero',
        'transition_resets':'Detector medium-transition recalibrations; not a board reboot counter'
    },
    'scale':'Nominal ADC conversion, not calibrated signed analogue voltage.',
    'other_firmware':'Do not apply these assignments to EE5/EF5 without separately verifying their implementation.',
    'historical_reports':'Earlier derived RMS labels referring to rms_mean describe arithmetic mean. Numerical raw readings are unchanged.'
}
(ROOT/'telemetry_schema.json').write_text(json.dumps(schema,indent=2,ensure_ascii=False),encoding='utf-8')
archive=ROOT/'metric_labels_before_correction'
archive.mkdir(exist_ok=True)
changed=[]
def rename(value):
    if isinstance(value,dict):
        return {key.replace('RMS','ADC_mean').replace('rms_median','adc_mean_median'):rename(v) for key,v in value.items()}
    if isinstance(value,list):return [rename(v) for v in value]
    if isinstance(value,str):return value.replace('RMS','ADC arithmetic mean')
    return value
for path in sorted((ROOT/'trials').glob('**/*.json')):
    if path.name in ('correction.json','analysis_console.json','detector_state_transitions.json','analysis_before_cue_adjustment.json'):
        continue
    value=json.loads(path.read_text(encoding='utf-8'))
    if path.name=='analysis.json':
        value['sensor_metric_semantics']=schema
    else:
        target=archive/path.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():target.write_text(path.read_text(encoding='utf-8'),encoding='utf-8')
        value=rename(value)
        value['metric_label_correction']={
            'at_utc':now,'schema':'telemetry_schema.json',
            'arithmetic_mean_field':'rms_mean','true_RMS_field_for_EB5_EC5_pilot':'filt',
            'original_before_correction':str(target.relative_to(ROOT))}
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')
    changed.append(str(path.relative_to(ROOT)))
method_path=ROOT/'methodology.json'
method=json.loads(method_path.read_text(encoding='utf-8'))
method['observation']['sensor_metric_semantics']='telemetry_schema.json: for EB5/EC5 pilot, filt is RMS and rms_mean is arithmetic ADC mean. Never compare rms_mean directly to base/threshold as if it were RMS.'
method_path.write_text(json.dumps(method,indent=2,ensure_ascii=False),encoding='utf-8')
with (ROOT/'captura_completa/markers.jsonl').open('a',encoding='utf-8') as f:
    f.write(json.dumps({'kind':'derived_metric_label_correction','at_utc':now,
                        'host_monotonic_ns':time.monotonic_ns(),
                        'schema':'telemetry_schema.json','changed_reports':changed,
                        'raw_telemetry_and_operator_reports':'unchanged'},ensure_ascii=False)+'\n')
print(json.dumps({'schema_saved':True,'corrected_derived_reports':len(changed),'raw_telemetry_changed':False}))
