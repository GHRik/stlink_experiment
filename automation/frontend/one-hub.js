// One-hub preparation reuses the existing upload runner and StandAlone capture.
let oneHubPreparing = false;
let oneHubCancelled = false;

async function startOneHubCapture() {
  const api = window.pywebview.api;
  const config = standaloneConfiguration();
  const value = id => document.querySelector(`#${id}`).value;
  const hub = {driver: value('hub-model'), serial: value('hub-serial'),
    port: Number(hub2Switches[0].dataset.port)};
  const sketch = document.querySelector('#dut1-sketch').dataset.path;
  if (!hubConfigured(document.querySelector('.upload-hub')) || !sketch) {
    status.classList.add('error');
    status.textContent = 'Select the hub model, serial number and a DUT sketch before running.';
    return;
  }
  const board = value('dut1-profile');
  const uploadPort = value('dut1-port');
  oneHubPreparing = true;
  oneHubCancelled = false;
  setRunning(true);
  stopButton.disabled = false;
  const output = document.querySelector('#capture-log-output');
  output.textContent = '';
  document.querySelector('#capture-log').hidden = false;
  const checkStop = () => { if (oneHubCancelled) throw new Error('Setup stopped.'); };
  const log = message => {
    status.textContent = message;
    output.textContent += message + '\n';
    output.scrollTop = output.scrollHeight;
  };
  const pause = async milliseconds => {
    for (let remaining = milliseconds; remaining > 0; remaining -= 100) {
      checkStop();
      await new Promise(resolve => setTimeout(resolve, Math.min(100, remaining)));
    }
    checkStop();
  };
  const switchHub = async enabled => {
    await api.set_hub_port(hub.driver, hub.serial, hub.port, enabled);
    hub2Switches[0].setAttribute('aria-pressed', String(enabled));
    hub2Switches[0].querySelector('.port-state').textContent = enabled ? 'ON' : 'OFF';
    updateConnectionFlows();
  };
  const probe = async () => {
    try {
      await api.set_meter_power(config.port, config.voltage, true);
      displayMeterPower(true);
    } finally {
      await api.set_meter_power(config.port, config.voltage, false);
      displayMeterPower(false);
    }
  };
  const confirm = async message => {
    checkStop();
    log(message);
    if (!await api.confirm_connection(message)) oneHubCancelled = true;
    checkStop();
  };
  try {
    log('Disabling DUT USB port...');
    await switchHub(false);
    checkStop();
    log('Checking STLINK: OUT ON / OFF...');
    await probe();
    await confirm('Please disconnect STLINK from the PC before uploading firmware. Leaving it connected during upload can damage STLINK. Disconnect it, then click OK.');
    log('Enabling DUT USB port...');
    await switchHub(true);
    await pause(2000);
    log('Compiling and uploading firmware...');
    await api.start_upload(board, uploadPort, sketch);
    let cursor = 0;
    while (true) {
      const result = await api.capture_status(cursor);
      cursor = result.cursor;
      if (result.lines.length) {
        output.textContent = (output.textContent + result.lines.join('\n') + '\n').slice(-100000);
        output.scrollTop = output.scrollHeight;
      }
      if (!result.running) {
        checkStop();
        if (result.returncode !== 0) throw new Error(`Upload exited with code ${result.returncode}. See the log below.`);
        break;
      }
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    await switchHub(false);
    await confirm('Firmware uploaded. The DUT USB port is now OFF. Please connect STLINK to the PC, then click OK.');
    for (let attempt = 1; attempt <= 3; attempt++) {
      checkStop();
      log(`Checking STLINK: OUT ON / OFF (attempt ${attempt}/3)...`);
      try { await probe(); break; }
      catch (error) {
        displayMeterPower(null);
        if (attempt === 3) throw error;
        log(`STLINK check failed: ${error.message || error}. Retrying in 5 seconds...`);
        await pause(5000);
      }
    }
    checkStop();
    oneHubPreparing = false;
    await startStandaloneCapture(true, config);
  } catch (error) {
    // Do not enable measurement power after an incomplete preparation.
    try { await switchHub(false); } catch (cleanupError) { log(`USB cleanup failed: ${cleanupError.message || cleanupError}`); }
    oneHubPreparing = false;
    setRunning(false);
    updateMeterControls();
    status.classList.toggle('error', !oneHubCancelled);
    log(oneHubCancelled ? 'Setup stopped. Measurement was not started.' : `One hub setup failed: ${error.message || error}`);
  }
}

function stopOneHubPreparation() {
  oneHubCancelled = true;
  stopButton.disabled = true;
  status.textContent = 'Stopping setup. If upload is active, waiting for it to finish...';
}
