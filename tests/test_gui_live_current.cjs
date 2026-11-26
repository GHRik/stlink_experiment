const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

function setup() {
  const labels = [];
  const handlers = {};
  const drawing = new Proxy({}, {get(target, key) {return target[key] || (() => {});}});
  drawing.fillText = text => labels.push(text);
  const fields = {'#live-current-canvas': {clientWidth: 800, getContext: () => drawing,
    addEventListener(event, handler) {handlers[event] = handler;},
    getBoundingClientRect() {return {left: 0, top: 0, width: 800, height: 280};}},
    '#live-current-label': {}, '#live-current-demo': {addEventListener() {}}, '.live-current': {hidden: true}};
  const context = vm.createContext({
    document: {querySelector: selector => fields[selector], documentElement: {dataset: {}}},
    window: {devicePixelRatio: 1},
    ResizeObserver: class {observe() {}}, MutationObserver: class {observe() {}},
    setInterval: () => 1, clearInterval() {},
  });
  vm.runInContext(fs.readFileSync('automation/frontend/live-current.js', 'utf8'), context);
  return {context, fields, labels, handlers};
}

test('Live chart retains only the last 30 seconds and resets between repeats', () => {
  const {context, fields} = setup();
  vm.runInContext(`updateLiveCurrent({type:'current_samples', name:'test', repeat:1,
    points:Array.from({length:2000}, (_, i) => [i*.05, 10, .1, 150])})`, context);
  assert.ok(vm.runInContext('liveCurrent.points.length <= 601', context));
  assert.match(fields['#live-current-label'].textContent, /Repeat 1/);
  vm.runInContext(`updateLiveCurrent({type:'repeat', state:'started', repeat:2})`, context);
  assert.equal(vm.runInContext('liveCurrent.points.length', context), 0);
  assert.match(fields['#live-current-label'].textContent, /Repeat 2/);
});

test('Hover selects the nearest visible bin and shows its time, mean and extrema', () => {
  const {context, fields, labels, handlers} = setup();
  vm.runInContext(`updateLiveCurrent({type:'current_samples', name:'test', repeat:1,
    points:[[10,20,5,150],[20,30,10,40]]})`, context);
  labels.length = 0;
  handlers.pointermove({currentTarget: fields['#live-current-canvas'], clientX: 66 + 716 / 3, clientY: 100});
  assert.ok(labels.includes('Time: 10.000 s'));
  assert.ok(labels.includes('Mean: 20.000 mA'));
  assert.ok(labels.includes('Min:  5.000 mA'));
  assert.ok(labels.includes('Max:  150.000 mA'));
  handlers.pointerleave();
  assert.equal(vm.runInContext('liveCurrent.hover', context), null);
});

test('Real samples cannot be mixed across boards and demo is explicitly labelled', () => {
  const {context, fields} = setup();
  vm.runInContext(`toggleLiveDemo()`, context);
  assert.match(fields['#live-current-label'].textContent, /DEMO/);
  vm.runInContext(`stopLiveDemo(); resetLiveCurrent();
    updateLiveCurrent({type:'current_samples', name:'boardA', repeat:1, points:[[0,1,0,2]]});
    updateLiveCurrent({type:'current_samples', name:'boardB', repeat:1, points:[[0,10,9,11]]});`, context);
  assert.equal(vm.runInContext('liveCurrent.points.length', context), 1);
  assert.equal(vm.runInContext('liveCurrent.points[0][1]', context), 10);
  assert.match(fields['#live-current-label'].textContent, /boardB/);
});
