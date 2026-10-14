// Display one continuous soil experiment and collect a separate report per plant.
let soilFormTrial=null;
function soilChoices(id,label){
  const wrapper=document.createElement('label');wrapper.textContent=label+' ';
  const select=document.createElement('select');select.id=id;
  for(const [value,text] of [['unknown','No pude distinguirlo'],['yes','Sí'],['no','No']]){
    const option=document.createElement('option');option.value=value;option.textContent=text;select.appendChild(option);
  }
  wrapper.appendChild(select);return wrapper;
}
function prepareSoilReport(c){
  if(soilFormTrial===c.trial_id)return;
  soilFormTrial=c.trial_id;$('sequence-report').replaceChildren();
  $('all-black-free').checked=false;$('ground-placed').disabled=false;
  for(const node of ['EB5','EC5','EE5','EF5']){
    const group=document.createElement('fieldset'),legend=document.createElement('legend');legend.textContent=node;group.appendChild(legend);
    const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.id=`soil-done-${node}`;
    label.appendChild(check);label.appendChild(document.createTextNode(' Realicé los contactos indicados para esta planta.'));group.appendChild(label);
    group.appendChild(soilChoices(`soil-plant-${node}`,'Sonó tocando solo la planta'));
    if(node!=='EB5')group.appendChild(soilChoices(`soil-pair-${node}`,`Sonó al agregar negro ${node}`));
    group.appendChild(soilChoices(`soil-held-${node}`,'El sonido se sostuvo durante el contacto'));
    group.appendChild(soilChoices(`soil-varied-${node}`,'Hubo variaciones de nota'));
    group.appendChild(soilChoices(`soil-released-${node}`,'Volvió al silencio al soltar'));
    const notes=document.createElement('textarea');notes.id=`soil-notes-${node}`;notes.placeholder='Sonidos antes de tocar, contactos omitidos, retrasos o persistencia.';group.appendChild(notes);
    $('sequence-report').appendChild(group);
  }
}
function readSoilReport(){
  const blocks=['EB5','EC5','EE5','EF5'].map(node=>({node,confirmed_contacts:$(`soil-done-${node}`).checked===true,
    plant_only_audible:$(`soil-plant-${node}`).value,
    paired_audible:node==='EB5'?'not_applicable':$(`soil-pair-${node}`).value,
    sustained:$(`soil-held-${node}`).value,varied:$(`soil-varied-${node}`).value,
    silence_after_release:$(`soil-released-${node}`).value,notes:$(`soil-notes-${node}`).value}));
  return {form_revision:3,followed_cues:$('followed').checked,
    completed_repetitions:blocks.filter(b=>b.confirmed_contacts).length,
    count_meaning:'completed plant blocks, one pass each',block_reports:blocks,
    grounded_black_kept_fixed:$('followed').checked,notes:$('notes').value};
}
function renderSoilSequence(s,c){
  const step=s.active_step,action=step?.instruction;
  prepareSoilReport(c);
  $('targets').hidden=false;
  $('plant-target').textContent=step?.plant_node?`PLANTA: rojo ${step.plant_node}`:'PLANTAS: EB5 → EC5 → EE5 → EF5';
  $('black-target').textContent=step?.black_node?`PUNTA NEGRA: ${step.black_node}`:'No sostengas ninguna punta negra';
  $('untouched-target').textContent=step?.ground_state==='all_black_free'?'Todos los negros al aire hasta el aviso de enterrado.':'Negro EB5 fijo en la maceta EB5; no lo sostengas durante los contactos.';
  $('environment').textContent='Toda la corrida de pie y con zapatos, incluido EB5 y EC5.';
  $('footwear').value='shoes';$('footwear').disabled=true;
  $('identity').textContent=c.trial_id+' · una sola corrida, cuatro plantas';
  $('condition').textContent='EB5: solo planta. EC5, EE5 y EF5: planta sola y después su propio negro. Duración máxima: 15 min 20 s.';
  $('footwear-control').hidden=s.mode!=='armed';$('soil-start-check').hidden=s.mode!=='armed';
  $('ground-control').hidden=!(s.mode==='running'&&s.phase==='ground_placement'&&ownsTrial);
  $('legacy-report').hidden=true;$('sequence-report').hidden=false;
  $('followed-label').lastChild.textContent=' El negro EB5 permaneció enterrado y fijo durante todos los contactos; registré cualquier incidente en observaciones.';
  $('start').disabled=!(s.mode==='armed'&&s.baseline_done);
  $('abort').disabled=!(s.mode==='running'&&ownsTrial);
  $('report').hidden=!(s.mode==='awaiting_report'&&ownsTrial);
  $('actions').hidden=s.mode!=='armed';
  if($('action-rows').dataset.signature!==c.trial_id){
    $('action-rows').replaceChildren();
    for(const node of ['EB5','EC5','EE5','EF5']){
      const row=document.createElement('tr');
      for(const text of [node,node==='EB5'?'20 s':'20 s + 20 s',node==='EB5'?'Solo planta EB5; ninguna mano toca negros.':`Planta ${node} sola; después agregar negro ${node} sin soltar la planta.`]){
        const cell=document.createElement('td');cell.textContent=text;row.appendChild(cell);
      }
      $('action-rows').appendChild(row);
    }
    $('action-rows').dataset.signature=c.trial_id;
  }
  let title='LISTO PARA INICIAR',text='Comienza con todos los negros al aire. El temporizador indicará cuándo enterrar EB5 y cuándo tocar cada planta.';
  if(s.mode==='running'){title=action.title;text=action.instruction;}
  if(s.mode==='awaiting_report'){
    title=s.phase==='aborted'?'TEMPORIZADOR INTERRUMPIDO':'CORRIDA TERMINADA';
    text='Suelta todas las plantas y puntas negras. Si EB5 ya está enterrado, déjalo fijo. Guarda la confirmación de cada planta y los incidentes.';
  }
  $('phase').textContent=title;$('instruction').textContent=text;
  $('seconds').textContent=s.mode==='running'?s.remaining_s:'—';
  $('repetition').textContent=s.mode==='running'&&step?.repetition?`Planta ${step.repetition} de 4: ${step.block_node}`:'';
  $('progress').max=step?.duration_s||1;$('progress').value=s.mode==='running'?Math.max(0,(step?.duration_s||1)-s.remaining_s):0;
  if(seq!==s.phase_seq){
    seq=s.phase_seq;const renderedAt=new Date().toISOString();let dispatched=null;
    if(s.mode==='running'&&ownsTrial&&!document.hidden){
      tone(s.phase==='contact'||s.phase==='first_contact'?2:s.phase==='release'?3:1);
      speak(action.spoken);dispatched=new Date().toISOString();
    }
    post('/display_ack',{phase_seq:seq,client_utc:new Date().toISOString(),client_render_utc:renderedAt,cue_dispatch_utc:dispatched,visibility:document.visibilityState}).catch(()=>{});
  }
}
