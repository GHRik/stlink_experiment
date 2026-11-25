// Run with: node --test tests/test_gui_one_hub.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup({failUpload = false, failedReconnects = 0, cancelPrompt = false} = {}) {
  const calls = [];
  let probes = 0;
  const fields = Object.fromEntries(Object.entries({
    'hub-model': 'ykushxs', 'hub-serial': 'XS123', 'dut1-profile': 'nodemcu', 'dut1-port': 'COM22',
  }).map(([id, value]) => [id, {value}]));
  fields['dut1-sketch'] = {dataset: {path: 'C:/my sketches/example.ino'}};
  fields['capture-log-output'] = {textContent: ''};
  fields['capture-log'] = {};
  const button = {dataset: {port: '1'}, setAttribute() {}, querySelector() {return {};}};
  const api = {
    async set_hub_port(...args) {calls.push(['hub', ...args]);},
    async set_meter_power(...args) {
      calls.push(['meter', ...args]);
      if (args[2] && ++probes > 1 && probes <= 1 + failedReconnects) throw new Error('Port unavailable');
    },
    async confirm_connection(message) {calls.push(['confirm', message]); return !cancelPrompt;},
    async start_upload(...args) {calls.push(['upload', ...args]);},
    async capture_status() {return {cursor: 1, lines: ['Arduino CLI output'], running: false, returncode: failUpload ? 1 : 0};},
  };
  const config = {port: 'COM18', voltage: '3.3', controller: 'C:/controller.py'};
  const context = vm.createContext({
    window: {pywebview: {api}},
    document: {querySelector(selector) {return fields[selector.slice(1)] || {}; }},
    hub2Switches: [button], hubConfigured: () => true,
    beginRunProgress() {}, applyRunEvents() {}, finishRunProgress() {},
    standaloneConfiguration: () => config,
    setRunning(value) {calls.push(['locked', value]);},
    stopButton: {}, status: {classList: {add() {}, toggle() {}}},
    updateConnectionFlows() {}, displayMeterPower() {}, updateMeterControls() {},
    setTimeout(resolve, ms) {calls.push(['wait', ms]); resolve();},
    async startStandaloneCapture(preserve, configuration) {calls.push(['capture', preserve, configuration]);},
  });
  vm.runInContext(fs.readFileSync('automation/frontend/one-hub.js', 'utf8'), context);
  return {calls, context, config};
}

test('One hub Run orders USB switching, confirmations, upload and StandAlone capture', async () => {
  const {calls, context, config} = setup();
  await vm.runInContext('startOneHubCapture()', context);
  assert.deepEqual(calls.filter(c => c[0] !== 'wait').map(c => c[0]),
    ['locked', 'hub', 'meter', 'meter', 'confirm', 'hub', 'upload', 'hub', 'confirm', 'meter', 'meter', 'capture']);
  assert.deepEqual(calls.filter(c => c[0] === 'hub').map(c => c.slice(1)),
    [['ykushxs', 'XS123', 1, false], ['ykushxs', 'XS123', 1, true], ['ykushxs', 'XS123', 1, false]]);
  assert.deepEqual(calls.find(c => c[0] === 'upload'), ['upload', 'nodemcu', 'COM22', 'C:/my sketches/example.ino']);
  assert.equal(calls.at(-1)[2], config);
});

test('STLINK reconnect retries twice with five-second intervals', async () => {
  const {calls, context} = setup({failedReconnects: 2});
  await vm.runInContext('startOneHubCapture()', context);
  assert.equal(calls.filter(c => c[0] === 'meter' && c[3]).length, 4);
  assert.equal(calls.filter(c => c[0] === 'wait').reduce((total, c) => total + c[1], 0), 12000);
  assert.equal(calls.at(-1)[0], 'capture');
});

for (const options of [{failedReconnects: 3}, {failUpload: true}, {cancelPrompt: true}]) {
  test(`Failed or cancelled setup never starts measurement: ${JSON.stringify(options)}`, async () => {
    const {calls, context} = setup(options);
    await vm.runInContext('startOneHubCapture()', context);
    assert.equal(calls.some(c => c[0] === 'capture'), false);
    assert.deepEqual(calls.at(-2), ['hub', 'ykushxs', 'XS123', 1, false]);
    assert.deepEqual(calls.at(-1), ['locked', false]);
  });
}

test('STOP during upload waits for completion, disables USB and skips measurement', async () => {
  const {calls, context} = setup();
  vm.runInContext(`window.pywebview.api.capture_status = async () => {
    stopOneHubPreparation();
    return {cursor: 0, lines: [], running: false, returncode: 0};
  };`, context);
  await vm.runInContext('startOneHubCapture()', context);
  assert.equal(calls.some(c => c[0] === 'capture'), false);
  assert.deepEqual(calls.at(-2), ['hub', 'ykushxs', 'XS123', 1, false]);
  assert.deepEqual(calls.at(-1), ['locked', false]);
});
