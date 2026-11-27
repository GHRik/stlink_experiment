// Synthetic frontend-only runs. No hardware API or result files are accessed.
let demoMode = false;
let demoRunActive = false;
let demoRunCancelled = false;
let demoWiringPhase = null;

function showDemoHardware(board, phase) {
  if (desktopReady) return;
  demoWiringPhase=phase==='idle'?null:{board,phase};
  const active=phase!=='idle', uploading=phase==='upload';
  const hasHub=['hil','one-hub'].includes(currentLayout), hasRelay=['hil','one-relay'].includes(currentLayout);
  const measuring=['warmup','measure'].includes(phase);
  const set=(button,on)=>{
    button.setAttribute('aria-pressed',String(on));
    button.querySelector('.port-state').textContent=on?'ON':'OFF';
  };
  hub1Switches.forEach((button,index)=>set(button,active && (index===0 || index===1&&hasRelay || index===2&&hasHub)));
  hub2Switches.forEach((button,index)=>set(button,active && hasHub && uploading && index===board));
  relaySwitches.forEach((button,index)=>set(button,active && hasRelay && !uploading && phase!=='prepare' && index===board));
  document.querySelectorAll('.dut').forEach((card,index)=>card.classList.toggle('demo-dut-active',active&&index===board));
  displayMeterPower(active&&measuring);
  updateConnectionFlows();
}

function showQueueDemoHardware(step, elapsed) {
  const index=Math.min(step.active.length-1,Math.floor(elapsed/(step.seconds/step.active.length)));
  const part=step.seconds/step.active.length, uploading=(elapsed-index*part)/part<.15;
  const cards=[...document.querySelectorAll('.dut')], board=cards.indexOf(step.active[index].card);
  const phase=uploading?'upload':'measure';
  if(demoWiringPhase?.board!==board || demoWiringPhase?.phase!==phase) showDemoHardware(board,phase);
  return `DUT ${board+1} · ${uploading?'Uploading':'Measuring'}`;
}

function demoTrace(seconds, repeat, board) {
  return Array.from({length: 601}, (_, index) => {
    const time = seconds * index / 600;
    const mean = (Math.floor(time / 5) % 2 ? .3 : 20) + repeat * .06 + board * .2;
    const peak = index === 0 ? 150 : mean + .2;
    return [time, mean, Math.max(0, mean - .2), peak];
  });
}

function demoReport(title, traces, seconds, voltage, statistics) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  svg.setAttribute('viewBox', '0 0 1000 440');
  const node = (tag, attributes, text) => {
    const element = document.createElementNS(svg.namespaceURI, tag);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
    if (text !== undefined) element.textContent = text;
    svg.append(element);
    return element;
  };
  node('rect', {width:1000, height:440, fill:'#fff'});
  const label = (x,y,text,extra={}) => node('text', {x,y,fill:'#172538','font-family':'monospace','font-size':13,...extra}, text);
  label(500,25,`DEMO — SYNTHETIC DATA · ${title}`, {'text-anchor':'middle','font-size':17});
  const colors = ['#087e80','#c85142','#7658a6','#2c74ba','#bd7a00'];
  const means = traces.map(points => points.reduce((sum, point) => sum + point[1], 0) / points.length);
  if (!statistics) {
    const max = Math.max(...traces.map(points => Math.max(...points.map(point => point[3])))) * 1.1;
    for (let step=0; step<=4; step++) {
      const y=350-step*70;
      node('line', {x1:70,y1:y,x2:970,y2:y,stroke:'#d8e1eb'});
      label(60,y+4,(max*step/4).toFixed(1),{'text-anchor':'end'});
      label(70+step*225,375,(seconds*step/4).toFixed(1),{'text-anchor':'middle'});
    }
    traces.forEach((points, index) => {
      node('polyline', {points:points.map(point => `${70+point[0]/seconds*900},${350-point[1]/max*280}`).join(' '),
        fill:'none',stroke:colors[index%colors.length],'stroke-width':1.5});
      label(80+(index%10)*88,405+Math.floor(index/10)*15,`R${index+1}`,{fill:colors[index%colors.length]});
    });
    label(70,55,'Current [mA]'); label(900,395,'Time [s]');
  } else {
    [means, means.map(mean => mean/1000*voltage*seconds)].forEach((values, panel) => {
      const left=panel*490+65, max=Math.max(...values)*1.2 || 1;
      const y=value=>350-value/max*270;
      const average=values.reduce((a,b)=>a+b,0)/values.length;
      const sd=values.length>1 ? Math.sqrt(values.reduce((sum,value)=>sum+(value-average)**2,0)/(values.length-1)) : 0;
      label(left,60,panel ? 'Energy [J]' : 'Mean current [mA]');
      for(let step=0;step<=4;step++) {
        node('line',{x1:left,y1:y(max*step/4),x2:left+400,y2:y(max*step/4),stroke:'#d8e1eb'});
        label(left-8,y(max*step/4)+4,(max*step/4).toFixed(3),{'text-anchor':'end'});
      }
      values.forEach((value,index)=>node('circle',{cx:left+50+(index+1)/(values.length+1)*300,cy:y(value),r:4,fill:colors[index%colors.length]}));
      node('line',{x1:left+200,x2:left+200,y1:y(average-sd),y2:y(average+sd),stroke:'#172538','stroke-width':2});
      node('circle',{cx:left+200,cy:y(average),r:5,fill:'#172538'});
      label(left,390,`Mean ${average.toFixed(3)} · SD ${sd.toFixed(3)}`);
      label(left,414,`Min ${Math.min(...values).toFixed(3)} · Max ${Math.max(...values).toFixed(3)}`);
    });
  }
  return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(new XMLSerializer().serializeToString(svg));
}

