const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

test('HIL GUI exports active DUT fields and physical mappings to the backend', () => {
  const fields = {'hub-model': 'ykush3', 'hub-serial': 'HUB123', 'relay-model': 'numato',
    'relay-port': 'COM19', 'dut1-profile': 'nodemcu', 'dut1-port': 'COM22'};
  let request;
  const context = vm.createContext({
    document: {querySelector(selector) {
      return selector === '#dut1-sketch' ? {dataset: {path: 'C:/sketches/example.ino'}}
        : {value: fields[selector.slice(1)]};
    }},
    standaloneConfiguration: () => ({name: 'energy_test', controller: 'C:/control.py'}),
    relaySwitches: [{hidden: false, dataset: {channel: '3'}}, {hidden: true}],
    hub2Switches: [{dataset: {port: '3'}}],
    hubConfigured: () => true,
    startStandaloneCapture(...args) {request = args;},
  });
  vm.runInContext(fs.readFileSync('automation/frontend/hil.js', 'utf8'), context);
  vm.runInContext('startHilCapture()', context);
  assert.equal(request[2], 'start_hil');
  assert.equal(request[1].name, 'energy_test');
  assert.equal(request[1].boards.length, 1);
  assert.equal(request[1].boards[0].relay, 3);
  assert.equal(request[1].boards[0].ykush_usb_port, 3);
  assert.equal(request[1].boards[0].sketch, 'C:/sketches/example.ino');
});
