// StandAlone delegates measurement, validation and cleanup to the existing CLI.
let captureInProgress = false;
let captureCursor = 0;

function standaloneConfiguration() {
  const value = id => document.querySelector(`#${id}`).value;
  return {
    port: value('meter-port'), name: value('test-name'), description: value('test-description'),
    repeats: value('measurement-repeats'), seconds: value('measurement-seconds'), hz: value('measurement-hz'),
    voltage: value('measurement-voltage'), warmup_seconds: value('measurement-warmup'), off_seconds: value('measurement-off'),
    controller: document.querySelector('#measurement-controller').dataset.path || '',
  };
}

async function startStandaloneCapture(preserveLog = false, config = standaloneConfiguration()) {
  if (!isRunning) setRunning(true);
  stopButton.disabled = true;
  captureCursor = 0;
  const output = document.querySelector('#capture-log-output');
  if (!preserveLog) output.textContent = '';
  document.querySelector('#capture-log').hidden = false;
  status.classList.remove('error');
  status.textContent = 'Starting measurement…';
  try {
    await window.pywebview.api.start_capture(config);
    displayMeterPower(null);
    captureInProgress = true;
    stopButton.disabled = false;
    status.textContent = 'Measurement running. See the log below.';
    pollCapture();
  } catch (error) {
    stopButton.disabled = false;
    setRunning(false);
    displayMeterPower(null);
    updateMeterControls();
    status.classList.add('error');
    status.textContent = `Could not start capture: ${error.message || error}`;
  }
}

async function pollCapture() {
  if (!captureInProgress) return;
  try {
    const result = await window.pywebview.api.capture_status(captureCursor);
    captureCursor = result.cursor;
    const output = document.querySelector('#capture-log-output');
    if (result.lines.length) {
      output.textContent = (output.textContent + result.lines.join('\n') + '\n').slice(-100000);
      output.scrollTop = output.scrollHeight;
    }
    if (!result.running) {
      captureInProgress = false;
      stopButton.disabled = false;
      setRunning(false);
      displayMeterPower(result.returncode === 0 ? false : null);
      updateMeterControls();
      status.classList.toggle('error', result.returncode !== 0 && !result.stopping);
      status.textContent = result.stopping ? 'Measurement stopped.'
        : result.returncode === 0 ? 'Measurement completed. Results location is in the log.'
        : `Capture exited with code ${result.returncode}. See the log below.`;
      return;
    }
  } catch (error) {
    status.classList.add('error');
    status.textContent = `Could not read capture log: ${error.message || error}`;
  }
  setTimeout(pollCapture, 500);
}

async function stopStandaloneCapture() {
  stopButton.disabled = true;
  status.textContent = 'Stopping measurement; waiting for cleanup…';
  try {
    await window.pywebview.api.stop_capture();
  } catch (error) {
    stopButton.disabled = false;
    status.classList.add('error');
    status.textContent = `Could not stop capture: ${error.message || error}`;
  }
}
