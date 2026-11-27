// Run with: node --test tests/test_gui_one_relay.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup({driver = 'numato', failedCapture = false, stopDuringCapture = false, stopDuringWait = false} = {}) {
  const calls = [];
  const config = {port: 'COM18', voltage: '3.3', name: 'test', repeats: '10', controller: 'C:/control.py'};
  const fields = {'relay-model': {value: driver}, 'relay-port': {value: 'COM19'},
    'capture-log-output': {textContent: ''}, 'capture-log': {}};
  const buttons = [driver === 'lcus2' ? 1 : 3, 0].map(channel => ({hidden: false,
    dataset: {channel: String(channel)}, setAttribute() {}, querySelector() {return {};}}));
  let context;
  let stopped = false;
  const api = {
    async set_relay(...args) {calls.push(['relay', ...args]);},
    async set_meter_power(...args) {calls.push(['meter', ...args]);},
    async start_capture(configuration) {calls.push(['capture', configuration]);},
    async capture_status() {
      if (stopDuringCapture && !stopped) {
        stopped = true;
        await vm.runInContext('stopOneRelayCapture()', context);
      }
      return {running: false, returncode: failedCapture ? 1 : 0, cursor: 1, lines: ['measurement output']};
    },
  };
  context = vm.createContext({
    window: {pywebview: {api}}, document: {querySelector: selector => fields[selector.slice(1)]},
    relayChannelNumber: (channel,driver) => channel + (driver === "lcus2" ? 1 : 0),
    standaloneConfiguration: () => config, relaySwitches: buttons, captureInProgress: false,
    beginRunProgress() {}, applyRunEvents() {}, finishRunProgress() {},
    setRunning(value) {calls.push(['locked', value]);},
    stopButton: {}, status: {classList: {remove() {}, toggle() {}}},
    displayMeterPower() {}, updateConnectionFlows() {}, updateMeterControls() {}, updateRelayControls() {},
    async stopStandaloneCapture() {calls.push(['stop']);},
    setTimeout(resolve, ms) {
      calls.push(['wait', ms]);
      if (stopDuringWait) vm.runInContext('relaySequenceCancelled = true', context);
      resolve();
    },
  });
  vm.runInContext(fs.readFileSync('automation/frontend/one-relay.js', 'utf8'), context);
  return {context, calls, config};
}

test('Numato disables all four channels, then measures mapped DUTs in row order', async () => {
  const {context, calls, config} = setup();
  await vm.runInContext('startOneRelayCapture()', context);
  const actions = calls.filter(call => call[0] !== 'wait' && call[0] !== 'locked');
  assert.deepEqual(actions.slice(0, 5), [
    ['relay', 'numato', 'COM19', 0, false], ['relay', 'numato', 'COM19', 1, false],
    ['relay', 'numato', 'COM19', 2, false], ['relay', 'numato', 'COM19', 3, false],
    ['meter', 'COM18', '3.3', false],
  ]);
  assert.deepEqual(actions.slice(5).map(c => c[0]), ['relay', 'capture', 'relay', 'relay', 'capture', 'relay']);
  const captures = calls.filter(call => call[0] === 'capture').map(call => call[1]);
  assert.deepEqual(captures.map(c => c.name), ['test_relay3', 'test_relay0']);
  assert.equal(captures[0].controller, config.controller);
  assert.equal(captures[0].repeats, '10');
  assert.equal(calls.filter(c => c[0] === 'wait').reduce((sum, c) => sum + c[1], 0), 8000);
  assert.deepEqual(calls.at(-1), ['locked', false]);
});

test('LCUS-2 initializes only its two channels', async () => {
  const {context, calls} = setup({driver: 'lcus2'});
  await vm.runInContext('startOneRelayCapture()', context);
  assert.equal(calls.filter(c => c[0] === 'relay').every(c => c[3] < 2), true);
  assert.deepEqual(calls.filter(c => c[0] === 'capture').map(c => c[1].name), ['test_relay2', 'test_relay1']);
});

for (const options of [{failedCapture: true}, {stopDuringCapture: true}, {stopDuringWait: true}]) {
  test(`Failure or STOP disables active relay and skips subsequent DUTs: ${JSON.stringify(options)}`, async () => {
    const {context, calls} = setup(options);
    await vm.runInContext('startOneRelayCapture()', context);
    assert.equal(calls.filter(c => c[0] === 'capture').length, options.stopDuringWait ? 0 : 1);
    assert.deepEqual(calls.filter(c => c[0] === 'relay').at(-1), ['relay', 'numato', 'COM19', 3, false]);
    assert.deepEqual(calls.at(-1), ['locked', false]);
    if (options.stopDuringCapture) assert.equal(calls.some(c => c[0] === 'stop'), true);
  });
}
