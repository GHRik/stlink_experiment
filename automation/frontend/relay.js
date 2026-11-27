// Numato hardware labels start at 0; LCUS-2 labels start at 1. Driver indices start at 0.
let relayBusy = false;
let readingHardwareStates = false;

async function refreshHardwareStates() {
  if (!desktopReady || relayBusy || switchingHub || readingHardwareStates) return;
  readingHardwareStates = true;
  const api = window.pywebview.api;
  const show = (buttons, states, key) => buttons.forEach(button => {
    const enabled = states[button.dataset[key]];
    button.setAttribute('aria-pressed', typeof enabled === 'boolean' ? String(enabled) : 'mixed');
    button.querySelector('.port-state').textContent = typeof enabled === 'boolean' ? (enabled ? 'ON' : 'OFF') : '?';
    button.title = typeof enabled === 'boolean' ? 'State read from device' : 'State unavailable';
  });
  try {
    const model = document.querySelector('#relay-model');
    const port = document.querySelector('#relay-port');
    const driver = model.value, address = port.value;
    // HIL owns the relay COM connection; its confirmed switch events update the diagram.
    const hilOwnsRelay = isRunning && currentLayout === 'hil';
    if (!hilOwnsRelay && address && !port.selectedOptions[0]?.disabled && !document.querySelector('.relay').hidden) {
      let states = {};
      try { states = await api.read_relay_states(driver, address); }
      catch (error) { status.textContent = `Relay readback failed: ${error.message || error}`; }
      if (!relayBusy && !(isRunning && currentLayout === 'hil') && driver === model.value && address === port.value) show(relaySwitches, states, 'channel');
    }
    for (const card of document.querySelectorAll('.primary-hub, .upload-hub')) {
      if (switchingHub || card.hidden || !hubConfigured(card)) continue;
      const model = card.querySelector('select[id$="model"]');
      const serial = card.querySelector('select[id$="serial"]');
      const driver = model.value, address = serial.value;
      let states = {};
      try { states = await api.read_hub_states(driver, address); }
      catch (error) { status.textContent = `Hub readback failed: ${error.message || error}`; }
      if (!switchingHub && driver === model.value && address === serial.value) {
        show(card.querySelectorAll('.hub-port'), states, 'port');
      }
    }
  } finally {
    readingHardwareStates = false;
    updateConnectionFlows();
  }
}

function relayChannelNumber(channel, driver = document.querySelector('#relay-model').value) {
  return Number(channel) + (driver === 'lcus2' ? 1 : 0);
}

function resetRelayStates() {
  if (!desktopReady) return;
  relaySwitches.forEach(button => {
    button.setAttribute('aria-pressed', 'mixed');
    button.querySelector('.port-state').textContent = '?';
  });
  updateConnectionFlows();
}

function updateRelayControls() {
  if (!desktopReady) return;
  const port = document.querySelector('#relay-port');
  relaySwitches.forEach(button => {
    button.disabled = isRunning || relayBusy || !port.value || port.selectedOptions[0]?.disabled;
  });
}

async function switchRelay(button) {
  if (isRunning || relayBusy) return;
  const driver = document.querySelector('#relay-model').value;
  const port = document.querySelector('#relay-port').value;
  if (!port) return;
  const channel = Number(button.dataset.channel);
  const enabled = button.getAttribute('aria-pressed') !== 'true';
  relayBusy = true;
  const controls = [...document.querySelectorAll('.relay button, .relay select, .relay-contacts button, .relay-contacts select'), runButton];
  const previous = controls.map(control => ({control, disabled: control.disabled}));
  controls.forEach(control => { control.disabled = true; });
  button.setAttribute('aria-busy', 'true');
  status.classList.remove('error');
  status.textContent = `Switching relay ${relayChannelNumber(channel,driver)} ${enabled ? 'ON' : 'OFF'}…`;
  try {
    const result = await window.pywebview.api.set_relay(driver, port, channel, enabled);
    button.setAttribute('aria-pressed', String(result.enabled));
    button.querySelector('.port-state').textContent = result.enabled ? 'ON' : 'OFF';
    status.textContent = `Relay ${relayChannelNumber(channel,driver)} ${result.enabled ? 'ON' : 'OFF'} · ${result.confirmation === 'readback' ? 'state confirmed' : 'command sent'}.`;
  } catch (error) {
    button.setAttribute('aria-pressed', 'mixed');
    button.querySelector('.port-state').textContent = '?';
    status.classList.add('error');
    status.textContent = error.message || String(error);
  } finally {
    relayBusy = false;
    button.removeAttribute('aria-busy');
    previous.forEach(({control, disabled}) => { control.disabled = disabled; });
    runButton.disabled = isRunning || refreshingPorts || switchingHub || meterBusy;
    updateRelayControls();
    updateConnectionFlows();
  }
}
