const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');

test('Numato dropdown 3 sends channel 3; LCUS-2 keeps physical labels 1 and 2',async()=>{
  const model={value:'numato'},calls=[],cards=Array.from({length:3},()=>({querySelector:()=>({})}));
  const buttons=Array.from({length:3},(_,channel)=>{
    const select={value:String(channel),options:[],replaceChildren(){this.options=[];},add(option){this.options.push(option);}};
    const row={querySelector:()=>select};
    return {hidden:false,disabled:false,dataset:{channel:String(channel)},parentElement:row,
      classList:{contains:name=>name==='relay-channel'},closest:()=>row,
      attrs:{'aria-pressed':'false'},setAttribute(name,value){this.attrs[name]=value;},
      getAttribute(name){return this.attrs[name];},removeAttribute(){},querySelector:()=>({})};
  });
  const port={value:'COM19',selectedOptions:[{disabled:false}]},status={classList:{add(){},remove(){}},textContent:''};
  const context=vm.createContext({relaySwitches:buttons,hub1Switches:[],hub2Switches:[],hubPortCount:()=>3,
    desktopReady:true,isRunning:false,refreshingPorts:false,switchingHub:false,meterBusy:false,runButton:{},status,
    document:{querySelector:selector=>selector==='#relay-model'?model:selector==='#relay-port'?port:{},
      querySelectorAll:selector=>selector==='.dut'?cards:[]},
    Option:function(text,value){this.text=text;this.value=value;},updateConnectionFlows(){},currentLayout:'hil',
    window:{pywebview:{api:{set_relay:async(...args)=>{calls.push(args);return {enabled:true,confirmation:'readback'};}}}}});
  vm.runInContext(fs.readFileSync('automation/frontend/relay.js','utf8'),context);
  vm.runInContext(fs.readFileSync('automation/frontend/mappings.js','utf8'),context);
  vm.runInContext('updateChannelMappings()',context);
  assert.deepEqual(buttons[0].parentElement.querySelector().options.map(option=>option.value),['0','1','2','3']);
  buttons[0].parentElement.querySelector().value='3';
  vm.runInContext('updateChannelMappings()',context);
  assert.equal(buttons[0].dataset.channel,'3');
  await vm.runInContext('switchRelay(relaySwitches[0])',context);
  assert.deepEqual(calls[0],['numato','COM19',3,true]);
  assert.match(status.textContent,/Relay 3 ON/);
  model.value='lcus2';buttons[2].hidden=true;
  vm.runInContext('updateChannelMappings()',context);
  assert.deepEqual(buttons[0].parentElement.querySelector().options.map(option=>option.value),['1','2']);
  assert.equal(vm.runInContext("relayChannelNumber(1,'lcus2')",context),2);
});
