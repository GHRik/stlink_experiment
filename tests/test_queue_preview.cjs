const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');

test('Queue preview skips missing sketches, updates both clocks, highlights progress and supports STOP',()=>{
  const element=()=>({hidden:false,textContent:'',classes:new Set(),
    classList:{toggle(name,on){on?this.owner.classes.add(name):this.owner.classes.delete(name);}},
    setAttribute(){},append(item){this.display=item;}});
  const ready=()=>{const item=element();item.classList.owner=item;return item;};
  const cards=Array.from({length:3},()=>{
    const card=ready();card.input={dataset:{},files:[]};
    card.querySelector=selector=>selector==='.sketch'?card.input:card.display;
    return card;
  });
  const queues=new Map(cards.map((card,i)=>[card,Array.from({length:[3,1,0][i]},(_,j)=>({name:`dut${i+1}_${j+1}.ino`}))]));
  const views=new Map(cards.map(card=>[card,{list:{children:queues.get(card).map(ready)},note:ready()}]));
  const fields=Object.fromEntries(['#measurement-warmup','#measurement-repeats','#measurement-seconds','#queue-progress',
    '#run-progress','#queue-actual-time','#queue-total-time','#queue-preview-phase','#status','#stop'].map(id=>[id,ready()]));
  fields['#measurement-warmup'].value=10;fields['#measurement-repeats'].value=2;fields['#measurement-seconds'].value=5;
  let stop;
  fields['#stop'].addEventListener=(name,handler)=>{stop=handler;};
  const context=vm.createContext({sketchQueues:queues,sketchQueueViews:views,
    document:{querySelector:id=>fields[id],createElement:ready},performance:{now:()=>0},setInterval:()=>1,clearInterval(){}});
  vm.runInContext("let isRunning=false;let currentLayout='hil';function setRunning(value){isRunning=value;}",context);
  vm.runInContext(fs.readFileSync('automation/frontend/queue-preview.js','utf8'),context);
  fields['#stop'].disabled=true;
  vm.runInContext('startSketchQueuePreview()',context);
  assert.equal(fields['#stop'].disabled,false);
  assert.match(fields['#queue-actual-time'].textContent,/0 min 40 s/);
  assert.match(fields['#queue-total-time'].textContent,/1\/3.*1 min 20 s/);
  assert.equal(cards[2].classes.has('queue-dut-skipped'),true);
  assert.equal(views.get(cards[0]).list.children[0].classes.has('is-current'),true);
  vm.runInContext('tickSketchQueuePreview(40)',context);
  assert.match(fields['#queue-total-time'].textContent,/2\/3.*0 min 40 s/);
  assert.equal(cards[1].classes.has('queue-dut-skipped'),true);
  assert.equal(views.get(cards[0]).list.children[0].classes.has('is-done'),true);
  assert.equal(views.get(cards[0]).list.children[1].classes.has('is-current'),true);
  vm.runInContext('tickSketchQueuePreview(40)',context);
  assert.equal(vm.runInContext('isRunning',context),false);
  assert.match(fields['#queue-actual-time'].textContent,/0 min 0 s/);
  assert.ok(views.get(cards[0]).list.children.every(row=>row.classes.has('is-done')));
  assert.equal(queues.get(cards[0]).length,3);
  vm.runInContext('startSketchQueuePreview()',context);
  let intercepted=false;stop({stopImmediatePropagation(){intercepted=true;}});
  assert.equal(intercepted,true);assert.equal(vm.runInContext('isRunning',context),false);
  assert.match(fields['#queue-preview-phase'].textContent,/stopped/);
  // A single selected sketch fills step one when that DUT has no queue.
  cards[2].input.dataset.path='C:\\firmware\\single.ino';
  assert.equal(vm.runInContext('buildSketchQueuePlan()[0].active[2].file.name',context),'single.ino');
  assert.equal(vm.runInContext('buildSketchQueuePlan()[1].active.length',context),1);
  for (const files of queues.values()) files.length=0;
  delete cards[2].input.dataset.path;
  vm.runInContext('startSketchQueuePreview()',context);
  assert.equal(vm.runInContext('isRunning',context),false);
  assert.equal(fields['#status'].classes.has('error'),true);
  assert.match(fields['#status'].textContent,/No sketches selected/);
  // A hidden DUT's queue must not satisfy validation for active DUTs.
  cards[2].hidden=true;queues.get(cards[2]).push({name:'hidden.ino'});
  vm.runInContext('startSketchQueuePreview()',context);
  assert.equal(vm.runInContext('isRunning',context),false);
  queues.get(cards[0]).push({name:'valid.ino'});
  vm.runInContext('startSketchQueuePreview()',context);
  assert.equal(vm.runInContext('isRunning',context),true);
  assert.equal(fields['#status'].classes.has('error'),false);
});
