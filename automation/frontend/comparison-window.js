try { document.documentElement.dataset.theme = localStorage.getItem('hil-theme') || 'dark'; } catch (_) {}

window.addEventListener('pywebviewready', async () => {
  const message = document.querySelector('#message');
  try {
    const result = await window.pywebview.api.get_comparison();
    document.querySelector('#traces').src = result.images.comparison_traces;
    document.querySelector('#statistics').src = result.images.comparison_statistics;
    for (const row of result.rows) {
      const tr = document.createElement('tr');
      const title = document.createElement('td');
      const color = document.createElement('span'); color.className = 'color';
      color.style.background = `rgb(${row.color.slice(0,3).map(value=>Math.round(value*255)).join(',')})`;
      title.append(color, document.createTextNode(`${row.id} · ${row.name}`)); tr.append(title);
      for (const value of [row.repeats, row.seconds, row.voltage, row.mean_mA.toFixed(4),
          row.sd_mA === null ? 'N/A (n=1)' : row.sd_mA.toFixed(4), row.energy_J.toFixed(6)]) {
        const cell = document.createElement('td'); cell.textContent = value; tr.append(cell);
      }
      document.querySelector('#summary').append(tr);
    }
    const excluded = result.rows.reduce((sum,row)=>sum+row.excluded,0);
    document.querySelector('#sd-note').hidden = !result.rows.some(row => row.sd_mA === null);
    message.textContent = `${result.rows.length} sessions · ${excluded} invalid repeats excluded. Save exports both figures as PNG and SVG, plus summary.json.`;
    document.querySelector('#save').disabled = false;
  } catch (error) { message.textContent = `Comparison failed: ${error.message || error}`; }
});

document.querySelector('#save').addEventListener('click', async event => {
  const button = event.currentTarget; button.disabled = true;
  try {
    const directory = await window.pywebview.api.save_figures();
    if (directory) document.querySelector('#message').textContent = `Saved to ${directory}`;
  } catch (error) { document.querySelector('#message').textContent = `Save failed: ${error.message || error}`; }
  finally { button.disabled = false; }
});
