"""Read-only simultaneous sensor, CKv2 and virtual-MIDI trace. Never binds CKv2 UDP ports."""
import argparse, json, selectors, socket, threading, time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from caja5_ota_probe import get_node, get_secrets

NODES = {21: ('EB5', 5016, '192.168.88.252'), 22: ('EC5', 5017, '192.168.88.254'),
         24: ('EE5', 5019, '192.168.88.249'), 25: ('EF5', 5020, '192.168.88.250')}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--seconds',type=int,default=600); p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    lock=threading.Lock(); done=threading.Event(); counts=Counter(); start=time.monotonic()
    with (a.out/'signals.jsonl').open('a',encoding='utf-8',buffering=1) as f:
        def record(kind, **values):
            row={'at_utc':datetime.now(timezone.utc).isoformat(),'elapsed_s':round(time.monotonic()-start,3),'kind':kind,**values}
            with lock: f.write(json.dumps(row,ensure_ascii=False)+'\n'); counts[kind]+=1
        selector=selectors.DefaultSelector(); sockets=[]; midi=[]
        try:
            for nid,(label,port,ip) in NODES.items():
                s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.bind(('192.168.88.251',port)); s.setblocking(False)
                selector.register(s,selectors.EVENT_READ,(nid,label,ip)); sockets.append(s)
            import mido
            names=mido.get_input_names(); matches=[n for n in names if n=='loopMIDI Port 2' or n.startswith('loopMIDI Port 2 ')]
            if len(matches)!=1: raise RuntimeError('Ambiguous MIDI input: '+repr(matches))
            def midi_event(message):
                if hasattr(message,'channel') and 5<=message.channel<=9:
                    record('midi',channel=message.channel+1,message=message.dict())
            midi.append(mido.open_input(matches[0],callback=midi_event))
            _,token=get_secrets()
            def runtime():
                while not done.is_set():
                    for nid in (21,22,23,24,25):
                        if done.is_set(): break
                        try: record('ckv2',node_id=nid,runtime=get_node(nid,token)['runtime'])
                        except Exception as e: record('api_error',node_id=nid,error=type(e).__name__)
                    done.wait(1)
            worker=threading.Thread(target=runtime,daemon=True); worker.start()
            record('started',midi_input=matches[0],sensor_ports=[v[1] for v in NODES.values()])
            print(json.dumps({'status':'capturing','directory':str(a.out),'midi_input':matches[0]}),flush=True)
            while time.monotonic()-start<a.seconds and not (a.out/'stop').exists():
                for key,_ in selector.select(timeout=.5):
                    raw,source=key.fileobj.recvfrom(4096); nid,label,ip=key.data
                    if source[0]!=ip: continue
                    line=raw.decode('ascii',errors='replace')
                    if line.startswith('PLANTDIAG '):
                        values=dict(part.split('=',1) for part in line.split()[1:] if '=' in part)
                        record('sensor',node_id=nid,label=label,values=values)
            done.set(); worker.join(timeout=6)
        finally:
            done.set()
            for port in midi: port.close()
            for s in sockets: s.close()
            selector.close()
        print(json.dumps({'status':'finished','counts':dict(counts)}),flush=True)

if __name__=='__main__': main()
