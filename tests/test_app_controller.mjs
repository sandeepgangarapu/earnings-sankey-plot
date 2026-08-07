import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';


class FakeElement {
  constructor(id, text = '') {
    this.id = id;
    this.textContent = text;
    this.innerHTML = '';
    this.hidden = false;
    this.disabled = false;
    this.dataset = {};
    this.attributes = new Map();
    this.listeners = new Map();
    this.children = [];
    this.value = '';
    this.href = '';
    this.download = '';
    this.tabIndex = 0;
    this.clicked = false;
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) || [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  async emit(type, properties = {}) {
    const event = {
      currentTarget: this,
      target: this,
      preventDefault() {},
      ...properties,
    };
    for (const listener of this.listeners.get(type) || []) await listener(event);
  }

  setAttribute(name, value) { this.attributes.set(name, value); }
  focus() { globalThis.document.activeElement = this; }
  click() { this.clicked = true; }
  append(child) { this.children.push(child); }
  replaceChildren() { this.children = []; }
  remove() { this.removed = true; }
  select() {}
  contains(target) { return target === this || target?.shareOwner === this; }
  querySelectorAll() { return []; }
}


function statement(ticker) {
  return {
    company: `${ticker} Company`,
    ticker,
    fiscal_year: 2026,
    period: 'Q1',
    source_url: 'https://www.sec.gov/filing',
    notes: [],
  };
}


function result(ticker) {
  return { statement: statement(ticker), svg: `<svg><title>${ticker}</title></svg>` };
}


function createHarness() {
  const elements = new Map();
  const make = (id, text = '') => {
    const element = new FakeElement(id, text);
    elements.set(`#${id}`, element);
    return element;
  };

  const form = make('generator-form');
  const sampleButton = make('sample-button', 'View example');
  const modeTabs = ['chart', 'svg', 'json'].map((mode) => {
    const tab = make(`mode-${mode}`, mode.toUpperCase());
    tab.dataset.resultMode = mode;
    return tab;
  });
  const resultPanels = ['chart', 'svg', 'json'].map((mode) => {
    const panel = make(`${mode}-panel`);
    panel.dataset.resultPanel = mode;
    panel.hidden = mode !== 'chart';
    return panel;
  });

  const labels = {
    'copy-image': 'Copy image',
    'download-button': 'Download',
    'download-png': 'Download PNG',
    'download-svg-chart': 'Download SVG',
    'download-svg-source': 'Download SVG',
    'download-json': 'Download JSON',
    'download-html': 'Download HTML',
    'copy-svg-source': 'Copy SVG code',
    'copy-json': 'Copy JSON',
    'share-button': 'Share',
  };
  Object.entries(labels).forEach(([id, label]) => make(id, label));
  [
    'empty-state', 'loading', 'error', 'chart-shell', 'result-views', 'result-toolbar',
    'result-meta', 'source-link', 'notes-panel', 'notes-list', 'svg-source', 'json-source',
    'share-menu', 'download-menu', 'native-share', 'action-status', 'override', 'fiscal-year', 'ticker',
    'period', 'user-agent', 'share-linkedin', 'share-x', 'share-facebook',
  ].forEach((id) => make(id));

  const shareControl = new FakeElement('share-control');
  const downloadControl = new FakeElement('download-control');
  elements.set('.share-control', shareControl);
  elements.set('.download-control', downloadControl);
  for (const id of ['share-button', 'native-share', 'share-linkedin', 'share-x', 'share-facebook']) {
    elements.get(`#${id}`).shareOwner = shareControl;
  }
  for (const id of ['download-button', 'download-png', 'download-svg-chart', 'download-html']) {
    elements.get(`#${id}`).shareOwner = downloadControl;
  }
  elements.get('#share-menu').hidden = true;
  elements.get('#download-menu').hidden = true;
  elements.get('#result-views').hidden = true;
  elements.get('#result-toolbar').hidden = true;
  form.querySelectorAll = () => [sampleButton];

  const documentListeners = new Map();
  const downloads = [];
  const document = {
    activeElement: null,
    body: { append(element) { if (element.download !== undefined) downloads.push(element); } },
    querySelector(selector) {
      const modeMatch = selector.match(/^\[data-result-mode="(.+)"\]$/);
      if (modeMatch) return modeTabs.find((tab) => tab.dataset.resultMode === modeMatch[1]);
      return elements.get(selector) || null;
    },
    querySelectorAll(selector) {
      if (selector === '[data-result-mode]') return modeTabs;
      if (selector === '[data-result-panel]') return resultPanels;
      if (selector === '[data-copy-label]') return [...elements.values()].filter((item) => item.dataset.copyLabel);
      if (selector === '#share-menu a') return ['share-linkedin', 'share-x', 'share-facebook'].map((id) => elements.get(`#${id}`));
      if (selector === '#download-menu button') return ['download-png', 'download-svg-chart', 'download-html'].map((id) => elements.get(`#${id}`));
      return [];
    },
    createElement(tag) {
      if (tag === 'canvas') {
        return {
          width: 0,
          height: 0,
          getContext() { return { drawImage() {} }; },
          toBlob(callback) { callback(new Blob(['png'], { type: 'image/png' })); },
        };
      }
      return new FakeElement(tag);
    },
    execCommand() { return false; },
    addEventListener(type, listener) {
      const listeners = documentListeners.get(type) || [];
      listeners.push(listener);
      documentListeners.set(type, listeners);
    },
    async emit(type, properties = {}) {
      const event = { target: document, ...properties };
      for (const listener of documentListeners.get(type) || []) await listener(event);
    },
  };

  let nextResult = result('FIRST');
  let clipboardWrite = async () => { throw new Error('clipboard denied'); };
  let clipboardImageWrite = async () => {};
  let nativeShare = async () => {};
  const navigator = {
    clipboard: {
      writeText(value) { return clipboardWrite(value); },
      write(items) { return clipboardImageWrite(items); },
    },
    canShare() { return false; },
    share(data) { return nativeShare(data); },
  };

  return {
    document,
    downloads,
    elements,
    modeTabs,
    navigator,
    resultPanels,
    sampleButton,
    setClipboardWrite(write) { clipboardWrite = write; },
    setClipboardImageWrite(write) { clipboardImageWrite = write; },
    setNativeShare(share) { nativeShare = share; },
    setResult(value) { nextResult = value; },
    async fetch() { return { ok: true, async json() { return nextResult; } }; },
  };
}


async function loadApp(harness) {
  Object.defineProperty(globalThis, 'document', { configurable: true, value: harness.document });
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: harness.navigator });
  Object.defineProperty(globalThis, 'window', { configurable: true, value: { location: { href: 'https://example.com/' } } });
  Object.defineProperty(globalThis, 'fetch', { configurable: true, value: harness.fetch });
  Object.defineProperty(globalThis, 'requestAnimationFrame', { configurable: true, value: (callback) => callback() });
  Object.defineProperty(globalThis, 'ClipboardItem', {
    configurable: true,
    value: class { constructor(content) { this.content = content; } },
  });
  Object.defineProperty(globalThis, 'Image', {
    configurable: true,
    value: class {
      constructor() { this.naturalWidth = 1280; this.naturalHeight = 720; }
      set src(value) { this.imageUrl = value; queueMicrotask(() => this.onload()); }
    },
  });

  const appPath = new URL('../web/app.js', import.meta.url);
  const actionsUrl = new URL('../web/result-actions.mjs', import.meta.url).href;
  const source = (await readFile(appPath, 'utf8')).replace("'./result-actions.mjs'", `'${actionsUrl}'`);
  const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString('base64')}#${Date.now()}`;
  await import(moduleUrl);
}


