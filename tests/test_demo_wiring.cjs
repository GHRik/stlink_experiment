const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');

function setup() {
  const button=()=>({on:false,setAttribute(name,value){if(name==='aria-pressed')this.on=value==='true';},
    getAttribute(){return String(this.on);},querySelector(){return {};}});
  const hub1=Array.from({length:3},button),hub2=Array.from({length:3},button),relays=Array.from({length:3},button);
  const cards=Array.from({length:3},()=>({classList:{toggle(){}}})),meter=button(),upstream={checked:true};
  const context=vm.createContext({desktopReady:false,hub1Switches:hub1,hub2Switches:hub2,relaySwitches:relays,
    meterOutput:meter,isOn:button=>button.on,
    document:{querySelectorAll:()=>cards,querySelector:()=>upstream},
    displayMeterPower:enabled=>{meter.on=enabled;},updateConnectionFlows(){}});
  vm.runInContext(fs.readFileSync('automation/frontend/demo.js','utf8'),context);
  vm.runInContext(fs.readFileSync('automation/frontend/modes.js','utf8'),context);
  return {context,hub1,hub2,relays,cards,meter,upstream};
}

test('HIL demo switches only the selected USB or relay branch and clears all branches on stop',()=>{
  const {context,hub1,hub2,relays,meter,upstream}=setup();
  vm.runInContext("currentLayout='hil';showDemoHardware(1,'upload')",context);
  assert.ok(hub1.every(button=>button.on));
  assert.deepEqual(hub2.map(button=>button.on),[false,true,false]);
  assert.ok(relays.every(button=>!button.on));assert.equal(meter.on,false);
  vm.runInContext("showDemoHardware(1,'measure')",context);
  assert.deepEqual(relays.map(button=>button.on),[false,true,false]);
  assert.ok(hub2.every(button=>!button.on));assert.equal(meter.on,true);
  upstream.checked=false;
  assert.equal(vm.runInContext('modeConnectionActive(8,()=>false)',context),true);
  assert.equal(vm.runInContext('modeConnectionActive(9,()=>true)',context),false);
  vm.runInContext("showDemoHardware(-1,'idle')",context);
  assert.ok([...hub1,...hub2,...relays].every(button=>!button.on));assert.equal(meter.on,false);
});

test('One hub visually disconnects STLINK during upload; standalone and one relay use their own power routes',()=>{
  const {context,hub2,relays,meter}=setup();
  vm.runInContext("currentLayout='one-hub';showDemoHardware(0,'upload')",context);
  assert.equal(vm.runInContext('modeConnectionActive(1,()=>true)',context),false);
  assert.equal(vm.runInContext('modeConnectionActive(7,()=>false)',context),true);
  assert.equal(meter.on,false);
  vm.runInContext("showDemoHardware(0,'measure')",context);
  assert.equal(vm.runInContext('modeConnectionActive(1,()=>false)',context),true);
  assert.equal(vm.runInContext('modeConnectionActive(5,()=>false)',context),true);
  assert.ok(hub2.every(button=>!button.on));
  vm.runInContext("currentLayout='standalone';showDemoHardware(0,'measure')",context);
  assert.equal(meter.on,true);assert.ok(relays.every(button=>!button.on));
  vm.runInContext("currentLayout='one-relay';showDemoHardware(2,'measure')",context);
  assert.deepEqual(relays.map(button=>button.on),[false,false,true]);
});

test('Queue demo follows actual active DUT order rather than consecutive DUT numbers',()=>{
  const {context,cards,hub2,relays}=setup();
  context.step={seconds:200,active:[{card:cards[2]},{card:cards[0]}]};
  vm.runInContext("currentLayout='hil';showQueueDemoHardware(step,0)",context);
  assert.deepEqual(hub2.map(button=>button.on),[false,false,true]);
  vm.runInContext('showQueueDemoHardware(step,30)',context);
  assert.deepEqual(relays.map(button=>button.on),[false,false,true]);
  vm.runInContext('showQueueDemoHardware(step,100)',context);
  assert.deepEqual(hub2.map(button=>button.on),[true,false,false]);
  vm.runInContext('showQueueDemoHardware(step,130)',context);
  assert.deepEqual(relays.map(button=>button.on),[true,false,false]);
});

test('Demo wiring helpers cannot change real desktop hardware/UI state',()=>{
  const {context,hub1,hub2,relays,meter}=setup();context.desktopReady=true;
  vm.runInContext("currentLayout='hil';showDemoHardware(1,'measure')",context);
  assert.ok([...hub1,...hub2,...relays].every(button=>!button.on));assert.equal(meter.on,false);
});
