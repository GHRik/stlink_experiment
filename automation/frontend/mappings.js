// Logical connections keep their own row; selectors choose physical USB/relay channels.
function initializeChannelMappings() {
  document.querySelectorAll('.hub-port, .relay-channel').forEach((button, index) => {
    const relay = button.classList.contains('relay-channel');
    const number = relay ? relayChannelNumber(button.dataset.channel) : Number(button.dataset.port);
    const row = document.createElement('div');
    row.className = 'connection-row';
    const select = document.createElement('select');
    select.className = 'channel-mapping';
    select.id = `channel-mapping-${index}`;
    select.setAttribute('aria-label', `${relay ? 'Relay channel' : 'USB port'} for ${button.querySelector('span').textContent}`);
    select.title = relay ? 'Physical relay channel' : 'Physical USB socket';
    select.add(new Option(String(number), String(number)));
    button.before(row);
    row.append(select, button);
    const label = button.querySelector('span');
    label.textContent = label.textContent.replace(/^\d+\s*(?:·|→)\s*/, '');
    select.addEventListener('change', () => {
      const offset = relay ? relayChannelNumber(0) : 0;
      const previous = Number(button.dataset[relay ? 'channel' : 'port']) + offset;
      const peers = relay ? relaySwitches : button.closest('.primary-hub') ? hub1Switches : hub2Switches;
      const occupied = peers.find(other => other !== button && !other.hidden && Number(other.parentElement.querySelector('select').value) === Number(select.value));
      if (occupied) {
        occupied.parentElement.querySelector('select').value = String(previous);
        occupied.setAttribute('aria-pressed', desktopReady ? 'mixed' : 'false');
        occupied.querySelector('.port-state').textContent = desktopReady ? '?' : 'OFF';
      }
      button.dataset[relay ? 'channel' : 'port'] = String(Number(select.value) - offset);
      button.setAttribute('aria-pressed', desktopReady ? 'mixed' : 'false');
      button.querySelector('.port-state').textContent = desktopReady ? '?' : 'OFF';
      updateChannelMappings();
      updateConnectionFlows();
    });
  });
  updateChannelMappings();
}

function updateChannelMappings() {
  const groups = [
    {buttons: hub1Switches, first: 1, limit: hubPortCount(document.querySelector('.primary-hub'))},
    {buttons: hub2Switches, first: 1, limit: hubPortCount(document.querySelector('.upload-hub'))},
    {buttons: relaySwitches, first: relayChannelNumber(0), limit: document.querySelector('#relay-model').value === 'lcus2' ? 2 : 4},
  ];
  groups.forEach(({buttons, first, limit}) => {
    if (!buttons[0]?.closest('.connection-row')) return;
    const assigned = new Set();
    const values = new Map();
    [...buttons].sort((a, b) => Number(a.hidden) - Number(b.hidden)).forEach(button => {
      let value = Number(button.parentElement.querySelector('select').value);
      if (value < first || value >= first+limit || (!button.hidden && assigned.has(value))) {
        value = Array.from({length: limit}, (_, index) => index + first).find(port => !assigned.has(port)) ?? first;
      }
      values.set(button, value);
      if (!button.hidden) assigned.add(value);
    });
    buttons.forEach(button => {
      const select = button.parentElement.querySelector('select');
      const value = values.get(button);
      select.replaceChildren();
      for (let number = first; number < first+limit; number++) {
        const option = new Option(String(number), String(number));
        select.add(option);
      }
      select.value = String(value);
      const relay = button.classList.contains('relay-channel');
      button.dataset[relay ? 'channel' : 'port'] = String(value - (relay ? first : 0));
      button.parentElement.hidden = button.hidden;
    });
  });
  document.querySelectorAll('.dut').forEach((card, index) => {
    const usb = hub2Switches[index]?.dataset.port;
    const relay = relayChannelNumber(relaySwitches[index]?.dataset.channel);
    if (currentLayout === 'hil') card.querySelector('small').textContent = `USB port ${usb} · relay ${relay}`;
    if (currentLayout === 'one-hub') card.querySelector('small').textContent = `USB port ${usb}`;
    if (currentLayout === 'one-relay') card.querySelector('small').textContent = `Relay ${relay} · firmware uploaded separately`;
  });
}
