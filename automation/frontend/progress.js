// Telemetry updates the diagram independently of disabled user controls.
let runProgress = null;

function beginRunProgress(config, names = [config.name], uploads = false) {
  runProgress = {finished: false, current: '', phase: 'Preparing', clock: null,
    boards: names.map(name => ({name: name.trim(), repeats: Number(config.repeats), seconds: Number(config.seconds),
      warmup: Number(config.warmup_seconds), warmElapsed: 0, elapsed: 0, calibration: 0,
      completed: 0, repeat: 0, warmed: false, report: false, upload: uploads ? false : null}))};
  document.querySelector('#run-progress').hidden = false;
  renderRunProgress();
}

function applyRunEvents(result) {
  for (const event of result.events || []) {
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
  const current = boards.find(board => board.name === runProgress.current);
  document.querySelector('#run-stage').textContent = `${runProgress.current || 'Setup'} · ${runProgress.phase}${current?.repeat ? ` · Repeat ${current.repeat}/${current.repeats}` : ''}`;
  document.querySelector('#run-count').textContent = `${done}/${total} stages done · ${total - done} remaining`;
  document.querySelector('#run-time').textContent = `${runProgress.finished && runProgress.phase !== 'Completed' ? 'Unfinished' : 'Remaining'} programmed time: ${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  document.querySelector('#run-bar').max = total;
  document.querySelector('#run-bar').value = done;
  document.querySelector('#run-done').replaceChildren(...boards.map(board => {
    const item = document.createElement('li');
    item.textContent = `${board.name}: ${board.upload === null ? '' : `Upload ${board.upload ? 'done' : 'pending'} · `}Warm-up ${board.warmed ? 'done' : 'pending'} · Calibration ${board.calibration}/${board.repeats} · Repeats ${board.completed}/${board.repeats} · Report ${board.report ? 'done' : 'pending'}`;
    return item;
  }));
}

setInterval(renderRunProgress, 1000);
