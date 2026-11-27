// Queue only selects configurations; existing Run flows own upload, capture and STOP.
async function startSketchQueueCapture() {
  if (isRunning || !['hil','one-hub'].includes(currentLayout)) return;
  const steps=buildSketchQueuePlan(), mode=currentLayout, shared=hilConfiguration();
  const {hub,relay}=shared;
  const boards=new Map([...sketchQueues.keys()].filter(card=>!card.hidden).map((card,index)=>[card,shared.boards[index]]));
  const fail=message=>{status.classList.add('error');status.textContent=message;};
  if(!steps.length) {fail('No sketches selected for active DUTs.');return;}
  if(mode !== 'hil' && !shared.name.trim()) {fail('Enter a test name.');return;}
  if(!hubConfigured(document.querySelector('.upload-hub'))) {fail('Select the DUT hub model and serial number.');return;}
  // A single-sketch selection uses the same native path as ordinary Run.
  steps.forEach(step=>step.active.forEach(board=>{
    if(!board.file.path && !sketchQueues.get(board.card).length)
      board.file={...board.file,path:board.card.querySelector('.sketch').dataset.path};
  }));
  const sketches=steps.flatMap(step=>step.active.map(board=>board.file.path));
  if(sketches.some(path=>!path)) {fail('Select sketches using the desktop file picker.');return;}
  sketchQueuePreview={steps,index:0,elapsed:0,running:true,stopped:false,real:true,timer:null,cancelled:false};
  const queue=sketchQueuePreview, output=`results/queue_${new Date().toISOString().replace(/[-:TZ.]/g,'')}`;
  setRunning(true);stopButton.disabled=false;
  let outcome='completed';
  try {
    await window.pywebview.api.validate_sketches(sketches);
    for(let index=0;index<steps.length;index++) {
      if(queue.cancelled) {outcome='stopped';break;}
      queue.index=index;queue.elapsed=0;queue.currentStepDone=false;
      const config={...shared,name:shared.name.trim() ? `${shared.name.trim()}_step${String(index+1).padStart(3,'0')}` : '',
        out:`${output}/step_${String(index+1).padStart(3,'0')}`,hub,relay,
        boards:steps[index].active.map(board=>({...boards.get(board.card),sketch:board.file.path}))};
      const result=await new Promise(resolve=>{
        const started=mode==='hil'
          ? startStandaloneCapture(false,config,'start_hil',resolve)
          : startOneHubCapture({config,hub:{...hub,port:config.boards[0].ykush_usb_port},
              sketch:config.boards[0].sketch,board:config.boards[0].upload_profile,
              uploadPort:config.boards[0].com,onComplete:resolve});
        document.querySelector('#queue-progress').hidden=false;
        paintSketchQueuePreview();renderSketchQueueTime();
        Promise.resolve(started).catch(error=>resolve({code:1,error}));
      });
      if(result.code===0) {queue.currentStepDone=true;queue.elapsed=steps[index].seconds;paintSketchQueuePreview();}
      if(result.stopped || queue.cancelled) {outcome='stopped';break;}
      if(result.code!==0) throw result.error || new Error(`Run ${index+1} exited with code ${result.code}.`);
    }
  } catch(error) {outcome='failed';fail(`Queue failed: ${error.message||error}`);}
  finally {
    finishRealSketchQueue(outcome);setRunning(false);stopButton.disabled=false;
    if(outcome!=='failed') status.textContent=outcome==='stopped'?'Queue stopped.':'Queue completed.';
  }
}

function updateSketchQueueRemaining(remaining) {
  if(!sketchQueuePreview?.real || !sketchQueuePreview.running) return;
  sketchQueuePreview.elapsed=Math.max(0,sketchQueuePreview.steps[sketchQueuePreview.index].seconds-remaining);
  renderSketchQueueTime();
}

function finishRealSketchQueue(state) {
  if(!sketchQueuePreview?.real || !sketchQueuePreview.running) return;
  sketchQueuePreview.running=false;sketchQueuePreview.stopped=state==='stopped';sketchQueuePreview.failed=state==='failed';
  if(state==='completed') {
    sketchQueuePreview.index=sketchQueuePreview.steps.length-1;
    sketchQueuePreview.elapsed=sketchQueuePreview.steps[sketchQueuePreview.index].seconds;
  }
  paintSketchQueuePreview();renderSketchQueueTime();
}
