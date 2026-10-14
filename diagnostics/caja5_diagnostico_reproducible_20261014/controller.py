"""Local operator timing and trace. Only records labels; never commands nodes or MIDI."""
import argparse
import ipaddress
import json
import math
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from soil_sequence import configure as configure_soil_sequence

ROOT = Path(__file__).resolve().parent
CAPTURE = ROOT / 'captura_completa'
PORT = 8986
UI_REVISION = 8
LAN_IP = None
LAN_NETWORK = None
LOCK = threading.RLock()
STOP = threading.Event()
TRACE = CAPTURE / 'markers.jsonl'
LABELS = ('EB5', 'EC5', 'ED5', 'EE5', 'EF5')
CONDITIONS = ('own_pair', 'plant_only', 'black_only', 'cross_pair', 'sham','soil_sequence')
STATE = {'mode': 'idle', 'trial': None, 'phase': None, 'phase_seq': 0,
         'phase_deadline': None, 'baseline_deadline': None, 'baseline_done': False,
         'armed': None, 'last_completed': None, 'trials': 0, 'operator_id': None}

def utc():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')

def record(kind, **values):
    row = {'at_utc': utc(), 'host_monotonic_ns': time.monotonic_ns(),
           'kind': kind, **values}
    with LOCK, TRACE.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + '\n')

def environment_for(plant):
    path=ROOT/'operator_environment.json'
    if not path.exists():
        return {'posture':'unknown','footwear':'unknown'}
    context=json.loads(path.read_text(encoding='utf-8'))
    return {**context['current_environment'],
            'posture':context['next_trial_postures'].get(plant,'unknown'),
            'metadata_source':path.name,
            'reported_at_utc':context['recorded_at_utc']}

def instructions(config):
    if config['condition']=='soil_sequence':
        return 'Una pasada: EB5 solo planta; EC5, EE5 y EF5 primero planta sola y despues su propio negro, sin soltar la planta. Negro EB5 fijo en sustrato durante todos los contactos.'
    plant, black = config['plant_node'], config['black_node']
    return {
        'own_pair': f'Toca la planta {plant} con una mano y la punta negra marcada {black} con la otra. Manten AMBOS contactos continuos durante los 20 segundos. La pinza roja permanece fijada a la planta; el contacto de tu mano es con la planta.',
        'plant_only': f'Toca SOLO la planta {plant} con una mano durante los 20 segundos. Deja la otra mano libre. Ninguna mano toca ninguna punta negra.',
        'black_only': f'Toca SOLO la punta negra marcada {black} con una mano durante los 20 segundos. Deja la otra mano libre. Ninguna mano toca ninguna planta.',
        'cross_pair': f'Toca la planta {plant} con una mano y la punta negra marcada {black} con la otra. Manten AMBOS contactos continuos durante los 20 segundos. Usa exactamente esa punta negra, identificada con un nodo distinto de la planta.',
        'sham': f'Acerca una mano a unos 5 cm de la planta {plant}, sin tocarla. Ninguna mano toca ninguna planta ni punta negra durante los 20 segundos.'
    }[config['condition']]

