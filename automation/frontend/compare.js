const comparisonSelection = new Set();

function comparisonCheckbox(name) {
  const checkbox = document.createElement('input');
  checkbox.type = 'checkbox'; checkbox.className = 'compare-select'; checkbox.checked = comparisonSelection.has(name);
  checkbox.setAttribute('aria-label', `Select ${name} for comparison`);
  checkbox.addEventListener('click', event => event.stopPropagation());
  checkbox.addEventListener('change', () => {
    if (checkbox.checked) comparisonSelection.add(name); else comparisonSelection.delete(name);
    updateComparisonSelection();
  });
  return checkbox;
}

function updateComparisonSelection() {
  const button = document.querySelector('#compare-results');
  button.textContent = `Compare selected (${comparisonSelection.size})`;
  button.disabled = comparisonSelection.size < 2 || isRunning;
}

document.querySelector('#compare-results').addEventListener('click', async event => {
  const button = event.currentTarget; button.disabled = true;
  const message = document.querySelector('#comparison-status');
  message.textContent = 'Generating comparison from saved samples…';
  try {
    await window.pywebview.api.compare_results([...comparisonSelection]);
    message.textContent = 'Comparison opened in a separate window.';
  } catch (error) { message.textContent = `Could not compare results: ${error.message || error}`; }
  finally { updateComparisonSelection(); }
});
