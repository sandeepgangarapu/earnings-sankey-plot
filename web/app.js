const form = document.querySelector('#generator-form');
const sampleButton = document.querySelector('#sample-button');
const emptyState = document.querySelector('#empty-state');
const loading = document.querySelector('#loading');
const errorBox = document.querySelector('#error');
const chartShell = document.querySelector('#chart-shell');
const toolbar = document.querySelector('#result-toolbar');
const resultMeta = document.querySelector('#result-meta');
const sourceLink = document.querySelector('#source-link');
const notesPanel = document.querySelector('#notes-panel');
const notesList = document.querySelector('#notes-list');
const state = { result: null };

function setBusy(isBusy) {
  form.querySelectorAll('button').forEach((button) => { button.disabled = isBusy; });
  loading.hidden = !isBusy;
  if (isBusy) {
    emptyState.hidden = true;
    chartShell.hidden = true;
    toolbar.hidden = true;
    notesPanel.hidden = true;
    errorBox.hidden = true;
  }
}

function showError(message) {
  setBusy(false);
  errorBox.textContent = message;
  errorBox.hidden = false;
  chartShell.hidden = true;
  toolbar.hidden = true;
}

function safeSourceUrl(value) {
  if (!value) return null;
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}

function showResult(result) {
  state.result = result;
  setBusy(false);
  errorBox.hidden = true;
  emptyState.hidden = true;
  chartShell.innerHTML = result.svg;
  chartShell.hidden = false;
  toolbar.hidden = false;
  const statement = result.statement;
  resultMeta.textContent = `${statement.ticker} · ${statement.period} FY${statement.fiscal_year}${statement.filed_date ? ` · filed ${statement.filed_date}` : ''}`;
  const source = safeSourceUrl(statement.source_url);
  sourceLink.hidden = !source;
  if (source) sourceLink.href = source;
  notesList.replaceChildren();
  (statement.notes || []).forEach((note) => {
    const item = document.createElement('li');
    item.textContent = note;
    notesList.append(item);
  });
  notesPanel.hidden = !statement.notes?.length;
}

async function parseResponse(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `Request failed with status ${response.status}.`);
  return payload;
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const overrideText = document.querySelector('#override').value.trim();
  let override = null;
  if (overrideText) {
    try { override = JSON.parse(overrideText); }
    catch { showError('The segment override is not valid JSON.'); return; }
  }
  const yearText = document.querySelector('#fiscal-year').value.trim();
  const request = {
    ticker: document.querySelector('#ticker').value.trim().toUpperCase(),
    fiscal_year: yearText ? Number(yearText) : null,
    period: document.querySelector('#period').value || null,
    user_agent: document.querySelector('#user-agent').value.trim(),
    override,
  };
  setBusy(true);
  try {
    const response = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    showResult(await parseResponse(response));
  } catch (error) { showError(error.message); }
});

sampleButton.addEventListener('click', async () => {
  setBusy(true);
  try {
    const response = await fetch('/api/sample');
    showResult(await parseResponse(response));
  } catch (error) { showError(error.message); }
});

function filename(extension) {
  const statement = state.result.statement;
  return `${statement.ticker.toLowerCase()}-${statement.fiscal_year}-${statement.period.toLowerCase()}-sankey.${extension}`;
}

function download(content, type, name) {
  const blob = new Blob([content], { type });
  const anchor = document.createElement('a');
  anchor.href = URL.createObjectURL(blob);
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(anchor.href);
}

document.querySelector('#download-svg').addEventListener('click', () => {
  if (state.result) download(state.result.svg, 'image/svg+xml', filename('svg'));
});
document.querySelector('#download-json').addEventListener('click', () => {
  if (state.result) download(`${JSON.stringify(state.result.statement, null, 2)}\n`, 'application/json', filename('json'));
});
document.querySelector('#download-html').addEventListener('click', () => {
  if (!state.result) return;
  const title = state.result.statement.company.replace(/[<>&"']/g, '');
  const documentText = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>${title} earnings Sankey</title><style>body{margin:0;background:#edf2ee;padding:24px}svg{width:100%;height:auto;background:#fbfcfa;border-radius:14px}</style></head><body>${state.result.svg}</body></html>`;
  download(documentText, 'text/html', filename('html'));
});
