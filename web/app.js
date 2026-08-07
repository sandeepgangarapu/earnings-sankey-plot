import {
  buildNativeShareData,
  buildShareMetadata,
  buildSocialShareUrls,
  buildStandaloneHtml,
  copyText,
  selectResultMode,
  serializeStatement,
  statementFilename,
} from './result-actions.mjs';

const form = document.querySelector('#generator-form');
const sampleButton = document.querySelector('#sample-button');
const emptyState = document.querySelector('#empty-state');
const loading = document.querySelector('#loading');
const errorBox = document.querySelector('#error');
const chartShell = document.querySelector('#chart-shell');
const resultViews = document.querySelector('#result-views');
const toolbar = document.querySelector('#result-toolbar');
const resultMeta = document.querySelector('#result-meta');
const sourceLink = document.querySelector('#source-link');
const notesPanel = document.querySelector('#notes-panel');
const notesList = document.querySelector('#notes-list');
const svgSource = document.querySelector('#svg-source');
const jsonSource = document.querySelector('#json-source');
const modeTabs = document.querySelectorAll('[data-result-mode]');
const resultPanels = document.querySelectorAll('[data-result-panel]');
const shareControl = document.querySelector('.share-control');
const shareButton = document.querySelector('#share-button');
const shareMenu = document.querySelector('#share-menu');
const nativeShare = document.querySelector('#native-share');
const actionStatus = document.querySelector('#action-status');
const state = { result: null, mode: 'chart', feedbackTimer: null };

function setBusy(isBusy) {
  form.querySelectorAll('button').forEach((button) => { button.disabled = isBusy; });
  loading.hidden = !isBusy;
  if (isBusy) {
    emptyState.hidden = true;
    resultViews.hidden = true;
    toolbar.hidden = true;
    notesPanel.hidden = true;
    errorBox.hidden = true;
  }
}

function showError(message) {
  setBusy(false);
  errorBox.textContent = message;
  errorBox.hidden = false;
  resultViews.hidden = true;
  toolbar.hidden = true;
}

function closeShareMenu({ restoreFocus = false } = {}) {
  const wasOpen = !shareMenu.hidden;
  shareMenu.hidden = true;
  shareButton.setAttribute('aria-expanded', 'false');
  if (restoreFocus && wasOpen) shareButton.focus();
}

function activateMode(mode, { focus = false } = {}) {
  state.mode = selectResultMode(mode, modeTabs, resultPanels);
  if (state.mode !== 'chart') closeShareMenu();
  if (focus) document.querySelector(`[data-result-mode="${state.mode}"]`)?.focus();
}

function configureShare(statement) {
  const metadata = buildShareMetadata(statement, window.location.href);
  const urls = buildSocialShareUrls(metadata);
  document.querySelector('#share-linkedin').href = urls.linkedin;
  document.querySelector('#share-x').href = urls.x;
  document.querySelector('#share-facebook').href = urls.facebook;
  nativeShare.hidden = typeof navigator.share !== 'function';
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
  clearTimeout(state.feedbackTimer);
  document.querySelectorAll('[data-copy-label]').forEach((item) => {
    item.textContent = item.dataset.copyLabel;
    delete item.dataset.copyLabel;
  });
  setBusy(false);
  errorBox.hidden = true;
  emptyState.hidden = true;
  chartShell.innerHTML = result.svg;
  svgSource.textContent = result.svg;
  jsonSource.textContent = serializeStatement(result.statement);
  resultViews.hidden = false;
  toolbar.hidden = false;
  actionStatus.textContent = '';
  closeShareMenu();
  activateMode('chart');
  const statement = result.statement;
  resultMeta.textContent = `${statement.ticker} · ${statement.period} FY${statement.fiscal_year}${statement.filed_date ? ` · filed ${statement.filed_date}` : ''}`;
  const source = safeSourceUrl(statement.source_url);
  sourceLink.hidden = !source;
  if (source) sourceLink.href = source;
  configureShare(statement);
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

function download(content, type, name) {
  const blob = new Blob([content], { type });
  const anchor = document.createElement('a');
  anchor.href = URL.createObjectURL(blob);
  anchor.download = name;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(anchor.href), 0);
}

function downloadSvg() {
  if (state.result) download(state.result.svg, 'image/svg+xml', statementFilename(state.result.statement, 'svg'));
}