async function showDemoReports(name, traces, config) {
  if(typeof window.pywebview?.api?.save_demo_result==='function') {
    const plots=[demoReport(name,traces,Number(config.seconds),Number(config.voltage),false),
                 demoReport(name,traces,Number(config.seconds),Number(config.voltage),true)];
    await window.pywebview.api.save_demo_result(name,traces,config,plots);
    await refreshResults();
    return;
  }
  const gallery=document.querySelector('#results-gallery');
  const day=new Date().toLocaleDateString('en-GB').replaceAll('/','.');
  let group=[...gallery.querySelectorAll('.result-day')].find(item=>item.dataset.day===day);
  if(!group) {
    group=document.createElement('section'); group.className='result-day'; group.dataset.day=day;
    const heading=document.createElement('h3'); heading.textContent=day; group.append(heading); gallery.prepend(group);
  }
  const card=document.createElement('details'); card.className='result-session'; card.dataset.name=`${name} ${day}`.toLowerCase();
  const heading=document.createElement('summary'); heading.textContent=`DEMO · ${name} · ${new Date().toLocaleTimeString('en-GB')}`;
  const plots=document.createElement('div'); plots.className='result-plots';
  for(const [label, statistics] of [['Current traces',false],['Summary statistics',true]]) {
    const source=demoReport(name,traces,Number(config.seconds),Number(config.voltage),statistics);
    const button=document.createElement('button'); button.type='button'; button.className='result-preview';
    const image=document.createElement('img'); image.src=source; image.alt=`DEMO ${label}`;
    const caption=document.createElement('span'); caption.textContent=label; button.append(image,caption);
    button.addEventListener('click',()=>{
      document.querySelector('#demo-report-image').src=source;
      document.querySelector('#demo-report-dialog').showModal();
    });
    plots.append(button);
  }
  card.append(heading,plots); group.prepend(card);
  document.querySelector('#results-note').textContent='Demo results only · synthetic data, not measurements. Click a preview to enlarge.';
  filterResults();
}

async function seedDemoResults() {
  if(typeof window.pywebview?.api?.save_demo_result!=='function') return;
  document.querySelector('#results-note').textContent='Preparing synthetic demo results…';
  const config={seconds:100,voltage:3.3};
  for(const [name,scale] of [['idle',3],['delay',1],['deep_sleep',.03]]) {
    const traces=Array.from({length:3},(_,repeat)=>demoTrace(100,repeat+1,0).map(point=>
      [point[0],point[1]*scale,point[2]*scale,point[3]*scale]));
    await showDemoReports(name,traces,config);
  }
}