def phase_instructions(config,step_index=None):
    if config['condition']=='soil_sequence':
        index=STATE.get('step_index',0) if step_index is None else step_index
        step=config['sequence_steps'][index or 0]
        return {step['phase']:step['instruction']}
    plant, black = config['plant_node'], config['black_node']
    condition = config['condition']
    paired = condition in ('own_pair','cross_pair')
    order = config.get('contact_order')
    rest='Deja AMBAS manos libres: no toques ninguna planta ni ninguna punta negra. Mantente quieto. No sostengas el negro durante el reposo.'
    release={
        'own_pair':f'SUELTA AMBOS: retira una mano de la planta {plant} y la otra de la punta negra {black}. Deja ambas manos libres y todo quieto durante los 30 segundos.',
        'cross_pair':f'SUELTA AMBOS: retira una mano de la planta {plant} y la otra de la punta negra {black}. Deja ambas manos libres y todo quieto durante los 30 segundos.',
        'plant_only':f'SUELTA LA PLANTA {plant}. Deja ambas manos libres. No toques ninguna planta ni ninguna punta negra durante los 30 segundos.',
        'black_only':f'SUELTA LA PUNTA NEGRA {black}. Deja ambas manos libres. No toques ninguna planta ni ninguna punta negra durante los 30 segundos.',
        'sham':'Retira la mano de la cercania de la planta. Deja ambas manos libres, sin tocar plantas ni puntas negras durante los 30 segundos.'
    }[condition]
    title={
        'own_pair':'PLANTA + NEGRO PROPIO', 'cross_pair':'PLANTA + OTRO NEGRO',
        'plant_only':'SOLO PLANTA', 'black_only':'SOLO PUNTA NEGRA', 'sham':'ACERCAR SIN TOCAR'
    }[condition]
    contact_voice={
        'own_pair':f'Toca ahora: planta {plant} con una mano y punta negra {black} con la otra.',
        'cross_pair':f'Toca ahora: planta {plant} con una mano y punta negra {black} con la otra.',
        'plant_only':f'Toca ahora solo la planta {plant}. No toques el negro.',
        'black_only':f'Toca ahora solo la punta negra {black}. No toques plantas.',
        'sham':f'Acerca la mano a la planta {plant}, sin tocar nada.'
    }[condition]
    first = None
    if paired:
        if order=='black_first':
            first={'title':f'1. SOLO NEGRO {black}', 'instruction':f'Toca SOLO la punta negra marcada {black} con una mano durante 10 segundos. La otra mano queda libre y no toca ninguna planta. Manten este negro sujeto hasta que termine la fase de ambos contactos.', 'spoken':f'Primero toca solo el negro {black}. No toques la planta.'}
            contact_text=f'2. SIN SOLTAR la punta negra marcada {black}, agrega la PLANTA identificada por la etiqueta ROJA {plant} con la otra mano. Manten ambos contactos durante 20 segundos. Tu mano toca la planta; la pinza roja queda fijada.'
            contact_voice=f'Sin soltar el negro {black}, agrega el contacto con la planta {plant} usando la otra mano.'
        else:
            first={'title':f'1. SOLO PLANTA {plant}', 'instruction':f'Toca SOLO la planta {plant} con una mano durante 10 segundos. La otra mano queda libre y no toca ninguna punta negra. Manten la mano en la planta hasta que termine la fase de ambos contactos.', 'spoken':f'Primero toca solo la planta {plant}. No toques el negro.'}
            contact_text=f'2. SIN SOLTAR la PLANTA identificada por la etiqueta ROJA {plant}, agrega la punta NEGRA marcada {black} con la otra mano. Manten ambos contactos durante 20 segundos.'
            contact_voice=f'Sin soltar la planta {plant}, agrega el contacto con el negro {black} usando la otra mano.'
    else:
        contact_text=instructions(config)
    if condition=='cross_pair':
        contact_text+=f' La planta con etiqueta roja {black} queda SIN TOCAR durante todo el ensayo.'
    release_voice='Suelta ambos: planta y punta negra. Deja ambas manos libres.' if condition in ('own_pair','cross_pair') else 'Suelta la planta. Ambas manos libres.' if condition=='plant_only' else 'Suelta la punta negra. Ambas manos libres.' if condition=='black_only' else 'Retira la mano. No toques nada.'
    result = {
        'preparation':{'title':'PREPARATE SIN TOCAR','instruction':rest+' El contacto empezara despues del reposo, cuando aparezca la indicacion de contacto.','spoken':'Preparate con ambas manos libres. Todavia no toques nada.'},
        'rest':{'title':'REPOSO: MANOS LIBRES','instruction':rest,'spoken':'Reposo. Ambas manos libres, sin tocar plantas ni puntas negras.'},
        'contact':{'title':(f'2. AGREGA PLANTA {plant}' if order=='black_first' else f'2. AGREGA NEGRO {black}') if paired else 'TOCA: '+title,'instruction':contact_text,'spoken':contact_voice},
        'release':{'title':'SUELTA AMBOS' if condition in ('own_pair','cross_pair') else 'SUELTA LA PLANTA' if condition=='plant_only' else 'SUELTA EL NEGRO' if condition=='black_only' else 'RETIRA LA MANO','instruction':release,'spoken':release_voice}
    }
    if first:
        result['first_contact']=first
    if config.get('reference_before_s'):
        result['preparation']={
            'title':'REFERENCIA: MANOS LIBRES',
            'instruction':rest+' Hay 10 segundos para acomodarte y luego 120 segundos de referencia sin contacto. No toques hasta la indicacion de contacto despues del reposo.',
            'spoken':'Referencia inicial. Ambas manos libres, sin tocar plantas ni puntas negras. Mantente quieto durante dos minutos y diez segundos.'
        }
    return result

