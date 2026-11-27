// Telemetry updates the diagram independently of disabled user controls.
let runProgress = null;

function beginRunProgress(config, names = [config.name], uploads = false) {
  document.querySelector('#queue-progress').hidden = true;
  if (typeof stopLiveDemo === 'function') stopLiveDemo();
  if (typeof resetLiveCurrent === 'function') resetLiveCurrent();
  runProgress = {finished: false, current: '', phase: 'Preparing', clock: null,
    boards: names.map(name => ({name: name.trim(), repeats: Number(config.repeats), seconds: Number(config.seconds),
      warmup: Number(config.warmup_seconds), warmElapsed: 0, elapsed: 0, calibration: 0,
      completed: 0, repeat: 0, warmed: false, report: false, active: '', stageSince: Date.now(), upload: uploads ? false : null}))};
  document.querySelector('#run-progress').hidden = false;
  renderRunProgress();
}

function applyRunEvents(result) {
  for (const event of result.events || []) {
    if (typeof updateLiveCurrent === 'function') updateLiveCurrent(event);
    if (event.type === 'meter_power') displayMeterPower(event.enabled);
    if (event.type === 'hub' || event.type === 'relay') {
      const buttons = event.type === 'relay' ? relaySwitches : [...hub1Switches, ...hub2Switches];
      buttons.filter(button => event.type === 'relay'
        ? Number(button.dataset.channel) === event.channel
        : Number(button.dataset.port) === event.port && button.closest('.device-card').querySelector('select[id$="serial"]').value === event.serial
      ).forEach(button => {
        button.setAttribute('aria-pressed', String(event.enabled));
        button.querySelector('.port-state').textContent = event.enabled ? 'ON' : 'OFF';
      });
      updateConnectionFlows();
    }
    if (!runProgress) continue;
    if (event.type === 'capture_plan' || event.type === 'upload') runProgress.current = event.name;
    const board = runProgress.boards.find(board => board.name === runProgress.current);
    if (!board) continue;
    if (['warmup', 'calibration', 'repeat', 'report', 'upload'].includes(event.type)) {
      if (board.active !== event.type || event.state === 'started') board.stageSince = Date.now();
      board.active = event.state === 'completed' ? '' : event.type;
    }
    if (event.type === 'capture_plan') {
      runProgress.phase = 'Preparing measurement';
    } else if (event.type === 'warmup') {
      board.warmElapsed = event.elapsed;
      board.warmed = event.state === 'completed';
      runProgress.phase = board.warmed ? 'Warm-up completed' : 'Warm-up';
    } else if (event.type === 'calibration') {
      board.repeat = event.repeat;
      if (event.state === 'completed') board.calibration = event.repeat;
      runProgress.phase = event.state === 'completed' ? 'Calibration completed' : 'Calibrating';
    } else if (event.type === 'repeat') {
      board.repeat = event.repeat;
      board.elapsed = event.state === 'completed' ? 0 : event.elapsed;
      if (event.state === 'completed') board.completed = event.repeat;
      runProgress.phase = event.state === 'completed' ? 'Repeat completed / analysis' : 'Acquiring samples';
    } else if (event.type === 'report') {
      board.report = event.state === 'completed';
      runProgress.phase = board.report ? 'Report completed' : 'Generating report';
    } else if (event.type === 'upload') {
      board.upload = event.state === 'completed';
      runProgress.phase = board.upload ? 'Upload completed' : 'Compiling / uploading';
    }
    // Interpolate only timed stages; calibrations and reports have no fixed duration.
    if (['capture_plan', 'warmup', 'calibration', 'repeat', 'report', 'upload'].includes(event.type)) {
      runProgress.clock = (event.type === 'repeat' || event.type === 'warmup') && event.state !== 'completed'
        ? {type: event.type, since: Date.now()} : null;
    }
  }
  renderRunProgress();
}

function finishRunProgress(label) {
  if (!runProgress) return;
  runProgress.finished = true;
  runProgress.clock = null;
  runProgress.phase = label;
  renderRunProgress();
  if (typeof refreshResults === 'function') refreshResults();
}

function renderRunProgress() {
  if (!runProgress) return;
  const {boards, clock} = runProgress;
  const total = boards.reduce((sum, board) => sum + 2 + board.repeats * 2 + (board.upload === null ? 0 : 1), 0);
  const done = boards.reduce((sum, board) => sum + Number(board.warmed) + board.calibration + board.completed + Number(board.report) + Number(board.upload === true), 0);
  let remaining = boards.reduce((sum, board) => sum + Math.max(0, board.warmup - board.warmElapsed)
    + Math.max(0, (board.repeats - board.completed) * board.seconds - board.elapsed), 0);
  if (clock) {
    const current = boards.find(board => board.name === runProgress.current);
    const available = clock.type === 'warmup' ? current.warmup - current.warmElapsed : current.seconds - current.elapsed;
    remaining -= Math.min(Math.max(0, available), (Date.now() - clock.since) / 1000);
  }
  const seconds = Math.max(0, Math.ceil(remaining));
  if (typeof updateSketchQueueRemaining === 'function') updateSketchQueueRemaining(remaining);
  const current = boards.find(board => board.name === runProgress.current);
  const formatTime = value => `${Math.floor(value / 60)}min ${value % 60}sec`;
  let stageText = 'Preparing next stage';
  if (runProgress.finished) stageText = runProgress.phase;
  else if (current?.active) {
    if (clock) {
      const available = clock.type === 'warmup' ? current.warmup - current.warmElapsed : current.seconds - current.elapsed;
      const left = Math.max(0, Math.ceil(available - (Date.now() - clock.since) / 1000));
      stageText = `Stage remaining: ${formatTime(left)}`;
    } else {
      stageText = `Stage elapsed: ${formatTime(Math.floor((Date.now() - current.stageSince) / 1000))} · completion time unknown`;
    }
  }
  document.querySelector('#run-stage-time').textContent = stageText;
  document.querySelector('#run-stage').textContent = `${runProgress.current || 'Setup'} · ${runProgress.phase}${current?.repeat ? ` · Repeat ${current.repeat}/${current.repeats}` : ''}`;
  document.querySelector('#run-count').textContent = `${done}/${total} stages done · ${total - done} remaining`;
  document.querySelector('#run-time').textContent = `${runProgress.finished && runProgress.phase !== 'Completed' ? 'Unfinished' : 'Remaining'} programmed time: ${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  document.querySelector('#run-bar').max = total;
  document.querySelector('#run-bar').value = done;
  document.querySelector('#run-done').replaceChildren(...boards.map(board => {
    const item = document.createElement('li');
    const name = document.createElement('strong');
    name.textContent = board.name;
    const stages = [
      ...(board.upload === null ? [] : [['upload', 'Upload', board.upload]]),
      ['warmup', 'Warm-up', board.warmed],
      ['calibration', `Calibration ${board.calibration}/${board.repeats}`, board.calibration === board.repeats],
      ['repeat', `Repeats ${board.completed}/${board.repeats}`, board.completed === board.repeats],
      ['report', 'Report', board.report]
    ];
    item.replaceChildren(name, ...stages.map(([key, label, done]) => {
      const badge = document.createElement('span');
      const state = done ? 'done' : !runProgress.finished && board.name === runProgress.current && board.active === key ? 'running' : 'pending';
      badge.className = `stage-badge stage-${state}`;
      badge.textContent = `${label} ${state.toUpperCase()}`;
      return badge;
    }));
    return item;
  }));
}

setInterval(renderRunProgress, 1000);
