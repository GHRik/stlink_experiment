const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');

test('RUN locks configuration but keeps saved results, previews and comparison controls usable',()=>{
  const control=(parent=null)=>({disabled:false,inert:false,attributes:{},
    closest:selectors=>parent&&selectors.split(',').map(s=>s.trim()).includes(parent)?{}:null,
    getAttribute(name){return this.attributes[name]??null;},
    setAttribute(name,value){this.attributes[name]=value;},
    removeAttribute(name){delete this.attributes[name];},focus(){}});
  const run=control(),stop=control(),config=control(),search=control('.results-section'),
    compare=control('.results-section'),summary=control('.results-section'),
    checkbox=control('.results-section'),preview=control('.results-section'),closePreview=control('#demo-report-dialog');
  const controls=[run,stop,config,search,compare,summary,checkbox,preview,closePreview];
  const context=vm.createContext({Event:class{},stopButton:stop,runButton:run,
    document:{dispatchEvent(){},querySelectorAll:selector=>selector==='.field-help[open]'?[]:controls}});
  vm.runInContext('let isRunning=false; let lockedControls=[];',context);
  const html=fs.readFileSync('automation/frontend/index.html','utf8');
  vm.runInContext(html.slice(html.indexOf('  function setRunning('),html.indexOf('  // Animated dots')),context);
  vm.runInContext('setRunning(true)',context);
  assert.equal(config.disabled,true);assert.equal(config.inert,true);
  for(const item of [search,compare,summary,checkbox,preview,closePreview,stop]) {
    assert.equal(item.disabled,false);assert.equal(item.inert,false);
  }
  vm.runInContext('setRunning(false)',context);
  assert.equal(config.disabled,false);assert.equal(config.inert,false);
});

test('Compare remains available during capture and prevents duplicate generation',async()=>{
  const listeners={},fields={};
  for(const id of ['#compare-results','#comparison-status']) fields[id]={classList:{add(){},remove(){}},setAttribute(){},
    addEventListener:(name,handler)=>{listeners[name]=handler;}};
  let finish,calls=0;
  const context=vm.createContext({isRunning:true,
    document:{querySelector:selector=>fields[selector]},
    window:{pywebview:{api:{compare_results:()=>{calls++;return new Promise(resolve=>{finish=resolve;});}}}}});
  vm.runInContext(fs.readFileSync('automation/frontend/compare.js','utf8'),context);
  vm.runInContext("comparisonSelection.add('DUT1');updateComparisonSelection()",context);
  assert.equal(fields['#compare-results'].disabled,true);
  vm.runInContext("comparisonSelection.add('DUT2');updateComparisonSelection()",context);
  assert.equal(fields['#compare-results'].disabled,false);
  const generation=listeners.click({currentTarget:fields['#compare-results']});
  assert.equal(fields['#compare-results'].disabled,true);
  await listeners.click({currentTarget:fields['#compare-results']});
  assert.equal(calls,1);
  finish();await generation;
  assert.equal(fields['#compare-results'].disabled,false);
});
