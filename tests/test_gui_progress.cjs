const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup() {
  const fields = {};
  const button = (dataset, serial) => ({dataset, disabled: true, attributes: {},
    setAttribute(name, value) {this.attributes[name] = value;},
    querySelector() {return {};},
    closest() {return {querySelector() {return {value: serial};}};}});
  const relay = button({channel: '3'});
  const hub = button({port: '2'}, 'HUB123');
  const meter = [];
  const context = vm.createContext({
    document: {querySelector(selector) {return fields[selector] ||= {replaceChildren(...items) {this.items = items;}};}, createElement() {return {}; }},
    relaySwitches: [relay], hub1Switches: [], hub2Switches: [hub],
    displayMeterPower(value) {meter.push(value);}, updateConnectionFlows() {}, setInterval() {},
  });
  vm.runInContext(fs.readFileSync('automation/frontend/progress.js', 'utf8'), context);
  return {context, fields, relay, hub, meter};
}

test('Telemetry updates mapped switches while user controls remain disabled', () => {
  const {context, relay, hub, meter} = setup();
  vm.runInContext(`applyRunEvents({events: [
    {type:'relay', channel:3, enabled:true},
    {type:'hub', serial:'HUB123', port:2, enabled:false},
    {type:'meter_power', enabled:true}
  ]})`, context);
  assert.equal(relay.attributes['aria-pressed'], 'true');
  assert.equal(hub.attributes['aria-pressed'], 'false');
  assert.deepEqual(meter, [true]);
  assert.equal(relay.disabled, true);
  assert.equal(hub.disabled, true);
});

test('Progress counts completed calibrations/repeats and displays remaining programmed time', () => {
  const {context, fields} = setup();
  vm.runInContext(`beginRunProgress({name:'test', repeats:2, seconds:10, warmup_seconds:20});
    applyRunEvents({events:[
      {type:'capture_plan', name:'test'},
      {type:'warmup', state:'completed', elapsed:20},
      {type:'calibration', state:'completed', repeat:1},
      {type:'repeat', state:'completed', repeat:1}
    ]});`, context);
  assert.equal(fields['#run-count'].textContent, '3/6 stages done · 3 remaining');
  assert.equal(fields['#run-time'].textContent, 'Remaining programmed time: 0m 10s');
  assert.match(fields['#run-stage'].textContent, /Repeat 1\/2/);
  vm.runInContext(`finishRunProgress('Stopped')`, context);
  assert.equal(fields['#run-count'].textContent, '3/6 stages done · 3 remaining');
  assert.match(fields['#run-stage'].textContent, /Stopped/);
});

test('HIL retains done stages across boards and hardware events do not reset its timer', () => {
  const {context, fields} = setup();
  vm.runInContext(`beginRunProgress({repeats:1, seconds:10, warmup_seconds:0}, ['first','second'], true);
    applyRunEvents({events:[
      {type:'upload', name:'first', state:'completed'},
      {type:'capture_plan', name:'first'}, {type:'warmup', state:'completed', elapsed:0},
      {type:'calibration', state:'completed', repeat:1},
      {type:'repeat', state:'completed', repeat:1}, {type:'report', state:'completed'},
      {type:'capture_plan', name:'second'}, {type:'repeat', state:'started', repeat:1, elapsed:0}
    ]});`, context);
  const timer = vm.runInContext('runProgress.clock', context);
  vm.runInContext(`applyRunEvents({events:[{type:'meter_power', enabled:true}]})`, context);
  assert.equal(vm.runInContext('runProgress.clock', context), timer);
  assert.equal(fields['#run-count'].textContent, '5/10 stages done · 5 remaining');
  assert.match(fields['#run-done'].items[0].textContent, /Report done/);
});