def phase_schedule(config):
    if config['condition']=='soil_sequence':
        return [(s['repetition'],s['phase'],s['duration_s']) for s in config['sequence_steps']]
    paired=config['condition'] in ('own_pair','cross_pair')
    phases=[('rest',20)] + ([('first_contact',10)] if paired else []) + [('contact',20),('release',30)]
    return [(0,'preparation',10+config.get('reference_before_s',0))]+[(r,p,d) for r in range(1,4) for p,d in phases]

def status():
    with LOCK:
        now = time.monotonic()
        s = dict(STATE)
        s['at_utc'] = utc()
        s['ui_revision'] = UI_REVISION
        s['remaining_s'] = max(0, math.ceil((s['phase_deadline'] or now)-now))
        s['baseline_remaining_s'] = max(0, math.ceil((s['baseline_deadline'] or now)-now))
        s.pop('phase_deadline')
        s.pop('baseline_deadline')
        config = s['trial'] or s['armed']
        s['instruction'] = instructions(config) if config else 'Esperando ensayo coordinado.'
        s['phase_instructions'] = phase_instructions(config) if config else None
        s['schedule'] = [{'repetition':r,'phase':p,'duration_s':d} for r,p,d in phase_schedule(config)] if config else []
        s['duration_s'] = sum(d for _,_,d in phase_schedule(config)) if config else 0
        s['active_step']=config['sequence_steps'][STATE.get('step_index',0) or 0] if config and config['condition']=='soil_sequence' else None
        return s

def assert_capture_ready():
    now=datetime.now(timezone.utc)
    path=CAPTURE/'signals.jsonl'
    with path.open('rb') as stream:
        stream.seek(max(0,path.stat().st_size-262144))
        lines=stream.read().decode('utf-8',errors='replace').splitlines()
    latest={}
    for line in lines:
        try:row=json.loads(line)
        except json.JSONDecodeError:continue
        if row.get('kind')=='sensor':latest[row['node_id']]=datetime.fromisoformat(row['at_utc'])
    missing=[nid for nid in (21,22,24,25) if nid not in latest or (now-latest[nid]).total_seconds()>5]
    if missing:
        raise ValueError('Captura incompleta o detenida; espera a que se restablezcan los datos antes de iniciar')

def begin_phase(name, duration, repetition,step_index=0):
    STATE['phase_seq'] += 1
    STATE['phase'] = name
    STATE['phase_deadline'] = time.monotonic() + duration
    STATE['repetition'] = repetition
    STATE['step_index']=step_index
    STATE['ground_placement_complete']=False
    record('scheduled_instruction', trial=STATE['trial'], phase=name,
           repetition=repetition, duration_s=duration, phase_seq=STATE['phase_seq'],
           ui_revision=UI_REVISION, instruction=phase_instructions(STATE['trial'],step_index)[name],
           sequence_step=STATE['trial']['sequence_steps'][step_index] if STATE['trial']['condition']=='soil_sequence' else None)

