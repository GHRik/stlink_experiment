// Measure each mapped DUT in order, keeping all GUI controls locked between captures.
let relaySequenceRunning = false;
let relaySequenceCancelled = false;

async function startOneRelayCapture() {
  const api = window.pywebview.api;
  const config = standaloneConfiguration();
  const driver = document.querySelector('#relay-model').value;
  const port = document.querySelector('#relay-port').value;
  const channels = relaySwitches.filter(button => !button.hidden).map(button => Number(button.dataset.channel));
  beginRunProgress(config, channels.map(channel => `${config.name.trim()}_relay${channel + 1}`));
  const totalChannels = driver === 'lcus2' ? 2 : 4;
  const output = document.querySelector('#capture-log-output');
  output.textContent = '';
  document.querySelector('#capture-log').hidden = false;
  relaySequenceRunning = true;
  relaySequenceCancelled = false;
  setRunning(true);
  stopButton.disabled = false;
  status.classList.remove('error');
  const checkStop = () => { if (relaySequenceCancelled) throw new Error('Sequence stopped.'); };
  const log = message => {
    status.textContent = message;
    output.textContent += message + '\n';
    output.scrollTop = output.scrollHeight;
  };
  const pause = async () => {
    for (let i = 0; i < 20; i++) {
      checkStop();
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    checkStop();
  };
  const switchRelayChannel = async (channel, enabled) => {
    await api.set_relay(driver, port, channel, enabled);
    relaySwitches.filter(button => Number(button.dataset.channel) === channel).forEach(button => {
      button.setAttribute('aria-pressed', String(enabled));
      button.querySelector('.port-state').textContent = enabled ? 'ON' : 'OFF';
    });
    updateConnectionFlows();
  };
  try {
    log('Disabling all relay channels...');
    for (let channel = 0; channel < totalChannels; channel++) {
      await switchRelayChannel(channel, false);
    }
    await api.set_meter_power(config.port, config.voltage, false);
    displayMeterPower(false);
    for (const channel of channels) {
      checkStop();
      let cursor = 0;
      try {
        log(`Relay ${channel + 1} ON. Waiting 2 seconds...`);
        await switchRelayChannel(channel, true);
        await pause();
        const measurement = {...config, name: `${config.name.trim()}_relay${channel + 1}`};
        log(`Measuring ${measurement.name}...`);
        await api.start_capture(measurement);
        captureInProgress = true;
        displayMeterPower(null);
        while (true) {
          const result = await api.capture_status(cursor);
          applyRunEvents(result);
          cursor = result.cursor;
          if (result.lines.length) {
            output.textContent = (output.textContent + result.lines.join('\n') + '\n').slice(-100000);
            output.scrollTop = output.scrollHeight;
          }
          if (!result.running) {
            captureInProgress = false;
            displayMeterPower(result.returncode === 0 ? false : null);
            checkStop();
            if (result.returncode !== 0) throw new Error(`Capture exited with code ${result.returncode}. See the log below.`);
            break;
          }
          await new Promise(resolve => setTimeout(resolve, 500));
        }
      } finally {
        // Capture cleanup must finish before disconnecting the DUT.
        if (captureInProgress) {
          await api.stop_capture();
          let cleanup;
          do {
            cleanup = await api.capture_status(cursor);
            cursor = cleanup.cursor;
            applyRunEvents(cleanup);
            if (!cleanup.running) break;
            await new Promise(resolve => setTimeout(resolve, 500));
          } while (cleanup.running);
          captureInProgress = false;
        }
        await switchRelayChannel(channel, false);
      }
      log(`Relay ${channel + 1} OFF. Waiting 2 seconds...`);
      await pause();
    }
    log('Relay sequence completed. Results locations are in the log.');
    finishRunProgress('Completed');
  } catch (error) {
    status.classList.toggle('error', !relaySequenceCancelled);
    log(relaySequenceCancelled ? 'Relay sequence stopped.' : `Relay sequence failed: ${error.message || error}`);
    finishRunProgress(relaySequenceCancelled ? 'Stopped' : 'Failed');
  } finally {
    relaySequenceRunning = false;
    setRunning(false);
    stopButton.disabled = false;
    updateMeterControls();
    updateRelayControls();
  }
}

async function stopOneRelayCapture() {
  relaySequenceCancelled = true;
  stopButton.disabled = true;
  status.textContent = 'Stopping relay sequence; waiting for capture cleanup...';
  if (captureInProgress) await stopStandaloneCapture();
}
