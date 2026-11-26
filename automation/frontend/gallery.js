// Existing results and newly completed measurements share the same gallery.
function filterResults() {
  const query = document.querySelector('#results-search').value.trim().toLowerCase();
  const cards = [...document.querySelectorAll('#results-gallery .result-session')];
  let matches = 0;
  cards.forEach(card => {
    card.hidden = !card.dataset.name.includes(query);
    if (!card.hidden) matches++;
  });
  document.querySelectorAll('#results-gallery .result-day').forEach(group => {
    group.hidden = ![...group.querySelectorAll('.result-session')].some(card => !card.hidden);
  });
  document.querySelector('#results-matches').textContent = query ? `${matches} of ${cards.length} result sets` : '';
}

document.querySelector('#results-search').addEventListener('input', filterResults);

async function loadResultPreview(image) {
  try { image.src = await window.pywebview.api.result_preview(image.dataset.path); }
  catch (error) { image.alt += ` (preview unavailable: ${error.message || error})`; }
}

const resultsPreviewObserver = new IntersectionObserver(entries => {
  for (const entry of entries) {
    if (!entry.isIntersecting) continue;
    const image = entry.target;
    resultsPreviewObserver.unobserve(image);
    loadResultPreview(image);
  }
}, {rootMargin: '400px'});

async function refreshResults() {
  if (!desktopReady || typeof window.pywebview?.api?.list_results !== 'function') return;
  const note = document.querySelector('#results-note');
  try {
    const sessions = await window.pywebview.api.list_results();
    const available = new Set(sessions.map(session => session.name));
    for (const name of comparisonSelection) if (!available.has(name)) comparisonSelection.delete(name);
    resultsPreviewObserver.disconnect();
    const groups = new Map();
    sessions.forEach(session => {
      if (!groups.has(session.date)) {
        const group = document.createElement('section');
        group.className = 'result-day';
        const heading = document.createElement('h3');
        heading.textContent = session.date;
        group.append(heading);
        groups.set(session.date, group);
      }
      const card = document.createElement('details');
      card.className = 'result-session';
      card.dataset.name = `${session.name} ${session.date}`.toLowerCase();
      const title = document.createElement('summary');
      title.append(comparisonCheckbox(session.name), document.createTextNode(session.name === '.' ? 'results' : session.name));
      const plots = document.createElement('div');
      plots.className = 'result-plots';
      for (const plot of session.plots) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'result-preview';
        button.title = `Open ${plot.path}`;
        const image = document.createElement('img');
        image.dataset.path = plot.preview;
        image.alt = `${session.name}: ${plot.label}`;
        resultsPreviewObserver.observe(image);
        const caption = document.createElement('span');
        caption.textContent = plot.label;
        button.append(image, caption);
        button.addEventListener('click', async () => {
          try { await window.pywebview.api.open_result(plot.path); }
          catch (error) { note.textContent = `Could not open plot: ${error.message || error}`; }
        });
        plots.append(button);
      }
      card.append(title, plots);
      groups.get(session.date).append(card);
    });
    document.querySelector('#results-gallery').replaceChildren(...groups.values());
    filterResults();
    updateComparisonSelection();
    note.textContent = sessions.length
      ? `${sessions.length} result sets · newest first. Click a preview to open the full plot (SVG when available).`
      : 'No English summary plots in results yet.';
  } catch (error) {
    note.textContent = `Could not load results: ${error.message || error}`;
  }
}
