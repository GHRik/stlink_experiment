// Manual OUT control uses the selected SMU port and configured voltage.
let meterBusy = false;

function displayMeterPower(enabled) {
  const button = document.querySelector('#meter-output');
  button.setAttribute('aria-pressed', enabled === null ? 'mixed' : String(enabled));
  button.querySelector('.port-state').textContent = enabled === null ? '?' : enabled ? 'ON' : 'OFF';
  updateConnectionFlows();
}

function updateMeterControls() {
  if (!desktopReady) return;
  const select = document.querySelector('#meter-port');
  document.querySelector('#meter-output').disabled = isRunning || meterBusy || !select.value || select.selectedOptions[0]?.disabled;
}

async function switchMeterPower() {
  if (isRunning || meterBusy) return;
  const port = document.querySelector('#meter-port').value;
  if (!port) return;
  const voltage = document.querySelector('#measurement-voltage').value;
  const enabled = document.querySelector('#meter-output').getAttribute('aria-pressed') !== 'true';
  meterBusy = true;
  const controls = [...document.querySelectorAll('.power-meter button, .power-meter select'),
    document.querySelector('#measurement-voltage'), runButton];
  const previous = controls.map(control => ({control, disabled: control.disabled}));
  controls.forEach(control => { control.disabled = true; });
  status.classList.remove('error');
  status.textContent = `Switching STLINK OUT ${enabled ? 'ON' : 'OFF'}…`;
  try {
    const result = await window.pywebview.api.set_meter_power(port, voltage, enabled);
    displayMeterPower(result.enabled);
    status.textContent = `STLINK OUT confirmed ${result.enabled ? `ON (${result.voltage} V)` : 'OFF'}.`;
  } catch (error) {
    displayMeterPower(null);
    status.classList.add('error');
    status.textContent = `OUT switching failed: ${error.message || error}`;
  } finally {
    meterBusy = false;
    previous.forEach(({control, disabled}) => { control.disabled = disabled; });
    runButton.disabled = isRunning || refreshingPorts || switchingHub || relayBusy;
    updateMeterControls();
  }
}
