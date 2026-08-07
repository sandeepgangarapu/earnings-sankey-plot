import {
  buildNativeShareData,
  buildShareMetadata,
  buildSocialShareUrls,
  buildStandaloneHtml,
  copyPngBlob,
  copyText,
  renderSvgToPng,
  selectResultMode,
  serializeStatement,
  statementFilename,
} from './result-actions.mjs';
import {
  fiscalYearChoices,
  formatCompany,
  moveCompanySelection,
  rankCompanyMatches,
  resolveCompanyTicker,
} from './company-search.mjs';

const form = document.querySelector('#generator-form');
const companyControl = document.querySelector('.company-combobox');
const companyInput = document.querySelector('#company-search');
const companyOptions = document.querySelector('#company-options');
const companyStatus = document.querySelector('#company-search-status');
const tickerInput = document.querySelector('#ticker');
const fiscalYear = document.querySelector('#fiscal-year');
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
const downloadControl = document.querySelector('.download-control');
const downloadButton = document.querySelector('#download-button');
const downloadMenu = document.querySelector('#download-menu');
const actionStatus = document.querySelector('#action-status');
const state = {
  result: null,
  mode: 'chart',
  feedbackTimer: null,
  copyImageOperation: 0,
  companies: null,
  companyPromise: null,
  companyLoadFailed: false,
  visibleCompanies: [],
  activeCompanyIndex: -1,
  selectedCompany: { ticker: 'GOOGL', name: 'Alphabet Inc.' },
};

function populateFiscalYears() {
  const defaultYear = 2026;
  const years = fiscalYearChoices(new Date().getFullYear());
  fiscalYear.replaceChildren();
  years.forEach((year) => {
    const option = document.createElement('option');
    option.value = String(year);
    option.textContent = String(year);
    fiscalYear.append(option);
  });
  fiscalYear.value = String(years.includes(defaultYear) ? defaultYear : new Date().getFullYear());
}

populateFiscalYears();

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

function closeDownloadMenu({ restoreFocus = false } = {}) {
  const wasOpen = !downloadMenu.hidden;
  downloadMenu.hidden = true;
  downloadButton.setAttribute('aria-expanded', 'false');
  if (restoreFocus && wasOpen) downloadButton.focus();
}