def run_trial(config):
    # /start publishes the first phase atomically before any running state is visible.
    for index,(repetition, name, duration) in enumerate(phase_schedule(config)):
        with LOCK:
            if STATE['mode'] != 'running' or STATE['trial'] != config:
                return
            if index:
                begin_phase(name, duration, repetition,index)
            sequence = STATE['phase_seq']
        while not STOP.wait(0.04):
            with LOCK:
                if STATE['mode'] != 'running' or STATE['phase_seq'] != sequence:
                    return
                placement_done=name=='ground_placement' and STATE['ground_placement_complete']
                expired=time.monotonic()>=STATE['phase_deadline']
                if expired and name=='ground_placement' and not placement_done:
                    record('trial_aborted',trial=config,reason='Ground placement not confirmed within 60 seconds',phase=name)
                    STATE.update(last_completed=config,mode='awaiting_report',phase='aborted',phase_deadline=None)
                    STATE['phase_seq']+=1
                    return
                if expired or placement_done:
                    record('phase_finished', trial=config, phase=name,
                           repetition=repetition,
                           completion_reason='operator_ground_placed' if placement_done else 'scheduled_duration',
                           lateness_ms=max(0,round((time.monotonic()-STATE['phase_deadline'])*1000, 1)))
                    break
        if STOP.is_set():
            return
    with LOCK:
        record('trial_completed', trial=config, requires_operator_report=True)
        STATE['last_completed'] = config
        STATE['mode'] = 'awaiting_report'
        STATE['phase'] = 'done'
        STATE['phase_seq'] += 1
        STATE['phase_deadline'] = None

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, code, payload, mime='application/json'):
        data = payload.encode('utf-8') if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', mime + '; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def allowed_client(self):
        client = ipaddress.ip_address(self.client_address[0])
        return client.is_loopback or (LAN_NETWORK is not None and client in LAN_NETWORK)

    def is_local_admin(self):
        return ipaddress.ip_address(self.client_address[0]).is_loopback

    def do_GET(self):
        if not self.allowed_client():
            self.respond(403, {'error':'Outside local experiment network'})
            return
        if self.path == '/':
            record('operator_view_opened', client_address=self.client_address[0],
                   user_agent=self.headers.get('User-Agent','')[:300])
            self.respond(200, (ROOT/'temporizador.html').read_text(encoding='utf-8'), 'text/html')
        elif self.path == '/status':
            self.respond(200, status())
        elif self.path=='/soil-sequence.js':
            self.respond(200,(ROOT/'soil-sequence.js').read_text(encoding='utf-8'),'application/javascript')
        else:
            self.respond(404, {'error':'Not found'})

    def do_POST(self):
        if not self.allowed_client():
            self.respond(403, {'error':'Outside local experiment network'})
            return
        origin = self.headers.get('Origin')
        origins = {f'http://127.0.0.1:{PORT}', f'http://localhost:{PORT}'}
        if LAN_IP:
            origins.add(f'http://{LAN_IP}:{PORT}')
        if origin and origin not in origins:
            self.respond(403, {'error':'Origin rejected'})
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 <= length <= 8192:
                raise ValueError('Body too large')
            value = json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(value, dict):
                raise ValueError('Object required')
            with LOCK:
                if self.path == '/arm':
                    if not self.is_local_admin():
                        self.respond(403, {'error':'Only local coordinator can arm trials'})
                        return
                    if STATE['mode'] == 'running':
                        raise ValueError('Trial running')
                    config = {k:value[k] for k in ('trial_id','plant_node','black_node','condition')}
                    if config['plant_node'] not in LABELS or config['black_node'] not in LABELS or config['condition'] not in CONDITIONS:
                        raise ValueError('Unknown node or condition')
                    if len(config['trial_id']) > 80:
                        raise ValueError('Invalid identifier')
                    if config['condition']=='soil_sequence':
                        configure_soil_sequence(config)
                    if config['condition']=='own_pair' and config['plant_node']!=config['black_node']:
                        raise ValueError('Own pair requires same node')
                    if config['condition']=='cross_pair' and config['plant_node']==config['black_node']:
                        raise ValueError('Cross pair requires different nodes')
                    if config['condition'] in ('own_pair','cross_pair'):
                        if value.get('contact_order') not in ('black_first','plant_first'):
                            raise ValueError('Paired trial requires an explicit contact order')
                        config['contact_order']=value['contact_order']
                    reference_before=value.get('reference_before_s',0)
                    if isinstance(reference_before,bool) or reference_before not in (0,120):
                        raise ValueError('Reference must be absent or 120 seconds')
                    if reference_before:
                        config['reference_before_s']=reference_before
                    if STATE['mode']=='awaiting_report':
                        raise ValueError('Previous trial still requires operator report')
                    config['operator_environment']=environment_for(config['plant_node'])
                    if config['condition']=='soil_sequence':
                        config['operator_environment'].update(posture='standing',footwear='shoes',
                            posture_source='Direct user request: entire soil sequence standing with shoes')
                    STATE['step_index']=0
                    STATE['armed']=config
                    STATE['mode']='armed'
                    record('trial_armed', trial=config)
                elif self.path == '/start':
                    if value.get('ui_revision') != UI_REVISION:
                        raise ValueError('Recarga el temporizador: las instrucciones se actualizaron')
                    if not STATE['baseline_done'] or STATE['mode']!='armed' or not STATE['armed']:
                        raise ValueError('Not ready')
                    assert_capture_ready()
                    # Reserve state before launching so double clicks cannot start two threads.
                    config = dict(STATE['armed'])
                    if config['condition']=='soil_sequence' and value.get('all_black_free') is not True:
                        raise ValueError('Confirma que todos los negros estan al aire antes de iniciar')
                    footwear=value.get('footwear','unknown')
                    if footwear not in ('shoes','socks','barefoot','unknown'):
                        raise ValueError('Invalid footwear condition')
                    if config['condition']=='soil_sequence' and footwear!=config['fixed_footwear']:
                        raise ValueError('Esta corrida fue definida de pie con zapatos')
                    config['operator_environment']={**config['operator_environment'],
                                                  'footwear':footwear,
                                                  'footwear_source':'Operator selection at trial start'}
                    operator_id = value.get('operator_id')
                    if not isinstance(operator_id,str) or not 8 <= len(operator_id) <= 80:
                        raise ValueError('Operator identifier required')
                    STATE['operator_id'] = operator_id
                    record('operator_started_trial', operator_id=operator_id,
                           client_address=self.client_address[0], trial=config)
                    STATE['trial']=config
                    STATE['armed']=None
                    record('trial_started', trial=config, ui_revision=UI_REVISION,
                           label_quality='Scheduled physical conditions; require operator confirmation. Not instrumented touch onset.')
                    begin_phase('preparation',phase_schedule(config)[0][2],0)
                    STATE['mode']='running'
                    threading.Thread(target=run_trial,args=(config,),daemon=True).start()
                elif self.path=='/ground_placed':
                    if value.get('operator_id')!=STATE['operator_id']:
                        raise ValueError('Only active operator can confirm soil placement')
                    if STATE['mode']!='running' or STATE['phase']!='ground_placement':
                        raise ValueError('Not in ground placement phase')
                    if STATE['ground_placement_complete']:
                        raise ValueError('Placement already confirmed')
                    moisture=value.get('soil_moisture','unknown')
                    if moisture not in ('unknown','dry','slightly_damp','damp','very_wet'):
                        raise ValueError('Invalid soil moisture label')
                    depth=value.get('depth_cm')
                    if depth is not None and (isinstance(depth,bool) or not isinstance(depth,(int,float)) or not 0<=depth<=20):
                        raise ValueError('Invalid soil depth')
                    record('operator_ground_placed',trial=STATE['trial'],operator_id=STATE['operator_id'],
                           client_address=self.client_address[0],grounded_black_node='EB5',
                           location='substrate_of_EB5_pot',hands_free_declared=True,
                           soil_moisture=moisture,depth_cm=depth)
                    STATE['ground_placement_complete']=True
                elif self.path == '/abort':
                    if value.get('operator_id') != STATE['operator_id'] and not self.is_local_admin():
                        raise ValueError('Only active operator can abort')
                    if STATE['mode']=='running':
                        record('trial_aborted', trial=STATE['trial'], reason=value.get('reason','Operator aborted'),
                               phase=STATE['phase'], repetition=STATE.get('repetition'),
                               client_address=self.client_address[0],
                               client_error=value.get('client_error'), client_stage=value.get('client_stage'))
                        STATE['last_completed']=STATE['trial']
                        STATE['mode']='awaiting_report'
                        STATE['phase']='aborted'
                        STATE['phase_seq']+=1
                        STATE['phase_deadline']=None
                elif self.path == '/report':
                    if STATE['mode']!='awaiting_report':
                        raise ValueError('No completed trial pending')
                    limit=4 if STATE['last_completed']['condition']=='soil_sequence' else 3
                    if value.get('completed_repetitions') not in range(limit+1):
                        raise ValueError('Invalid repetition count')
                    if limit==4:
                        blocks=value.get('block_reports')
                        if not isinstance(blocks,list) or len(blocks)!=4 or {b.get('node') for b in blocks} != {'EB5','EC5','EE5','EF5'}:
                            raise ValueError('Se requiere un informe para cada una de las cuatro plantas')
                        if any(not isinstance(b.get('confirmed_contacts'),bool) for b in blocks):
                            raise ValueError('Confirm each plant contact block')
                    record('operator_report', trial=STATE['last_completed'], report=value,
                           client_address=self.client_address[0],
                           confirmed_physical_labels=value.get('followed_cues',False) is True)
                    STATE['mode']='idle'
                    STATE['trial']=None
                    STATE['phase']=None
                elif self.path == '/display_ack':
                    record('display_ack', trial=STATE['trial'], phase_seq=value.get('phase_seq'),
                           operator_id=value.get('operator_id'), client_address=self.client_address[0],
                           client_ui_revision=value.get('ui_revision'), client_note=value.get('client_note'),
                           client_utc=value.get('client_utc'), visibility=value.get('visibility'),
                           client_render_utc=value.get('client_render_utc'),
                           cue_dispatch_utc=value.get('cue_dispatch_utc'))
                else:
                    self.respond(404, {'error':'Not found'})
                    return
            self.respond(200, status())
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            self.respond(409, {'error':str(error)})

