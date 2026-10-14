
const $=id=>document.getElementById(id);
let operatorId=sessionStorage.getItem('okua-timer-operator');
if(!operatorId){
  operatorId=window.crypto&&typeof crypto.randomUUID==='function'?crypto.randomUUID():`${Date.now()}-${Math.random().toString(36).slice(2)}`;
  sessionStorage.setItem('okua-timer-operator',operatorId);
}
let seq=-1,lastMode='',context=null,busy=false,ownsTrial=false,currentActions=null;
async function post(route,data={}){
  const r=await fetch(route,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...data,operator_id:operatorId,ui_revision:5})});
  const v=await r.json();if(!r.ok)throw Error(v.error);return v;
}
function speak(text){
  if('speechSynthesis' in window){speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(text);u.lang='es-CO';u.rate=.9;speechSynthesis.speak(u);}
}
function tone(count=1){
  try{
    const Audio=window.AudioContext||window.webkitAudioContext;
    context=context||new Audio();context.resume();
    for(let i=0;i<count;i++){
      const o=context.createOscillator(),g=context.createGain();o.frequency.value=880;o.connect(g);g.connect(context.destination);
      const t=context.currentTime+i*.24;g.gain.setValueAtTime(.12,t);g.gain.exponentialRampToValueAtTime(.001,t+.15);o.start(t);o.stop(t+.17);
    }
  }catch(e){$('problem').textContent='Usa las indicaciones visuales: no se pudo emitir la señal sonora.';}
}
$('sound').onclick=()=>{
  tone(1);
  const sample=currentActions?[currentActions.rest,currentActions.first_contact,currentActions.contact,currentActions.release].filter(Boolean).map(a=>a.spoken).join(' '):'Ambas manos libres, sin tocar plantas ni puntas negras.';
  speak('Prueba de voz. No realices contactos todavia. '+sample);
  post('/display_ack',{phase_seq:seq,client_utc:new Date().toISOString(),visibility:document.visibilityState,client_note:'cue_check_no_physical_contact'}).catch(()=>{});
};
$('start').onclick=async()=>{
  try{tone(1);const s=await post('/start',{footwear:$('footwear').value});ownsTrial=s.operator_id===operatorId;$('problem').textContent='';$('phase').scrollIntoView({behavior:'smooth',block:'start'});}
  catch(e){$('problem').textContent=e.message;}
};
$('abort').onclick=async()=>{
  try{await post('/abort',{reason:'Operator button'});speak('Ensayo anulado. Suelta todo.');}
  catch(e){$('problem').textContent=e.message;}
};
$('save').onclick=async()=>{
  try{
    await post('/report',{form_revision:2,followed_cues:$('followed').checked,completed_repetitions:Number($('completed').value),audible_repetitions:$('heard').value,first_contact_audible_repetitions:$('heard-first').value,paired_contact_audible_repetitions:currentActions?.first_contact?$('heard-both').value:'not_applicable',second_contact_audible_change:currentActions?.first_contact?$('change').value:'not_applicable',contact_sound:$('sustain').value,paired_contact_sound:currentActions?.first_contact?$('sustain').value:'not_applicable',after_release_silence:$('silence').value,notes:$('notes').value});
    $('problem').textContent='Confirmación guardada. Espera el siguiente ensayo.';$('notes').value='';$('followed').checked=false;
    for(const id of ['heard','heard-first','heard-both','change','sustain','silence'])$(id).value='unknown';
    $('completed').value='3';
  }catch(e){$('problem').textContent=e.message;}
};
document.addEventListener('visibilitychange',()=>{
  if(document.hidden&&lastMode==='running'&&ownsTrial)post('/abort',{reason:'Operator timer tab hidden during trial'}).catch(()=>{});
});
async function poll(){
  if(busy)return;busy=true;
  try{
    const r=await fetch('/status',{cache:'no-store'});if(!r.ok)throw Error('Sin conexión con el temporizador');
    const s=await r.json();lastMode=s.mode;ownsTrial=s.operator_id===operatorId;
    const c=s.trial||s.armed;
    const actions=s.phase_instructions;currentActions=actions;
    const paired=c&&['own_pair','cross_pair'].includes(c.condition);
    $('targets').hidden=!c;
    $('plant-target').textContent=c?(c.condition==='black_only'?'PLANTA: NINGUNA':`PLANTA: etiqueta ROJA ${c.plant_node}`):'';
    $('black-target').textContent=c?(c.condition==='plant_only'||c.condition==='sham'?'PUNTA NEGRA: NINGUNA':`PUNTA NEGRA: etiqueta ${c.black_node}`):'';
    $('untouched-target').textContent=c?.condition==='cross_pair'?`La planta de etiqueta roja ${c.black_node} queda SIN TOCAR.`:'';
    const env=c?.operator_environment;
    const posture=env?.posture==='seated_on_floor_through_trousers'?'Sentado en el piso, pantalón en contacto con él':env?.posture==='standing'?'De pie':'Postura sin confirmar';
    $('environment').textContent=env?`${posture}. Piso: pasto sintético ligeramente húmedo. Mantén la posición y el calzado; registra cualquier cambio.`:'';
    $('footwear-control').hidden=s.mode!=='armed';
    $('identity').textContent=c?`${c.trial_id} · ${paired?`planta ${c.plant_node} + negro ${c.black_node}`:c.condition==='plant_only'?`SOLO planta ${c.plant_node} · ninguna punta negra`:c.condition==='black_only'?`SOLO negro ${c.black_node} · ninguna planta`:`Acercar sin tocar la planta ${c.plant_node}`}`:'Esperando ensayo coordinado';
    $('report-both').hidden=!paired;$('report-change').hidden=!paired;
    $('first-label').textContent=c?paired?`Sonó al tocar solo ${c.contact_order==='black_first'?'el negro':'la planta'}`:c.condition==='plant_only'?'Sonó al tocar solo la planta':c.condition==='black_only'?'Sonó al tocar solo el negro':'Sonó al acercar la mano sin tocar':'Sonó durante el contacto';
    $('sustain-label').textContent=paired?'Mientras mantuve planta + negro':'Mientras mantuve el contacto indicado';
    $('condition').textContent=c?paired?`Orden: ${c.contact_order==='black_first'?'NEGRO PRIMERO → PLANTA DESPUÉS':'PLANTA PRIMERO → NEGRO DESPUÉS'} · ${s.duration_s} s en total`:`Condición: ${c.condition==='plant_only'?'SOLO PLANTA':c.condition==='black_only'?'SOLO NEGRO':'ACERCAR SIN TOCAR'}`:'';
    $('actions').hidden=!actions||s.mode==='awaiting_report';
    if(actions){
      const signature=JSON.stringify(c);
      if($('action-rows').dataset.signature!==signature){
        $('action-rows').replaceChildren();
        const phases=s.schedule.filter(p=>p.repetition===1);
        for(const p of phases){
          const row=document.createElement('tr');
          for(const text of [actions[p.phase].title,`${p.duration_s} s`,actions[p.phase].instruction]){const cell=document.createElement('td');cell.textContent=text;row.appendChild(cell);}
          $('action-rows').appendChild(row);
        }
        $('action-rows').dataset.signature=signature;
      }
    }
    $('start').disabled=!(s.baseline_done&&s.mode==='armed');
    $('abort').disabled=s.mode!=='running'||!ownsTrial;
    $('report').hidden=s.mode!=='awaiting_report'||!ownsTrial;
    let phase='ESPERA',remaining=s.remaining_s,text=s.instruction,maximum=30;
    if(!s.baseline_done){phase='REPOSO INICIAL';remaining=s.baseline_remaining_s;maximum=300;text='Ambas manos libres. No toques ninguna planta ni ninguna punta negra.';}
    else if(s.mode==='running'){
      const action=actions[s.phase];phase=action.title;text=action.instruction;
      maximum=s.schedule.find(p=>p.phase===s.phase).duration_s;
    }else if(s.mode==='awaiting_report'){
      phase=s.phase==='aborted'?'TEMPORIZADOR INTERRUMPIDO':'TERMINADO';
      text=s.phase==='aborted'?'Los datos anteriores siguen guardados. Deja ambas manos libres, sin tocar plantas ni puntas negras. Guarda la confirmación e indica en observaciones qué contactos completaste y cuándo ocurrió la interrupción.':'Ambas manos libres, sin tocar plantas ni puntas negras. Ahora puedes escribir y guardar la confirmación.';
    }else if(s.mode==='armed'){phase='LISTO PARA INICIAR';text=paired?`Primero: ${actions.first_contact.instruction} Después: ${actions.contact.instruction}`:s.instruction;}
    $('phase').textContent=phase;$('seconds').textContent=s.mode==='running'||!s.baseline_done?remaining:'—';$('instruction').textContent=text;
    $('repetition').textContent=s.mode==='running'&&s.repetition?`Repetición ${s.repetition} de 3`:'';
    $('progress').max=maximum;$('progress').value=maximum-remaining;
    if(seq!==s.phase_seq){
      seq=s.phase_seq;
      await post('/display_ack',{phase_seq:seq,client_utc:new Date().toISOString(),visibility:document.visibilityState});
      if(s.mode==='running'&&ownsTrial&&!document.hidden){
        tone(s.phase==='contact'||s.phase==='first_contact'?2:s.phase==='release'?3:1);
        speak(actions[s.phase].spoken);
      }
    }
  }catch(e){
    $('problem').textContent='Se perdió la conexión. Suelta todo; el ensayo debe revisarse.';
    if(lastMode==='running'&&ownsTrial)post('/abort',{reason:'Operator timer polling failed'}).catch(()=>{});
  }finally{busy=false;}
}
setInterval(poll,250);poll();
