// Relay channel labels are one-based; the shared Python drivers use zero-based indices.
let relayBusy = false;

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
  status.textContent = `Switching relay ${channel + 1} ${enabled ? 'ON' : 'OFF'}…`;
  try {
    const result = await window.pywebview.api.set_relay(driver, port, channel, enabled);
    button.setAttribute('aria-pressed', String(result.enabled));
    button.querySelector('.port-state').textContent = result.enabled ? 'ON' : 'OFF';
    status.textContent = `Relay ${channel + 1} ${result.enabled ? 'ON' : 'OFF'} · ${result.confirmation === 'readback' ? 'state confirmed' : 'command sent'}.`;
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