def main():
    global LAN_IP, LAN_NETWORK
    parser=argparse.ArgumentParser()
    parser.add_argument('--lan-ip')
    args=parser.parse_args()
    if args.lan_ip:
        address=ipaddress.ip_address(args.lan_ip)
        if address not in ipaddress.ip_network('192.168.1.0/24'):
            raise ValueError('Unexpected experiment LAN')
        LAN_IP=str(address)
        LAN_NETWORK=ipaddress.ip_network('192.168.1.0/24')
    started = None
    with (CAPTURE/'signals.jsonl').open(encoding='utf-8') as f:
        for line in f:
            row=json.loads(line)
            if row['kind']=='started':
                started=row['at_utc']
                break
    if not started:
        raise RuntimeError('Capture not started')
    age=(datetime.now(timezone.utc)-datetime.fromisoformat(started)).total_seconds()
    STATE['baseline_deadline']=time.monotonic()+max(0,300-age)
    STATE['baseline_done']=age>=300
    record('baseline_reference_reused' if STATE['baseline_done'] else 'baseline_declared', start_utc=started, duration_s=300,
           condition='glass_on_all_black_electrodes_free_no_contact',
           source='User confirmed caja 5 lista before capture',
           initial_incomplete_capture='captura_1700Z: EB5 old DHCP address rejected; excluded from complete baseline')
    servers=[]
    for address in ['127.0.0.1'] + ([LAN_IP] if LAN_IP else []):
        server=ThreadingHTTPServer((address,PORT),Handler)
        server.daemon_threads=True
        threading.Thread(target=server.serve_forever,daemon=True).start()
        servers.append(server)
    record('controller_started', addresses=[f'http://{s.server_address[0]}:{PORT}' for s in servers], allowed_network=str(LAN_NETWORK), baseline_remaining_s=max(0,300-age))
    print(json.dumps({'status':'timing_ready','url':f'http://127.0.0.1:{PORT}', 'phone_url':f'http://{LAN_IP}:{PORT}' if LAN_IP else None,'baseline_remaining_s':max(0,300-age)}),flush=True)
    deadline=time.monotonic()+21600
    try:
        while time.monotonic()<deadline and not (ROOT/'stop_controller').exists():
            with LOCK:
                if not STATE['baseline_done'] and time.monotonic()>=STATE['baseline_deadline']:
                    STATE['baseline_done']=True
                    record('baseline_finished', expected_start_utc=started, duration_s=300)
            STOP.wait(.1)
    finally:
        STOP.set()
        for server in servers:
            server.shutdown()
            server.server_close()
        record('controller_stopped')

if __name__=='__main__':
    main()
