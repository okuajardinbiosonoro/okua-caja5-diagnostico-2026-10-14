// Render every planned interval and verify targets and four independent reports.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const root=__dirname,plan=JSON.parse(fs.readFileSync(path.join(root,'soil_sequence_protocol.json'),'utf8'));
const html=fs.readFileSync(path.join(root,'temporizador.html'),'utf8');
const nodes={},calls=[];
function element(){
  const el={hidden:false,disabled:false,checked:false,value:'unknown',textContent:'',dataset:{},children:[],
    replaceChildren(){this.children=[];},appendChild(child){this.children.push(child);},scrollIntoView(){}};
  Object.defineProperty(el,'id',{set(value){nodes[value]=this;},get(){return Object.entries(nodes).find(([id,n])=>n===this)?.[0];}});
  Object.defineProperty(el,'lastChild',{get(){return this.children.at(-1)||this.tail;}});
  el.tail={textContent:''};return el;
}
let state={mode:'armed',baseline_done:true,armed:plan,trial:null,operator_id:'fixture-soil-owner',
  active_step:plan.sequence_steps[0],phase:null,phase_seq:0,remaining_s:0};
const sandbox={document:{getElementById:id=>nodes[id]||(nodes[id]=element()),createElement:element,
  createTextNode:text=>({textContent:text}),addEventListener(){},visibilityState:'visible',hidden:false},
  sessionStorage:{getItem:()=> 'fixture-soil-owner',setItem(){}},window:{speechSynthesis:{}},
  speechSynthesis:{cancel(){},speak(){}},SpeechSynthesisUtterance:function(text){this.text=text;},
  setInterval(){},Date,Math,fetch:async(route,options)=>{calls.push(route);return {ok:true,json:async()=>state};},testConfig:plan};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(root,'soil-sequence.js'),'utf8'),sandbox);
vm.runInContext(html.split('<script>')[1].split('</script>')[0],sandbox);
(async()=>{
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(nodes.footwear.value,'shoes');assert(nodes.footwear.disabled);
  for(const step of plan.sequence_steps){
    sandbox.testState={...state,mode:'running',trial:plan,armed:null,active_step:step,
      phase:step.phase,phase_seq:step.step_index+1,remaining_s:step.duration_s};
    vm.runInContext('renderSoilSequence(testState,testConfig)',sandbox);
    assert.equal(nodes.phase.textContent,step.instruction.title);
    assert.equal(nodes.instruction.textContent,step.instruction.instruction);
    assert.equal(nodes['ground-control'].hidden,step.phase!=='ground_placement');
    if(step.plant_node)assert(nodes['plant-target'].textContent.includes(step.plant_node));
    if(step.black_node)assert(nodes['black-target'].textContent.includes(step.black_node));
  }
  sandbox.document.getElementById('followed').checked=true;
  for(const node of ['EB5','EC5','EE5','EF5']){
    nodes[`soil-done-${node}`].checked=true;
    nodes[`soil-plant-${node}`].value='yes';
    if(node!=='EB5')nodes[`soil-pair-${node}`].value='yes';
  }
  const report=vm.runInContext('readSoilReport()',sandbox);
  assert.equal(report.completed_repetitions,4);
  assert.equal(report.block_reports.length,4);
  assert.equal(report.block_reports[0].paired_audible,'not_applicable');
  assert(!calls.includes('/abort'));
  console.log(JSON.stringify({rendered_intervals:plan.sequence_steps.length,targets_correct:true,
    report_blocks:4,EB5_no_hand_contact_with_black:true,footwear:'shoes',unintended_abort:false,real_browser_or_trial:false}));
})().catch(e=>{console.error(e);process.exitCode=1;});
