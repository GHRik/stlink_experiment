// Accelerated frontend simulation. Never calls upload, capture or switching APIs.
let sketchQueuePreview = null;
const queuePreviewSpeed = 60;

function buildSketchQueuePlan() {
  const boards = [...sketchQueues].filter(([card]) => !card.hidden).map(([card, queued]) => {
    const input = card.querySelector('.sketch');
    const path = input.dataset.path;
    const single = input.files[0] || (path ? {name:path.split(/[\\/]/).pop()} : null);
    return {card, files:queued.length ? [...queued] : single ? [single] : []};
  });
  const value = id => Math.max(0, Number(document.querySelector(id).value) || 0);
  const boardSeconds = value('#measurement-warmup') + value('#measurement-repeats')*value('#measurement-seconds');
  return Array.from({length:Math.max(0,...boards.map(board=>board.files.length))}, (_, index) => {
    const active = boards.filter(board=>board.files[index]).map(board=>({card:board.card,file:board.files[index]}));
    return {active, seconds:Math.max(1, active.length*boardSeconds)};
  });
}

function queueTime(seconds) {
  seconds = Math.max(0, Math.ceil(seconds));
  return `${Math.floor(seconds/60)} min ${seconds%60} s`;
}

function paintSketchQueuePreview() {
  const preview = sketchQueuePreview, step = preview.steps[preview.index];
  for (const [card, files] of sketchQueues) {
    if (card.hidden) continue;
    const view = sketchQueueViews.get(card);
    const active = step.active.find(board=>board.card===card);
    card.classList.toggle('queue-dut-skipped', preview.running && !active);
    card.classList.toggle('queue-preview-active', preview.running);
    const label=preview.real?'Queue':'Preview';
    view.note.textContent = !preview.running ? `${label} ${preview.failed?'failed':preview.stopped?'stopped':'completed'}.`
      : active ? `${label} · Current sketch: ${active.file.name}` : `Skipped in run ${preview.index+1} · no sketch.`;
    view.list.children && [...view.list.children].forEach((row, index) => {
      const done = index < preview.index || (index===preview.index && preview.currentStepDone)
        || (!preview.running && !preview.stopped && !preview.failed);
      const current = preview.running && !preview.currentStepDone && index === preview.index;
      row.classList.toggle('is-done', done);
      row.classList.toggle('is-current', current);
      row.setAttribute('aria-current', current?'step':'false');
      row.title = done?'Completed':current?'Current sketch':'Pending';
    });
    let display = card.querySelector('.queue-current-sketch');
    if (!display) { display=document.createElement('p');display.className='queue-current-sketch';card.append(display); }
    display.textContent = preview.running ? active ? `Queue sketch: ${active.file.name}` : 'DUT inactive in this run' : `${label} finished`;
  }
}

function renderSketchQueueTime() {
  const preview=sketchQueuePreview;
  if (!preview) return;
  const current=Math.max(0,preview.steps[preview.index].seconds-preview.elapsed);
  const remaining=current+preview.steps.slice(preview.index+1).reduce((sum,step)=>sum+step.seconds,0);
  document.querySelector('#queue-actual-time').textContent=`Actual run remaining: ${queueTime(current)}`;
  document.querySelector('#queue-total-time').textContent=`Run: ${preview.index+1}/${preview.steps.length} · Remaining time: ${queueTime(remaining)}`;
  document.querySelector('#queue-preview-phase').textContent=preview.running
    ? `${preview.real?'Queue running':`Frontend preview · ${queuePreviewSpeed}× simulated time`} · ${preview.steps[preview.index].active.length} active DUTs`
    : preview.failed?'Queue failed':preview.stopped?'Queue stopped':'Queue completed';
  if(!preview.real && preview.running && typeof showQueueDemoHardware==='function')
    document.querySelector('#queue-preview-phase').textContent+=` · ${showQueueDemoHardware(preview.steps[preview.index],preview.elapsed)}`;
}

function finishSketchQueuePreview(stopped=false) {
  const preview=sketchQueuePreview;
  if (!preview?.running) return;
  if(!stopped && typeof saveDemoQueueStep==='function') saveDemoQueueStep(preview.steps[preview.index],preview.index);
  clearInterval(preview.timer);preview.running=false;preview.stopped=stopped;
  if(typeof showDemoHardware==='function') showDemoHardware(-1,'idle');
  if (!stopped) {preview.index=preview.steps.length-1;preview.elapsed=preview.steps[preview.index].seconds;}
  setRunning(false);
  document.querySelector('#stop').disabled=false;
  paintSketchQueuePreview();renderSketchQueueTime();
  document.querySelector('#status').textContent=stopped?'Queue preview stopped.':'Queue preview completed.';
}

function tickSketchQueuePreview(seconds) {
  const preview=sketchQueuePreview;
  if (!preview?.running) return;
  preview.elapsed+=seconds;
  while (preview.elapsed>=preview.steps[preview.index].seconds) {
    if (preview.index===preview.steps.length-1) {finishSketchQueuePreview();return;}
    if(typeof saveDemoQueueStep==='function') saveDemoQueueStep(preview.steps[preview.index],preview.index);
    preview.elapsed-=preview.steps[preview.index].seconds;
    preview.index++;paintSketchQueuePreview();
  }
  renderSketchQueueTime();
}

function startSketchQueuePreview() {
  if (isRunning || !['hil','one-hub'].includes(currentLayout)) return;
  const steps=buildSketchQueuePlan();
  if (!steps.length) {
    document.querySelector('#status').classList.toggle('error',true);
    document.querySelector('#status').textContent='No sketches selected. Add at least one sketch to an active DUT queue or choose an Arduino sketch.';
    return;
  }
  document.querySelector('#status').classList.toggle('error',false);
  sketchQueuePreview={steps,index:0,elapsed:0,running:true,stopped:false,timer:null};
  document.querySelector('#queue-progress').hidden=false;
  document.querySelector('#run-progress').hidden=true;
  setRunning(true);
  document.querySelector('#stop').disabled=false;
  paintSketchQueuePreview();renderSketchQueueTime();
  document.querySelector('#status').textContent='Sketch queue frontend preview running.';
  let previous=performance.now();
  sketchQueuePreview.timer=setInterval(()=>{
    const now=performance.now();tickSketchQueuePreview((now-previous)/1000*queuePreviewSpeed);previous=now;
  },100);
}

document.querySelector('#stop').addEventListener('click', event=>{
  if (!sketchQueuePreview?.running) return;
  if (sketchQueuePreview.real) {sketchQueuePreview.cancelled=true;return;}
  event.stopImmediatePropagation();finishSketchQueuePreview(true);
},{capture:true});