async function flushAsyncEvents() {
  await new Promise((resolve) => setImmediate(resolve));
  await new Promise((resolve) => setImmediate(resolve));
}


test('real app controller resets views, wires downloads, dismisses sharing, and ignores stale copy feedback', async () => {
  const harness = createHarness();
  await loadApp(harness);

  await harness.sampleButton.emit('click');
  await harness.modeTabs[1].emit('click');
  assert.equal(harness.resultPanels[1].hidden, false);

  harness.setResult(result('SECOND'));
  await harness.sampleButton.emit('click');
  assert.deepEqual(harness.resultPanels.map((panel) => panel.hidden), [false, true, true]);
  assert.match(harness.elements.get('#svg-source').textContent, /SECOND/);

  await harness.elements.get('#download-button').emit('click');
  assert.equal(harness.elements.get('#download-menu').hidden, false);
  await harness.elements.get('#download-png').emit('click');
  assert.equal(harness.downloads.at(-1).download, 'second-2026-q1-sankey.png');
  assert.equal(harness.downloads.at(-1).clicked, true);
  assert.equal(harness.document.activeElement, harness.elements.get('#download-button'));

  const shareButton = harness.elements.get('#share-button');
  await shareButton.emit('click');
  assert.equal(harness.elements.get('#share-menu').hidden, false);
  await harness.document.emit('keydown', { key: 'Escape' });
  assert.equal(harness.elements.get('#share-menu').hidden, true);
  assert.equal(harness.document.activeElement, shareButton);

  harness.setNativeShare(async () => {
    const error = new Error('share failed');
    error.name = 'NotAllowedError';
    throw error;
  });
  await harness.elements.get('#native-share').emit('click');
  assert.equal(harness.elements.get('#action-status').textContent, 'Sharing isn’t available right now.');

  let finishCopy;
  harness.setClipboardWrite(() => new Promise((resolve) => { finishCopy = resolve; }));
  const copyButton = harness.elements.get('#copy-svg-source');
  await copyButton.emit('click');
  harness.setResult(result('THIRD'));
  await harness.sampleButton.emit('click');
  finishCopy();
  await flushAsyncEvents();

  assert.equal(copyButton.textContent, 'Copy SVG code');
  assert.equal(harness.elements.get('#action-status').textContent, '');

  harness.setClipboardWrite(async () => { throw new Error('clipboard denied'); });
  await copyButton.emit('click');
  await flushAsyncEvents();
  assert.equal(
    harness.elements.get('#action-status').textContent,
    'Couldn’t copy the SVG code. Select it in the source view and copy manually.',
  );
});


