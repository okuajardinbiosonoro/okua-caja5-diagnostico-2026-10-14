"""Analyze labelled trials without changing nodes, MIDI routing or controller state."""
import argparse
import json
import statistics
from datetime import datetime, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'captura_completa'
NODES={21:('EB5',6),22:('EC5',7),23:('ED5',8),24:('EE5',9),25:('EF5',10)}
METRICS=('raw','filt','base','rms_mean','occupancy','occupancy_base','adc_peak','samples','span_ms','score','threshold','noise_p95','transition_resets')

def stamp(row):
    return datetime.fromisoformat(row['at_utc'])

def summary(values):
    if not values:return None
    v=sorted(values)
    return {'n':len(v),'min':v[0],'median':statistics.median(v),'p95':v[int(.95*(len(v)-1))],'max':v[-1]}

def coverage(rows,lo,hi):
    if not rows:
        return {'leading_gap_s':None,'trailing_gap_s':None,'max_gap_including_boundaries_s':(hi-lo).total_seconds(),
                'first_frame_utc':None,'last_frame_utc':None,'no_frames':True}
    gaps=[(stamp(b)-stamp(a)).total_seconds() for a,b in zip(rows,rows[1:])]
    leading=(stamp(rows[0])-lo).total_seconds()
    trailing=(hi-stamp(rows[-1])).total_seconds()
    return {'leading_gap_s':leading,'trailing_gap_s':trailing,
            'max_gap_including_boundaries_s':max([leading,trailing]+gaps),
            'first_frame_utc':rows[0]['at_utc'],'last_frame_utc':rows[-1]['at_utc'],'no_frames':False}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('trial_id')
    args=parser.parse_args()
    correction_path=ROOT/'trials'/args.trial_id/'correction.json'
    correction=json.loads(correction_path.read_text(encoding='utf-8')) if correction_path.exists() else None
    markers=[]
    with (DATA/'markers.jsonl').open(encoding='utf-8') as f:
        for line in f:
            try:markers.append(json.loads(line))
            except json.JSONDecodeError:continue
    own=[r for r in markers if (r.get('trial') or {}).get('trial_id')==args.trial_id]
    started=[r for r in own if r['kind']=='trial_started']
    if len(started)!=1:raise RuntimeError('Need exactly one started trial for this identifier')
    start=stamp(started[0])
    endings=[r for r in own if r['kind'] in ('trial_completed','trial_aborted') and stamp(r)>start]
    if not endings:raise RuntimeError('Trial not ended')
    ending=endings[0];end=stamp(ending)
    phases=[r for r in own if r['kind']=='scheduled_instruction' and start<=stamp(r)<end]
    operator=next((r.get('operator_id') for r in own if r['kind']=='operator_started_trial' and abs((stamp(r)-start).total_seconds())<2),None)
    acks=[r for r in own if r['kind']=='display_ack' and r.get('operator_id')==operator]
    reports=[r for r in own if r['kind']=='operator_report' and stamp(r)>=end]
    records=[]
    with (DATA/'signals.jsonl').open(encoding='utf-8') as f:
        for line in f:
            try:r=json.loads(line)
            except json.JSONDecodeError:continue
            at=stamp(r)
            if start-timedelta(seconds=5)<=at<=end+timedelta(seconds=2):records.append(r)
            if at>end+timedelta(seconds=3):break
    midi=[r for r in records if r['kind']=='midi']
    intervals=[];open_notes={}
    for r in midi:
        m=r['message'];key=(r['channel'],m.get('note'))
        if m['type']=='note_on' and m.get('velocity',0)>0:
            if key in open_notes:intervals.append((key[0],open_notes.pop(key),stamp(r)))
            open_notes[key]=stamp(r)
        elif m['type']=='note_off' or (m['type']=='note_on' and m.get('velocity',0)==0):
            if key in open_notes:intervals.append((key[0],open_notes.pop(key),stamp(r)))
    for (ch,note),at in open_notes.items():intervals.append((ch,at,end+timedelta(seconds=2)))

    def note_duration(ch,lo,hi):
        parts=sorted((max(lo,a),min(hi,b)) for c,a,b in intervals if c==ch and a<hi and b>lo)
        merged=[]
        for a,b in parts:
            if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(merged[-1][1],b))
            else:merged.append((a,b))
        return sum((b-a).total_seconds() for a,b in merged)

    result={'trial_id':args.trial_id,'trial':started[0]['trial'],'start_utc':start.isoformat(),'end_utc':end.isoformat(),
            'actual_duration_s':(end-start).total_seconds(),'completed':ending['kind']=='trial_completed',
            'timer_completed':ending['kind']=='trial_completed','timer_end_event':ending,
            'operator_report':reports[-1] if reports else None,'confirmed_labels':reports[-1].get('confirmed_physical_labels',False) if reports else False,
            'operator_display_ack_delays_ms':[],'phases':[], 'runtime':{},
            'limitations':['Physical onset is operator-followed cue, not electronically instrumented.',
                           'Analogue scales are native firmware scales, not calibrated signed voltage.',
                           'MIDI note-duration estimate is not an audio recording.',
                           'Compare native sensor metrics within a node; installed firmware differs between nodes.']}
    context_path=ROOT/'operator_environment.json'
    context=json.loads(context_path.read_text(encoding='utf-8')) if context_path.exists() else {}
    result['operator_environment']=started[0]['trial'].get('operator_environment') or context.get('retrospective_trials',{}).get(args.trial_id)
    if correction and correction.get('operator_environment_correction'):
        result['operator_environment']={**(result['operator_environment'] or {}),
                                        **correction['operator_environment_correction']}
    schema_path=ROOT/'telemetry_schema.json'
    if schema_path.exists():result['sensor_metric_semantics']=json.loads(schema_path.read_text(encoding='utf-8'))
    result['limitations'].append('Reported floor contact and footwear are environmental labels, not a measured body-to-earth impedance or proof of electrical isolation.')
    for i,p in enumerate(phases):
        lo=stamp(p);hi=stamp(phases[i+1]) if i+1<len(phases) else end
        ack=next((a for a in acks if a['phase_seq']==p['phase_seq']),None)
        if ack:result['operator_display_ack_delays_ms'].append(round((stamp(ack)-lo).total_seconds()*1000,2))
        # Keep full phases and settled portions separate; retain transition samples in source.
        if p['phase']=='rest': stable_lo,stable_hi=lo+timedelta(seconds=5),hi
        elif p['phase'] in ('first_contact','contact'):stable_lo,stable_hi=lo+timedelta(seconds=3),hi-timedelta(seconds=2)
        elif p['phase']=='release':stable_lo,stable_hi=hi-timedelta(seconds=15),hi
        elif p['phase']=='preparation' and started[0]['trial'].get('reference_before_s'):
            stable_lo,stable_hi=lo+timedelta(seconds=10),hi
        else:stable_lo,stable_hi=lo,hi
        timing_annotation=next((t for t in (correction or {}).get('timing_adjustments',[])
                                if t.get('repetition')==p['repetition'] and t.get('phase')==p['phase']),None)
        if timing_annotation and timing_annotation.get('operator_followed_delayed_cue') and ack:
            stable_lo=max(stable_lo,stamp(ack)+timedelta(seconds=3))
            stable_lo=min(stable_lo,stable_hi)
        phase={'repetition':p['repetition'],'phase':p['phase'],'start_utc':lo.isoformat(),'end_utc':hi.isoformat(),
               'stable_start_utc':stable_lo.isoformat(),'stable_end_utc':stable_hi.isoformat(),
               'operator_display_ack':ack,'instruction':p.get('instruction'),'nodes':{}}
        if p.get('sequence_step'):phase['sequence_step']=p['sequence_step']
        if timing_annotation:
            phase['timing_annotation']=timing_annotation
            phase['stable_duration_s']=(stable_hi-stable_lo).total_seconds()
            phase['shortened_stable_window']=phase['stable_duration_s']<2
        for nid,(label,ch) in NODES.items():
            full=[r for r in records if r['kind']=='sensor' and r['node_id']==nid and lo<=stamp(r)<hi]
            stable=[r for r in full if stable_lo<=stamp(r)<stable_hi]
            music=[r for r in midi if r['channel']==ch and lo<=stamp(r)<hi]
            ons=[r for r in music if r['message']['type']=='note_on' and r['message'].get('velocity',0)>0]
            gaps=[(stamp(b)-stamp(a)).total_seconds() for a,b in zip(full,full[1:])]
            phase['nodes'][label]={
                'frames':len(full),'stable_frames':len(stable),'max_gap_s':max(gaps) if gaps else None,
                'detailed_sensor_available':nid!=23,
                'coverage':coverage(full,lo,hi) if nid!=23 else None,
                'stable_coverage':coverage(stable,stable_lo,stable_hi) if nid!=23 else None,
                'active_fraction':sum(r['values'].get('plant_active')=='1' for r in full)/len(full) if full else None,
                'stable_active_fraction':sum(r['values'].get('plant_active')=='1' for r in stable)/len(stable) if stable else None,
                'metrics':{key:summary([float(r['values'][key]) for r in stable if key in r['values']]) for key in METRICS if any(key in r['values'] for r in stable)},
                'midi_note_ons':len(ons),'midi_note_pitches':sorted(set(r['message']['note'] for r in ons)),
                'midi_pitch_summary':summary([r['message']['note'] for r in ons]),
                'midi_note_duration_s':note_duration(ch,lo,hi),'stable_midi_note_duration_s':note_duration(ch,stable_lo,stable_hi)
            }
        result['phases'].append(phase)
    for nid,(label,ch) in NODES.items():
        states=[r['runtime'] for r in records if r['kind']=='ckv2' and r['node_id']==nid and start<=stamp(r)<=end]
        uptime=[r['last_uptime_s'] for r in states]
        result['runtime'][label]={'samples':len(states),'statuses':sorted(set(r['status'] for r in states)),
                                  'uptime_decreased':any(b<a for a,b in zip(uptime,uptime[1:]))}
    finished={(r.get('repetition'),r.get('phase')) for r in own if r['kind']=='phase_finished' and start<=stamp(r)<=end}
    paired=started[0]['trial']['condition'] in ('own_pair','cross_pair')
    sequence=started[0]['trial']['condition']=='soil_sequence'
    reps=range(1,5) if sequence else (1,2,3)
    report=result['operator_report']['report'] if result['operator_report'] else {}
    valid_reps=[]
    for repetition in reps:
        required={'rest','contact'}|({'first_contact'} if paired else set())
        confirmed=result['confirmed_labels'] and repetition<=report.get('completed_repetitions',0)
        if sequence:
            node=('EB5','EC5','EE5','EF5')[repetition-1]
            block=next((b for b in report.get('block_reports',[]) if b.get('node')==node),{})
            required={'rest','contact'}|({'first_contact'} if node!='EB5' else set())
            placed=any(r['kind']=='operator_ground_placed' for r in own)
            confirmed=result['confirmed_labels'] and report.get('grounded_black_kept_fixed') is True and placed and block.get('confirmed_contacts') is True
        if confirmed and all((repetition,p) in finished for p in required):
            valid_reps.append(repetition)
    complete_recovery=[r for r in reps if (r,'release') in finished]
    result['validity']={
        'operator_confirmed':result['confirmed_labels'],
        'valid_contact_repetitions':valid_reps,
        'complete_recovery_repetitions':complete_recovery,
        'timer_abort_does_not_discard_prior_finished_contact_phases':True,
        'operator_incident_notes':report.get('notes',''),
        'assessment':'all_contact_phases_confirmed_final_recovery_truncated' if len(valid_reps)==3 and not result['timer_completed'] else 'all_contact_phases_confirmed' if len(valid_reps)==3 else 'partial_or_unconfirmed_contact_phases',
        'data_after_timer_end':'Retained in source recording, excluded from labelled phase comparisons'
    }
    result['data_quality']={
        'coverage_gap_flag_s':1.0,
        'operator_ack_delay_flag_s':1.0,
        'meaning':'Flags missing host-received telemetry, including phase boundaries; does not prove a node reboot or missing analogue response.',
        'sensor_coverage_warnings':[{'node':name,'repetition':p['repetition'],'phase':p['phase'],'coverage':node['coverage']}
                                    for p in result['phases'] for name,node in p['nodes'].items()
                                    if node['coverage'] is not None and node['coverage']['max_gap_including_boundaries_s']>1.0]
    }
    result['data_quality']['operator_ack_delay_warnings']=[
        {'repetition':p['repetition'],'phase':p['phase'],
         'receipt_delay_s':(stamp(p['operator_display_ack'])-datetime.fromisoformat(p['start_utc'])).total_seconds(),
         'meaning':'Host receipt delay; not an instrumented physical touch onset or audio emission timestamp.'}
        for p in result['phases'] if p['operator_display_ack'] is not None
        and (stamp(p['operator_display_ack'])-datetime.fromisoformat(p['start_utc'])).total_seconds()>1.0]
    if sequence:
        placements=[r for r in own if r['kind']=='operator_ground_placed']
        result['ground_placement_confirmation']=placements[-1] if placements else None
        result['validity'].update({'count_meaning':'plant blocks, one pass per plant',
                                  'operator_confirmed_ground_kept_fixed':report.get('grounded_black_kept_fixed') is True,
                                  'ground_placement_confirmed':bool(placements),
                                  'valid_plant_blocks':[('EB5','EC5','EE5','EF5')[r-1] for r in valid_reps],
                                  'assessment':'sequence_blocks_confirmed' if len(valid_reps)==4 else 'partial_or_unconfirmed_sequence_blocks'})
    if correction:
        result['operator_correction']=correction
        if correction.get('timing_adjustments'):
            result['validity']['timing_adjustments']=correction['timing_adjustments']
            result['validity']['assessment']='contact_phases_confirmed_with_documented_delayed_cue'
            result['validity']['repetitions_without_recorded_cue_delay']=[r for r in valid_reps if r not in {t['repetition'] for t in correction['timing_adjustments']}]
        phase_exclusions=correction.get('phase_exclusions',[])
        for p in result['phases']:
            matched=[e for e in phase_exclusions if e.get('repetition')==p['repetition'] and e.get('phase')==p['phase']]
            if matched:
                p['excluded_from_labelled_comparisons']=True
                p['exclusion_reasons']=matched
        if phase_exclusions:
            excluded_reps={e['repetition'] for e in phase_exclusions}
            result['validity'].update({
                'phase_exclusions':phase_exclusions,
                'clean_rest_contact_comparison_repetitions':[r for r in valid_reps if r not in excluded_reps],
                'assessment':'contact_phases_confirmed_with_reference_phase_exclusions',
                'exclusion_scope':'Excluded reference phases are preserved; do not use them as uncontaminated baseline for quantitative comparisons.'
            })
        if correction.get('void_planned_trial'):
            result['original_operator_declared_followed_cues']=result['confirmed_labels']
            result['confirmed_labels']=False
            result['validity'].update({
                'operator_confirmed':False,
                'operator_original_confirmation':result['original_operator_declared_followed_cues'],
                'valid_contact_repetitions':[],
                'assessment':correction.get('assessment','excluded_wrong_plant_or_contact_condition'),
                'excluded_from_planned_comparisons':True,
                'actual_reported_contacts':correction.get('actual_reported_contacts'),
                'correction_reason':correction.get('reason')
            })
    out=ROOT/'trials'/args.trial_id
    out.mkdir(parents=True,exist_ok=True)
    (out/'analysis.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    target=started[0]['trial']['plant_node']
    compact=[]
    for p in result['phases']:
        if p['repetition']==0:continue
        phase_target=(p.get('sequence_step') or {}).get('plant_node') or target
        t=p['nodes'][phase_target]
        compact.append({'rep':p['repetition'],'node':phase_target,'phase':p['phase'],'frames':t['frames'],
                        'adc_mean_median':t['metrics'].get('rms_mean',{}).get('median'),
                        'filt_median':t['metrics'].get('filt',{}).get('median'),
                        'occupancy_median':t['metrics'].get('occupancy',{}).get('median'),
                        'active_pct':None if t['active_fraction'] is None else round(t['active_fraction']*100,1),
                        'stable_active_pct':None if t['stable_active_fraction'] is None else round(t['stable_active_fraction']*100,1),
                        'notes':t['midi_note_ons'],'pitches':t['midi_note_pitches'],
                        'note_duration':round(t['midi_note_duration_s'],2),
                        'other_notes':{k:v['midi_note_ons'] for k,v in p['nodes'].items() if k!=phase_target},
                        'other_adc_mean':{k:v['metrics'].get('rms_mean',{}).get('median') for k,v in p['nodes'].items() if k!=phase_target},
                        'max_gap_s':t['max_gap_s']})
    print(json.dumps({'trial_id':args.trial_id,'completed':result['completed'],'confirmed_labels':result['confirmed_labels'],'validity':result['validity'],
                      'display_delays_ms':summary(result['operator_display_ack_delays_ms']), 'phases':compact, 'runtime':result['runtime']},indent=2))

if __name__=='__main__':main()
