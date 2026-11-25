// Layouts reuse the existing cards, form fields, switches and animated SVG paths.
let currentLayout = 'standalone';

function modeDutCount() {
  if (currentLayout === 'standalone') return 1;
  if (currentLayout === 'one-hub') return 1;
  const relayLimit = document.querySelector('#relay-model').value === 'lcus2' ? 2 : 3;
  const count = Math.min(Number(relayCount.value), relayLimit);
  return currentLayout === 'hil'
    ? Math.min(count, hubPortCount(document.querySelector('.upload-hub')))
    : count;
}

function initializeModes() {
  const tabs = [...document.querySelectorAll('.layout-tabs [data-layout]')];
  function activate(layout) {
    if (isRunning || switchingHub || meterBusy || relayBusy) return;
    document.dispatchEvent(new Event('close-device-menus'));
    currentLayout = layout;
    document.querySelector('.wiring-diagram').dataset.layout = layout;
    tabs.forEach(tab => tab.setAttribute('aria-pressed', String(tab.dataset.layout === layout)));
    const visibility = {
      '.primary-hub': layout === 'hil',
      '.upload-hub': layout === 'hil' || layout === 'one-hub',
      '.relay': layout === 'hil' || layout === 'one-relay',
      '.relay-contacts': layout === 'hil' || layout === 'one-relay',
      '.external-power': layout === 'hil',
    };
    Object.entries(visibility).forEach(([selector, visible]) => {
      document.querySelector(selector).hidden = !visible;
    });
    // HIL's upstream hub needs three sockets; its DUT hub may be single-port XS.
    ['#hub1-model', '#hub-model'].forEach(selector => {
      const model = document.querySelector(selector);
      const xs = model.querySelector('option[value="ykushxs"]');
      const unavailable = layout === 'hil' && selector === '#hub1-model';
      xs.hidden = unavailable;
      xs.disabled = unavailable;
      if (unavailable && model.value === 'ykushxs') {
        model.value = '';
        model.dispatchEvent(new Event('change'));
      }
    });
    document.querySelectorAll('.dut').forEach((card, index) => {
      card.querySelector('small').textContent = layout === 'standalone' ? 'Firmware uploaded separately'
        : layout === 'one-hub' ? `USB port ${index + 1}`
        : layout === 'one-relay' ? `Relay ${index + 1} · firmware uploaded separately`
        : `YKUSH port ${index + 1} · relay ${index + 1}`;
    });
    updateDeviceCount();
  }
  tabs.forEach(tab => tab.addEventListener('click', () => activate(tab.dataset.layout)));
  activate('standalone');
}

function modeConnectionActive(index, hilActive) {
  if (currentLayout === 'hil') return hilActive();
  if (index === 1 || index === 2 || index === 3 || index === 4) return true;
  if (index === 5) return isOn(meterOutput);
  const dut = Math.floor((index - 6) / 2);
  if (index >= 6 && index % 2 === 0) return isOn(meterOutput) && isOn(relaySwitches[dut]);
  if (index >= 7) return isOn(hub2Switches[dut]);
  return false;
}

