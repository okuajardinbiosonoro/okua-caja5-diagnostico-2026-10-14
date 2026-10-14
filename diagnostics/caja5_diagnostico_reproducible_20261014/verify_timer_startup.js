// Exercise the actual page script with transitional state and unavailable speech.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(path.join(__dirname,'temporizador.html'),'utf8');
const script=html.split('<script>')[1].split('</script>')[0];
const nodes={};
const element=()=>({hidden:false,disabled:false,value:'unknown',textContent:'',dataset:{},lastChild:{textContent:''},
  replaceChildren(){},appendChild(){},scrollIntoView(){}});
const actions={preparation:{title:'PREPARATE SIN TOCAR',instruction:'Ambas manos libres.',spoken:'Todavía no toques nada.'},
  rest:{title:'REPOSO',instruction:'Ambas manos libres.',spoken:'No toques nada.'}};
async function exercise(phase,breakVoice=false,blockAck=false){
  const calls=[];
  const state={mode:'running',phase,phase_seq:1,baseline_done:true,remaining_s:10,operator_id:'test-operator',
    trial:{trial_id:'isolated-page-test',condition:'cross_pair',plant_node:'EB5',black_node:'EC5',contact_order:'black_first'},
    phase_instructions:actions,schedule:[{phase:'preparation',duration_s:10,repetition:0}],duration_s:250,repetition:0};
  const sandbox={document:{getElementById:id=>nodes[id]??(nodes[id]=element()),createElement:element,
      addEventListener(){},visibilityState:'visible',hidden:false},
    sessionStorage:{getItem:()=> 'test-operator',setItem(){}},window:{},
    setInterval(){},Date,Math,SpeechSynthesisUtterance:function(text){this.text=text;},
    fetch:async(route,options)=>{calls.push(route);if(blockAck&&route==='/display_ack')return new Promise(()=>{});return {ok:true,json:async()=>state};}};
  sandbox.window.speechSynthesis={};sandbox.speechSynthesis={cancel(){},speak(){calls.push('speech_cue');}};
  if(breakVoice){sandbox.window.speechSynthesis={};sandbox.speechSynthesis={cancel(){throw Error('Speech unavailable');}};}
  vm.createContext(sandbox);vm.runInContext(script,sandbox);
  await new Promise(resolve=>setImmediate(resolve));
  assert(!calls.includes('/abort'),`Unexpected abort for phase ${phase}`);
  assert.equal(nodes.phase.textContent,phase===null?'PREPARANDO':'PREPARATE SIN TOCAR');
  if(blockAck){assert(calls.includes('speech_cue'));assert(calls.indexOf('speech_cue')<calls.indexOf('/display_ack'));}
  return {phase,voice_unavailable:breakVoice,ack_blocked:blockAck,aborted:false};
}
(async()=>{const checks=[await exercise(null),await exercise('preparation'),await exercise('preparation',true),await exercise('preparation',false,true)];
  console.log(JSON.stringify({page_checks:checks,real_browser_or_trial:false}));})().catch(error=>{console.error(error);process.exitCode=1;});
