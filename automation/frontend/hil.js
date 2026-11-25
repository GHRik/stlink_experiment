// Export the selected DUT mappings; Python fills the existing runner defaults.
function hilConfiguration() {
  const value = id => document.querySelector(`#${id}`).value;
  return {
    ...standaloneConfiguration(),
    hub: {driver: value('hub-model'), serial: value('hub-serial')},
    relay: {driver: value('relay-model'), port: value('relay-port')},
    boards: relaySwitches.flatMap((button, index) => button.hidden ? [] : [{
      upload_profile: value(`dut${index + 1}-profile`),
      sketch: document.querySelector(`#dut${index + 1}-sketch`).dataset.path || '',
      com: value(`dut${index + 1}-port`),
      ykush_usb_port: Number(hub2Switches[index].dataset.port),
      relay: Number(button.dataset.channel),
    }]),
  };
}

function startHilCapture() {
  const config = hilConfiguration();
  if (!hubConfigured(document.querySelector('.upload-hub')) || config.boards.some(board => !board.sketch)) {
    status.classList.add('error');
    status.textContent = 'Select the DUT hub model, serial number and a sketch for each DUT before running.';
    return;
  }
  startStandaloneCapture(false, config, 'start_hil');
}
