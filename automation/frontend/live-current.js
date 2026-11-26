// Local canvas preview: time/current bins, independent of the full sample files.
const liveCurrent = {points: [], name: '', repeat: 0, demo: null, hover: null};

function resetLiveCurrent(name = '', repeat = 0) {
  document.querySelector('.live-current').hidden = true;
  liveCurrent.points = [];
  liveCurrent.hover = null;
  liveCurrent.name = name;
  liveCurrent.repeat = repeat;
  document.querySelector('#live-current-label').textContent = name
    ? `${name} · Repeat ${repeat || '—'} · waiting for samples`
    : 'Waiting for acquisition';
  drawLiveCurrent();
}

function updateLiveCurrent(event) {
  if (event.type === 'capture_plan') resetLiveCurrent(event.name);
  if (event.type === 'repeat' && event.state === 'started') resetLiveCurrent(liveCurrent.name, event.repeat);
  if (event.type !== 'current_samples') return;
  if (liveCurrent.name !== event.name || liveCurrent.repeat !== event.repeat) resetLiveCurrent(event.name, event.repeat);
  liveCurrent.points.push(...event.points);
  const end = liveCurrent.points.at(-1)?.[0] || 0;
  liveCurrent.points = liveCurrent.points.filter(point => point[0] >= end - 30).slice(-1000);
  const latest = liveCurrent.points.at(-1);
  if (latest) document.querySelector('.live-current').hidden = false;
  if (latest) document.querySelector('#live-current-label').textContent =
    `${event.name} · Repeat ${event.repeat} · ${latest[0].toFixed(1)} s · ${latest[1].toFixed(3)} mA (bin mean)`;
  drawLiveCurrent();
}