test('copy image reports success and ignores a superseded failure for the same result', async () => {
  const harness = createHarness();
  await loadApp(harness);
  await harness.sampleButton.emit('click');

  let rejectFirstWrite;
  let writeCount = 0;
  harness.setClipboardImageWrite(async (items) => {
    await items[0].content['image/png'];
    writeCount += 1;
    if (writeCount === 1) {
      await new Promise((resolve, reject) => { rejectFirstWrite = reject; });
    }
  });

  const copyButton = harness.elements.get('#copy-image');
  const firstCopy = copyButton.emit('click');
  await flushAsyncEvents();
  const secondCopy = copyButton.emit('click');
  await secondCopy;

  assert.equal(copyButton.textContent, 'Copied');
  assert.equal(harness.elements.get('#action-status').textContent, 'Chart image copied to the clipboard.');

  rejectFirstWrite(new Error('first write denied'));
  await firstCopy;
  assert.equal(copyButton.textContent, 'Copied');
  assert.equal(harness.elements.get('#action-status').textContent, 'Chart image copied to the clipboard.');
});


test('copy image failure gives a truthful PNG download fallback', async () => {
  const harness = createHarness();
  await loadApp(harness);
  await harness.sampleButton.emit('click');
  harness.setClipboardImageWrite(async () => { throw new Error('clipboard denied'); });

  await harness.elements.get('#copy-image').emit('click');

  assert.equal(harness.elements.get('#copy-image').textContent, 'Copy image');
  assert.equal(
    harness.elements.get('#action-status').textContent,
    'Couldn’t copy the chart image. Use Download → Download PNG instead.',
  );
});


test('copy image completion from an earlier result cannot change the current result feedback', async () => {
  const harness = createHarness();
  await loadApp(harness);
  await harness.sampleButton.emit('click');

  let finishWrite;
  harness.setClipboardImageWrite(async (items) => {
    await items[0].content['image/png'];
    await new Promise((resolve) => { finishWrite = resolve; });
  });

  const copyButton = harness.elements.get('#copy-image');
  const pendingCopy = copyButton.emit('click');
  await flushAsyncEvents();
  harness.setResult(result('THIRD'));
  await harness.sampleButton.emit('click');
  finishWrite();
  await pendingCopy;

  assert.equal(copyButton.textContent, 'Copy image');
  assert.equal(harness.elements.get('#action-status').textContent, '');
});