function saveDemoQueueStep(step, index) {
  if(typeof window.pywebview?.api?.save_demo_result!=='function') return;
  const config=standaloneConfiguration(),cards=[...document.querySelectorAll('.dut')];
  for(const board of step.active) {
    const dut=cards.indexOf(board.card);
    const traces=Array.from({length:Number(config.repeats)},(_,repeat)=>demoTrace(Number(config.seconds),repeat+1,dut));
    showDemoReports(`${config.name||'queue'}_step${index+1}_DUT${dut+1}`,traces,config)
      .catch(error=>{document.querySelector('#results-note').textContent=`Demo result failed: ${error.message||error}`;});
  }
}

async function startDemoRun() {
  if(!demoMode || desktopReady) return;
  const config=standaloneConfiguration();
  config.name=config.name.trim() || 'demo_test';
  const count=['hil','one-relay'].includes(currentLayout) ? modeDutCount() : 1;
  const names=Array.from({length:count},(_,index)=>`${config.name}${count>1 ? `_DUT${index+1}` : ''}`);
  const uploads=['hil','one-hub'].includes(currentLayout);
  beginRunProgress(config,names,uploads);
  demoRunActive=true; demoRunCancelled=false; setRunning(true);
  stopButton.disabled=false;
  status.classList.remove('error');
  const output=document.querySelector('#capture-log-output'); output.textContent='DEMO — accelerated frontend simulation. No hardware commands.\n';
  document.querySelector('#capture-log').hidden=false;
  const pause=async ms=>{await new Promise(resolve=>setTimeout(resolve,ms)); if(demoRunCancelled) throw new Error('Stopped');};
  const event=data=>applyRunEvents({events:[data]});
  try {
    showDemoHardware(-1,'prepare');
    if(uploads) for(let board=0;board<count;board++) {
      showDemoHardware(board,'upload');
      event({type:'upload',name:names[board],state:'started'});await pause(900);
      event({type:'upload',name:names[board],state:'completed'});
      showDemoHardware(-1,'prepare');
    }
    for(let board=0;board<count;board++) {
      const name=names[board], traces=[];
      event({type:'capture_plan',name});
      showDemoHardware(board,'warmup');
      event({type:'warmup',state:'started',elapsed:0}); await pause(400);
      event({type:'warmup',state:'completed',elapsed:Number(config.warmup_seconds)});
      for(let repeat=1;repeat<=Number(config.repeats);repeat++) {
        showDemoHardware(board,'calibration');
        event({type:'calibration',state:'started',repeat}); await pause(100);
        event({type:'calibration',state:'completed',repeat});
        showDemoHardware(board,'measure');
        event({type:'repeat',state:'started',repeat,elapsed:0}); event({type:'meter_power',enabled:true});
        const points=demoTrace(Number(config.seconds),repeat,board); traces.push(points);
        for(let start=0;start<points.length;start+=100) {
          event({type:'current_samples',name,repeat,points:points.slice(start,start+100)});
          event({type:'repeat',state:'progress',repeat,elapsed:points[Math.min(start+99,points.length-1)][0]});
          await pause(100);
        }
        event({type:'meter_power',enabled:false}); event({type:'repeat',state:'completed',repeat,elapsed:Number(config.seconds)});
      }
      showDemoHardware(board,'report');
      event({type:'report',state:'started'}); await pause(100);
      await showDemoReports(name,traces,config); event({type:'report',state:'completed'});
    }
    status.textContent='Demo completed. Generated plots are in Results.';
    finishRunProgress('Completed');
  } catch(error) {
    status.textContent=demoRunCancelled ? 'Demo stopped.' : `Demo failed: ${error.message}`;
    finishRunProgress(demoRunCancelled ? 'Stopped' : 'Failed');
  } finally {
    showDemoHardware(-1,'idle'); demoRunActive=false; setRunning(false);stopButton.disabled=false;
    document.querySelectorAll('#results-gallery .result-preview').forEach(button=>{button.disabled=false;});
  }
}
