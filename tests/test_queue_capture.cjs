const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');

for(const mode of ['hil','one-hub']) for(const outcome of ['success','failure','stop']) {
  test(`${mode} queue loops over existing Run and stops correctly: ${outcome}`,async()=>{
    const cards=[1,2].map(i=>({hidden:false,querySelector:()=>({id:`dut${i}-sketch`,dataset:{},files:[]})}));
    const files=[{name:'a.ino',path:'C:/a.ino'},{name:'b.ino',path:'C:/b.ino'}];
    const values={'#hub-model':'ykush3','#hub-serial':'YK123','#relay-model':'numato','#relay-port':'COM19',
      '#dut1-profile':'nodemcu','#dut1-port':'COM22','#dut2-profile':'nodemcu','#dut2-port':'COM23'};
    const fields={},calls=[];let checked;
    const run=(config,complete)=>{
      calls.push(config);
      complete({code:outcome==='failure'?1:outcome==='stop'?130:0,stopped:outcome==='stop'});
      return Promise.resolve();
    };
    const context=vm.createContext({sketchQueues:new Map([[cards[0],files],[cards[1],[files[0]]]]),
      status:{classList:{add(){}},textContent:''},stopButton:{},hubConfigured:()=>true,
      hilConfiguration:()=>({name:'test',controller:'C:/control.py',hub:{driver:'ykush3',serial:'YK123'},
        relay:{driver:'numato',port:'COM19'},boards:[{upload_profile:'nodemcu',com:'COM22',ykush_usb_port:3,relay:3},
          {upload_profile:'nodemcu',com:'COM23',ykush_usb_port:1,relay:0}]}),
      buildSketchQueuePlan:()=>[{seconds:100,active:cards.slice(0,mode==='hil'?2:1).map(card=>({card,file:files[0]}))},
        {seconds:50,active:[{card:cards[0],file:files[1]}]}],
      hub2Switches:[{dataset:{port:'3'}},{dataset:{port:'1'}}],relaySwitches:[{dataset:{channel:'3'}},{dataset:{channel:'0'}}],
      window:{pywebview:{api:{validate_sketches:async paths=>{checked=paths;}}}},
      document:{querySelector:selector=>fields[selector]||=(selector in values?{value:values[selector]}:{})},
      startStandaloneCapture:(preserve,config,method,complete)=>{assert.equal(method,'start_hil');return run(config,complete);},
      startOneHubCapture:options=>run({...options.config,selectedSketch:options.sketch,physicalPort:options.hub.port},options.onComplete),
      paintSketchQueuePreview(){},renderSketchQueueTime(){}});
    vm.runInContext(`let isRunning=false;let currentLayout='${mode}';let sketchQueuePreview=null;function setRunning(value){isRunning=value;}`,context);
    vm.runInContext(fs.readFileSync('automation/frontend/queue-capture.js','utf8'),context);
    await vm.runInContext('startSketchQueueCapture()',context);
    assert.ok(checked.includes('C:/b.ino'));
    assert.equal(calls.length,outcome==='success'?2:1);
    assert.equal(calls[0].boards[0].relay,3);assert.equal(calls[0].boards[0].ykush_usb_port,3);
    assert.equal(calls[0].controller,'C:/control.py');
    assert.equal(calls[0].name,'test_step001');
    if(outcome==='success') {
      assert.equal(calls[1].boards.length,1);assert.equal(calls[1].boards[0].sketch,'C:/b.ino');
      assert.match(calls[1].out,/\/step_002$/);
      if(mode==='one-hub') assert.equal(calls[1].selectedSketch,'C:/b.ino');
    }
    assert.equal(vm.runInContext('isRunning',context),false);
    assert.equal(vm.runInContext('sketchQueuePreview.failed',context),outcome==='failure');
    assert.equal(vm.runInContext('sketchQueuePreview.stopped',context),outcome==='stop');
  });
}