document.querySelector('#download-svg-chart').addEventListener('click', downloadSvg);
document.querySelector('#download-svg-source').addEventListener('click', downloadSvg);
document.querySelector('#download-json').addEventListener('click', () => {
  if (state.result) download(serializeStatement(state.result.statement), 'application/json', statementFilename(state.result.statement, 'json'));
});
document.querySelector('#download-html').addEventListener('click', () => {
  if (!state.result) return;
  download(buildStandaloneHtml(state.result), 'text/html', statementFilename(state.result.statement, 'html'));
});

function announce(message) {
  actionStatus.textContent = '';
  requestAnimationFrame(() => { actionStatus.textContent = message; });
}

async function handleCopy(button, content, kind) {
  if (!state.result) return;
  const resultAtStart = state.result;
  let copied = false;
  try {
    copied = await copyText(content(), { clipboard: navigator.clipboard, document });
  } catch {
    // Unexpected browser API failures use the same truthful failure feedback.
  }
  if (state.result !== resultAtStart) return;
  clearTimeout(state.feedbackTimer);
  document.querySelectorAll('[data-copy-label]').forEach((item) => {
    item.textContent = item.dataset.copyLabel;
    delete item.dataset.copyLabel;
  });
  if (!copied) {
    announce(`Couldn’t copy the ${kind}. Select it in the source view and copy manually.`);
    return;
  }
  button.dataset.copyLabel = button.textContent;
  button.textContent = 'Copied';
  announce(`${kind} copied to the clipboard.`);
  state.feedbackTimer = setTimeout(() => {
    if (button.dataset.copyLabel) {
      button.textContent = button.dataset.copyLabel;
      delete button.dataset.copyLabel;
    }
  }, 1800);
}

document.querySelector('#copy-svg-chart').addEventListener('click', (event) => {
  handleCopy(event.currentTarget, () => state.result.svg, 'SVG');
});
document.querySelector('#copy-svg-source').addEventListener('click', (event) => {
  handleCopy(event.currentTarget, () => state.result.svg, 'SVG');
});
document.querySelector('#copy-json').addEventListener('click', (event) => {
  handleCopy(event.currentTarget, () => serializeStatement(state.result.statement), 'JSON');
});

modeTabs.forEach((tab) => {
  tab.addEventListener('click', () => activateMode(tab.dataset.resultMode));
  tab.addEventListener('keydown', (event) => {
    const tabs = Array.from(modeTabs);
    const currentIndex = tabs.indexOf(tab);
    let nextIndex = null;
    if (event.key === 'ArrowRight') nextIndex = (currentIndex + 1) % tabs.length;
    if (event.key === 'ArrowLeft') nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    if (event.key === 'Home') nextIndex = 0;
    if (event.key === 'End') nextIndex = tabs.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    activateMode(tabs[nextIndex].dataset.resultMode, { focus: true });
  });
});

shareButton.addEventListener('click', () => {
  const willOpen = shareMenu.hidden;
  shareMenu.hidden = !willOpen;
  shareButton.setAttribute('aria-expanded', String(willOpen));
  if (willOpen) {
    const firstAction = nativeShare.hidden ? document.querySelector('#share-linkedin') : nativeShare;
    firstAction.focus();
  }
});

document.querySelectorAll('#share-menu a').forEach((link) => {
  link.addEventListener('click', () => closeShareMenu());
});

nativeShare.addEventListener('click', async () => {
  if (!state.result || typeof navigator.share !== 'function') return;
  closeShareMenu();
  try {
    const metadata = buildShareMetadata(state.result.statement, window.location.href);
    const shareData = buildNativeShareData(
      metadata,
      state.result.svg,
      statementFilename(state.result.statement, 'svg'),
      {
        File: typeof File === 'function' ? File : null,
        canShare: typeof navigator.canShare === 'function' ? navigator.canShare.bind(navigator) : null,
      },
    );
    await navigator.share(shareData);
    announce('Shared.');
  } catch (error) {
    if (error.name !== 'AbortError') announce('Sharing isn’t available right now.');
  }
});

document.addEventListener('click', (event) => {
  if (!shareMenu.hidden && !shareControl.contains(event.target)) closeShareMenu();
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !shareMenu.hidden) closeShareMenu({ restoreFocus: true });
});
