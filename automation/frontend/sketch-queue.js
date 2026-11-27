// Desktop queues retain native paths; browser/demo queues retain local File objects.
const sketchQueues = new Map();
const sketchQueueViews = new Map();
function initializeSketchQueues() {
  document.querySelectorAll('.dut').forEach((card, index) => {
    const files = [];
    sketchQueues.set(card, files);
    const panel = document.createElement('section');
    panel.className = 'sketch-queue';
    panel.setAttribute('aria-label', `DUT ${index+1} sketch queue preview`);
    const header = document.createElement('div'); header.className = 'sketch-queue-header';
    const title = document.createElement('strong'); title.textContent = 'Sketch queue';
    const badge = document.createElement('span'); badge.textContent = 'Preview'; header.append(title, badge);
    const list = document.createElement('ol'); list.className = 'sketch-queue-list';
    const empty = document.createElement('p'); empty.className = 'sketch-queue-empty'; empty.textContent = 'No sketches queued.';
    const picker = document.createElement('input');
    picker.type = 'file'; picker.accept = '.ino'; picker.multiple = true; picker.hidden = true; picker.dataset.queuePicker = '';
    const actions = document.createElement('div'); actions.className = 'sketch-queue-actions';
    const note = document.createElement('p'); note.className = 'sketch-queue-note';
    note.textContent = 'Preview only. RUN uses the single Arduino sketch selected on the DUT.';
    const locked = () => typeof isRunning !== 'undefined' && isRunning;
    function button(text, label, action) {
      const item = document.createElement('button'); item.type = 'button'; item.textContent = text;
      item.setAttribute('aria-label', label);
      item.addEventListener('click', () => { if (!locked()) action(); });
      return item;
    }
    function render() {
      list.replaceChildren(); empty.hidden = files.length > 0;
      title.textContent = `Sketch queue (${files.length})`;
      files.forEach((file, position) => {
        const row = document.createElement('li'); row.className = 'sketch-queue-row';
        const order = document.createElement('span'); order.className = 'sketch-queue-order'; order.textContent = `${position+1}.`;
        const name = document.createElement('span'); name.className = 'sketch-queue-name'; name.textContent = file.name; name.title = file.name;
        const move = delta => { [files[position], files[position+delta]] = [files[position+delta], files[position]]; render(); };
        const up = button('↑', `Move ${file.name} up`, () => move(-1)); up.disabled = position === 0;
        const down = button('↓', `Move ${file.name} down`, () => move(1)); down.disabled = position === files.length-1;
        row.append(order, name, up, down, button('×', `Remove ${file.name}`, () => { files.splice(position, 1); render(); }));
        list.append(row);
      });
      clear.disabled = files.length === 0;
    }
    const add = button('Add sketches…', `Add sketches for DUT ${index+1}`, async () => {
      if (typeof desktopReady === 'undefined' || !desktopReady) {picker.click();return;}
      try {
        const paths = await window.pywebview.api.pick_sketches();
        files.push(...paths.map(path=>({name:path.split(/[\\/]/).pop(),path})));
        render();
      } catch(error) {
        document.querySelector('#status').classList.add('error');
        document.querySelector('#status').textContent=`File selection failed: ${error.message||error}`;
      }
    });
    const clear = button('Clear', `Clear DUT ${index+1} sketch queue`, () => { files.length = 0; render(); });
    picker.addEventListener('change', () => {
      if (locked()) return;
      files.push(...Array.from(picker.files).filter(file => file.name.toLowerCase().endsWith('.ino')));
      picker.value = ''; render();
    });
    sketchQueueViews.set(card, {list, note, badge});
    actions.append(add, clear); panel.append(header, empty, list, actions, picker, note); card.append(panel); render();
  });
}

initializeSketchQueues();

document.querySelector('#run-queue').addEventListener('click', () => {
  if (typeof desktopReady !== 'undefined' && desktopReady) startSketchQueueCapture();
  else startSketchQueuePreview();
});
window.addEventListener('pywebviewready',()=>{
  if(typeof window.pywebview?.api?.pick_sketches!=='function') return;
  for(const view of sketchQueueViews.values()) {
    view.badge.textContent='Queue';
    view.note.textContent='Run queue uses these sketches in order. Missing steps are skipped.';
  }
});