function routeModeConnections() {
  const diagram = document.querySelector('.wiring-diagram').getBoundingClientRect();
  document.querySelector('.wiring-connections').setAttribute('viewBox', `0 0 ${diagram.width} ${diagram.height}`);
  function anchor(selector, side = 'right', switchElement = null) {
    const card = document.querySelector(selector);
    const rect = card.getBoundingClientRect();
    const row = switchElement ? switchElement.getBoundingClientRect() : rect;
    return {x: (side === 'left' ? rect.left : rect.right) - diagram.left,
      y: row.top + row.height / 2 - diagram.top};
  }
  const pathVia = (start, end, lane) => `M${start.x} ${start.y} H${lane} V${end.y} H${end.x}`;
  const paths = Array(12).fill(null);
  const hil = currentLayout === 'hil';
  const single = currentLayout === 'standalone';
  const oneHub = currentLayout === 'one-hub';
  const oneRelay = currentLayout === 'one-relay';
  const hasHub = hil || currentLayout === 'one-hub';
  const hasRelay = hil || currentLayout === 'one-relay';
  const pc = anchor('.pc');
  const meter = anchor('.power-meter', 'left');
  const output = anchor('.power-meter', 'right', meterOutput);
  const count = modeDutCount();
  if (hil) {
    const hub = anchor('.primary-hub', 'left');
    const pcTop = document.querySelector('.pc').offsetTop;
    paths[0] = `M${pc.x} ${pc.y} H365 V${pcTop - 30} H120 V${hub.y} H${hub.x}`;
    paths[1] = pathVia(anchor('.primary-hub', 'right', hub1Switches[0]), meter, 350);
    if (hubPortCount(document.querySelector('.primary-hub')) > 1) {
      paths[2] = pathVia(anchor('.primary-hub', 'right', hub1Switches[1]), anchor('.relay', 'left'), 370);
      paths[3] = pathVia(anchor('.primary-hub', 'right', hub1Switches[2]), anchor('.upload-hub', 'left'), 390);
    }
  } else {
    paths[1] = pathVia({...pc, y: pc.y - (oneHub || oneRelay ? 30 : 0)}, meter, 390);
    if (hasRelay) paths[2] = pathVia({...pc, y: pc.y + 30}, anchor('.relay', 'left'), 350);
    if (hasHub) {
      const hub = anchor('.upload-hub', 'left');
      paths[3] = pathVia(pc, {...hub, y: hub.y - 25}, 370);
    }
  }
  if (hasRelay) {
    paths[4] = pathVia(anchor('.relay'), anchor('.relay-contacts', 'left'), 630);
    paths[5] = pathVia(output, {x: 745, y: document.querySelector('.relay-contacts').offsetTop}, 745);
  } else if (single || currentLayout === 'one-hub') {
    paths[5] = pathVia(output, anchor('.dut-position-1', 'left'), 750);
  }
  for (let index = 0; index < count; index++) {
    const target = anchor(`.dut-position-${index + 1}`, 'left');
    if (hasRelay) {
      const source = anchor('.relay-contacts', 'right', relaySwitches[index]);
      if (oneRelay) {
        paths[6 + index * 2] = pathVia(source, target, [900, 925, 950][index]);
      } else {
        paths[6 + index * 2] = pathVia(source, {...target, y: target.y - 55}, [900, 875, 850][index]);
      }
    }
    if (hasHub) {
      const source = anchor('.upload-hub', 'right', hub2Switches[index]);
      const end = {...target, y: target.y + 70};
      paths[7 + index * 2] = oneHub ? pathVia(source, end, 820) : index === 0
        ? `M${source.x} ${source.y} H650 V${source.y - 35} H940 V${end.y} H${end.x}`
        : pathVia(source, end, [940, 965, 990][index]);
    }
  }
  connectionFlows.forEach((flow, index) => {
    const path = paths[index];
    flow.modeVisible = Boolean(path);
    flow.line.style.display = path ? '' : 'none';
    if (path) {
      flow.line.setAttribute('d', path);
      flow.motion.setAttribute('path', path);
    }
  });
  function label(selector, visible, x, y, text) {
    const element = document.querySelector(selector);
    element.toggleAttribute('hidden', !visible);
    element.style.display = visible ? '' : 'none';
    if (x !== undefined) element.setAttribute('x', x);
    if (y !== undefined) element.setAttribute('y', y);
    if (text !== undefined) element.textContent = text;
  }
  label('#pc-usb-label', true, oneHub || oneRelay ? pc.x + 10 : pc.x - 100, pc.y - (oneHub || oneRelay ? 45 : 30), hil ? 'USB - Data line only' : 'USB');
  label('#relay-control-label', hasRelay, 610, anchor('.relay').y - 12);
  label('#meter-output-label', hasRelay || single || currentLayout === 'one-hub', output.x + 10, output.y - 12);
  const relayStart = anchor('.relay-contacts', 'right', relaySwitches[0]);
  label('.dut-supply-label', hasRelay, relayStart.x + 10, relayStart.y - 12);
  const uploadLabel = anchor('.upload-hub', 'right', hub2Switches[Math.max(0, count - 1)]);
  label('#upload-label', hasHub, uploadLabel.x + 15, uploadLabel.y - 12);
  const external = document.querySelector('.external-power-wire');
  external.style.display = hil || currentLayout === 'one-hub' ? '' : 'none';
  if (hil) external.setAttribute('d', 'M179 465 H240 V577');
  if (currentLayout === 'one-hub') {
    const hub = anchor('.upload-hub', 'left');
    external.setAttribute('d', pathVia({...pc, y: pc.y + 30}, {...hub, y: hub.y + 25}, 350));
  }
  const hubInput = anchor('.upload-hub', 'left');
  label('#hub-power-label', oneHub, pc.x + 10, pc.y + 52, 'USB · 5 V power');
  label('#hub-data-label', oneHub, pc.x + 10, pc.y - 10, 'USB · data');
}