function activateMode(mode, { focus = false } = {}) {
  state.mode = selectResultMode(mode, modeTabs, resultPanels);
  if (state.mode !== 'chart') {
    closeShareMenu();
    closeDownloadMenu();
  }
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
  state.copyImageOperation += 1;
  clearTimeout(state.feedbackTimer);
  restoreCopyLabels();
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
  closeDownloadMenu();
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

function closeCompanyOptions() {
  companyOptions.hidden = true;
  companyInput.setAttribute('aria-expanded', 'false');
  companyInput.removeAttribute('aria-activedescendant');
  state.activeCompanyIndex = -1;
}

function setActiveCompany(index) {
  state.activeCompanyIndex = index;
  Array.from(companyOptions.children).forEach((option, optionIndex) => {
    option.setAttribute('aria-selected', String(optionIndex === index));
  });
  if (index < 0) {
    companyInput.removeAttribute('aria-activedescendant');
    return;
  }
  companyInput.setAttribute('aria-activedescendant', companyOptions.children[index].id);
}

function selectCompany(company) {
  state.selectedCompany = company;
  companyInput.value = formatCompany(company);
  tickerInput.value = company.ticker;
  companyStatus.textContent = `${company.name} selected.`;
  closeCompanyOptions();
}

function renderCompanyOptions() {
  if (!state.companies) return;
  if (state.selectedCompany && companyInput.value === formatCompany(state.selectedCompany)) {
    state.visibleCompanies = [];
    companyOptions.replaceChildren();
    closeCompanyOptions();
    companyStatus.textContent = `${state.selectedCompany.name} selected.`;
    return;
  }
  state.visibleCompanies = rankCompanyMatches(state.companies, companyInput.value);
  state.activeCompanyIndex = -1;
  companyOptions.replaceChildren();
  state.visibleCompanies.forEach((company, index) => {
    const option = document.createElement('button');
    option.type = 'button';
    option.id = `company-option-${index}`;
    option.className = 'company-option';
    option.dataset.ticker = company.ticker;
    option.setAttribute('role', 'option');
    option.setAttribute('aria-selected', 'false');

    const name = document.createElement('span');
    name.className = 'company-option-name';
    name.textContent = company.name;
    const ticker = document.createElement('span');
    ticker.className = 'company-option-ticker';
    ticker.textContent = company.ticker;
    option.append(name, ticker);
    option.addEventListener('click', () => selectCompany(company));
    option.addEventListener('mouseenter', () => setActiveCompany(index));
    companyOptions.append(option);
  });

  if (!state.visibleCompanies.length) {
    closeCompanyOptions();
    if (!state.companyLoadFailed) companyStatus.textContent = 'No matches. You can enter a ticker directly.';
    return;
  }
  companyOptions.hidden = false;
  companyInput.setAttribute('aria-expanded', 'true');
  companyStatus.textContent = `${state.visibleCompanies.length} matching companies.`;
}

async function loadCompanies() {
  if (state.companies) return state.companies;
  if (!state.companyPromise) {
    companyStatus.textContent = 'Loading companies…';
    state.companyPromise = fetch('/api/companies')
      .then(parseResponse)
      .then((companies) => {
        if (!Array.isArray(companies)) throw new Error('The company directory is unavailable.');
        state.companies = companies;
        return companies;
      })
      .catch(() => {
        state.companyLoadFailed = true;
        companyStatus.textContent = 'Company search is unavailable. Enter a ticker directly.';
        return [];
      });
  }
  return state.companyPromise;
}

async function refreshCompanyOptions() {
  await loadCompanies();
  renderCompanyOptions();
}

companyInput.addEventListener('focus', refreshCompanyOptions);
companyInput.addEventListener('input', async () => {
  state.selectedCompany = null;
  tickerInput.value = '';
  await refreshCompanyOptions();
});
companyInput.addEventListener('keydown', async (event) => {
  if (event.key === 'Escape') {
    closeCompanyOptions();
    return;
  }
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault();
    if (companyOptions.hidden) await refreshCompanyOptions();
    setActiveCompany(moveCompanySelection(
      state.activeCompanyIndex,
      event.key,
      state.visibleCompanies.length,
    ));
    return;
  }
  if (event.key === 'Enter' && !companyOptions.hidden && state.activeCompanyIndex >= 0) {
    event.preventDefault();
    selectCompany(state.visibleCompanies[state.activeCompanyIndex]);
  }
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const ticker = resolveCompanyTicker(companyInput.value, state.selectedCompany);
  if (!ticker) {
    showError('Select a matching company or enter a valid ticker.');
    return;
  }
  tickerInput.value = ticker;
  closeCompanyOptions();
  const yearText = fiscalYear.value.trim();
  const request = {
    ticker,
    fiscal_year: yearText ? Number(yearText) : null,
    period: document.querySelector('#period').value || null,
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

function download(content, type, name) {
  saveBlob(new Blob([content], { type }), name);
}

function saveBlob(blob, name) {
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
document.querySelector('#download-png').addEventListener('click', async () => {
  if (!state.result) return;
  const resultAtStart = state.result;
  closeDownloadMenu({ restoreFocus: true });
  announce('Preparing PNG…');
  try {
    const png = await renderSvgToPng(state.result.svg, {
      Blob,
      Image,
      document,
      URL,
    }, 2);
    if (state.result !== resultAtStart) return;
    saveBlob(png, statementFilename(state.result.statement, 'png'));
    announce('PNG downloaded.');
  } catch {
    if (state.result === resultAtStart) announce('The chart couldn’t be rendered as a PNG.');
  }
});

function announce(message) {
  actionStatus.textContent = '';
  requestAnimationFrame(() => { actionStatus.textContent = message; });
}

function restoreCopyLabels() {
  document.querySelectorAll('[data-copy-label]').forEach((item) => {
    item.textContent = item.dataset.copyLabel;
    delete item.dataset.copyLabel;
  });
}

function showCopiedFeedback(button, kind) {
  button.textContent = 'Copied';
  announce(`${kind} copied to the clipboard.`);
  state.feedbackTimer = setTimeout(() => restoreCopyLabels(), 1800);
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
  restoreCopyLabels();
  if (!copied) {
    announce(`Couldn’t copy the ${kind}. Select it in the source view and copy manually.`);
    return;
  }
  button.dataset.copyLabel = button.textContent;
  showCopiedFeedback(button, kind);
}

document.querySelector('#copy-image').addEventListener('click', async (event) => {
  if (!state.result) return;
  const button = event.currentTarget;
  const resultAtStart = state.result;
  const operation = ++state.copyImageOperation;
  const isCurrentOperation = () => state.result === resultAtStart && state.copyImageOperation === operation;
  clearTimeout(state.feedbackTimer);
  restoreCopyLabels();
  button.dataset.copyLabel = button.textContent;
  button.textContent = 'Copying…';
  try {
    const png = renderSvgToPng(state.result.svg, { Blob, Image, document, URL }, 2);
    png.catch(() => {});
    const copied = await copyPngBlob(png, {
      ClipboardItem: typeof ClipboardItem === 'function' ? ClipboardItem : null,
      clipboard: navigator.clipboard,
    });
    if (!isCurrentOperation()) return;
    if (copied) {
      showCopiedFeedback(button, 'Chart image');
      return;
    }
  } catch {
    // The action below reports the same useful fallback for render and permission failures.
  }
  if (!isCurrentOperation()) return;
  restoreCopyLabels();
  announce('Couldn’t copy the chart image. Use Download → Download PNG instead.');
});
document.querySelector('#copy-svg-source').addEventListener('click', (event) => {
  handleCopy(event.currentTarget, () => state.result.svg, 'SVG code');
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
  closeDownloadMenu();
  shareMenu.hidden = !willOpen;
  shareButton.setAttribute('aria-expanded', String(willOpen));
  if (willOpen) {
    const firstAction = nativeShare.hidden ? document.querySelector('#share-linkedin') : nativeShare;
    firstAction.focus();
  }
});

downloadButton.addEventListener('click', () => {
  const willOpen = downloadMenu.hidden;
  closeShareMenu();
  downloadMenu.hidden = !willOpen;
  downloadButton.setAttribute('aria-expanded', String(willOpen));
  if (willOpen) document.querySelector('#download-png').focus();
});

document.querySelectorAll('#download-menu button').forEach((item) => {
  item.addEventListener('click', () => closeDownloadMenu({ restoreFocus: true }));
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
  if (!companyOptions.hidden && !companyControl.contains(event.target)) closeCompanyOptions();
  if (!shareMenu.hidden && !shareControl.contains(event.target)) closeShareMenu();
  if (!downloadMenu.hidden && !downloadControl.contains(event.target)) closeDownloadMenu();
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !shareMenu.hidden) closeShareMenu({ restoreFocus: true });
  if (event.key === 'Escape' && !downloadMenu.hidden) closeDownloadMenu({ restoreFocus: true });
});