function drawLiveCurrent() {
  const canvas = document.querySelector('#live-current-canvas');
  const width = canvas.clientWidth || 800, height = 280;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const ctx = canvas.getContext('2d');
  ctx.scale(ratio, ratio);
  const dark = document.documentElement.dataset.theme === 'dark';
  const ink = dark ? '#c5d5e8' : '#34465c';
  const line = dark ? '#63e2d3' : '#087e80';
  const area = {left: 66, right: width - 18, top: 22, bottom: height - 38};
  const points = liveCurrent.points;
  const last = points.at(-1)?.[0] || 0;
  const start = Math.max(0, last - 30), end = Math.max(30, last);
  const maximum = Math.max(.01, ...points.map(point => point[3])) * 1.12;
  const x = time => area.left + (time - start) / (end - start) * (area.right - area.left);
  const y = current => area.bottom - current / maximum * (area.bottom - area.top);
  ctx.font = '11px Consolas, monospace';
  ctx.lineWidth = 1;
  for (let step = 0; step <= 4; step++) {
    const value = maximum * step / 4;
    ctx.strokeStyle = dark ? '#344359' : '#d9e1eb';
    ctx.beginPath(); ctx.moveTo(area.left, y(value)); ctx.lineTo(area.right, y(value)); ctx.stroke();
    ctx.fillStyle = ink; ctx.textAlign = 'right';
    ctx.fillText(value.toFixed(maximum < 1 ? 3 : 1), area.left - 8, y(value) + 4);
    ctx.textAlign = 'center';
    ctx.fillText((start + (end - start) * step / 4).toFixed(1), x(start + (end - start) * step / 4), height - 18);
  }
  ctx.fillStyle = ink; ctx.textAlign = 'left'; ctx.fillText('Current [mA]', area.left, 12);
  ctx.textAlign = 'right'; ctx.fillText('Time [s]', area.right, height - 3);
  if (!points.length) {
    ctx.textAlign = 'center'; ctx.fillText('Waiting for current samples', width / 2, height / 2);
    return;
  }
  // Envelope preserves short peaks that are absent from the mean line.
  ctx.fillStyle = dark ? '#e6ab4155' : '#d48c2040';
  ctx.beginPath();
  points.forEach((point, index) => index ? ctx.lineTo(x(point[0]), y(point[3])) : ctx.moveTo(x(point[0]), y(point[3])));
  [...points].reverse().forEach(point => ctx.lineTo(x(point[0]), y(point[2])));
  ctx.closePath(); ctx.fill();
  ctx.strokeStyle = line; ctx.lineWidth = 1.7;
  ctx.beginPath();
  points.forEach((point, index) => index ? ctx.lineTo(x(point[0]), y(point[1])) : ctx.moveTo(x(point[0]), y(point[1])));
  ctx.stroke();
  if (points.length === 1) {ctx.fillStyle = line; ctx.beginPath(); ctx.arc(x(points[0][0]), y(points[0][1]), 2, 0, Math.PI * 2); ctx.fill();}
  if (liveCurrent.hover) {
    const pointerX = liveCurrent.hover.x * width, pointerY = liveCurrent.hover.y * height;
    if (pointerX < area.left || pointerX > area.right || pointerY < area.top || pointerY > area.bottom) return;
    const point = points.reduce((nearest, item) => Math.abs(x(item[0]) - pointerX) < Math.abs(x(nearest[0]) - pointerX) ? item : nearest);
    const px = x(point[0]), py = y(point[1]);
    if (Math.abs(px - pointerX) > 15) return;
    ctx.strokeStyle = ink; ctx.lineWidth = 1; ctx.setLineDash([3, 4]);
    ctx.beginPath(); ctx.moveTo(px, area.top); ctx.lineTo(px, area.bottom); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = line; ctx.strokeStyle = dark ? '#202c3c' : '#fff'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(px, py, 4, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    const boxWidth = Math.min(220, width - 12), boxHeight = 78;
    const bx = Math.max(6, Math.min(width - boxWidth - 6, px + 12));
    const by = Math.max(area.top + 4, Math.min(area.bottom - boxHeight, py - boxHeight - 12));
    ctx.fillStyle = dark ? '#101722' : '#fff'; ctx.strokeStyle = ink; ctx.lineWidth = 1;
    ctx.fillRect(bx, by, boxWidth, boxHeight); ctx.strokeRect(bx, by, boxWidth, boxHeight);
    ctx.fillStyle = ink; ctx.textAlign = 'left';
    [`Time: ${point[0].toFixed(3)} s`, `Mean: ${point[1].toFixed(3)} mA`,
      `Min:  ${point[2].toFixed(3)} mA`, `Max:  ${point[3].toFixed(3)} mA`]
      .forEach((text, index) => ctx.fillText(text, bx + 10, by + 16 + index * 16));
  }
}

function stopLiveDemo() {
  if (liveCurrent.demo) {
    clearInterval(liveCurrent.demo);
    liveCurrent.demo = null;
    document.querySelector('#live-current-demo').textContent = 'Demo preview';
    document.querySelector('#live-current-label').textContent = 'Demo preview stopped · simulated data';
  }
}

function toggleLiveDemo() {
  if (typeof demoMode !== 'undefined' && (!demoMode || desktopReady)) return;
  const button = document.querySelector('#live-current-demo');
  if (liveCurrent.demo) {
    stopLiveDemo();
    return;
  }
  resetLiveCurrent('DEMO — simulated current', 1);
  document.querySelector('.live-current').hidden = false;
  button.textContent = 'Stop demo preview';
  let time = 0;
  liveCurrent.demo = setInterval(() => {
    const points = [];
    for (let index = 0; index < 10; index++) {
      const mean = Math.floor(time / 5) % 2 ? .2 : 20 + Math.sin(time * 3);
      points.push([time, mean, Math.max(0, mean - .15), mean + (Math.floor(time * 20) % 41 === 0 ? 55 : .25)]);
      time += .05;
    }
    updateLiveCurrent({type: 'current_samples', name: 'DEMO — simulated current', repeat: 1, points});
  }, 500);
}

document.querySelector('#live-current-demo').addEventListener('click', toggleLiveDemo);
document.querySelector('#live-current-canvas').addEventListener('pointermove', event => {
  const rect = event.currentTarget.getBoundingClientRect();
  liveCurrent.hover = {x: (event.clientX - rect.left) / rect.width, y: (event.clientY - rect.top) / rect.height};
  drawLiveCurrent();
});
document.querySelector('#live-current-canvas').addEventListener('pointerleave', () => {
  liveCurrent.hover = null;
  drawLiveCurrent();
});
new ResizeObserver(drawLiveCurrent).observe(document.querySelector('#live-current-canvas'));
new MutationObserver(drawLiveCurrent).observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
