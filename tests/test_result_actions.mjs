import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildShareMetadata,
  buildNativeShareData,
  buildSocialShareUrls,
  buildStandaloneHtml,
  copyPngBlob,
  copyText,
  renderSvgToPng,
  selectResultMode,
  serializeStatement,
  statementFilename,
} from '../web/result-actions.mjs';


const statement = {
  company: 'Alphabet & Co <Holdings>',
  ticker: 'GOOGL',
  fiscal_year: 2026,
  period: 'Q1',
  revenue: 100,
};


test('serializes result artifacts with stable filenames and safe standalone HTML', () => {
  assert.equal(statementFilename(statement, 'svg'), 'googl-2026-q1-sankey.svg');
  assert.equal(
    serializeStatement(statement),
    '{\n  "company": "Alphabet & Co <Holdings>",\n  "ticker": "GOOGL",\n  "fiscal_year": 2026,\n  "period": "Q1",\n  "revenue": 100\n}\n',
  );

  const html = buildStandaloneHtml({ statement, svg: '<svg aria-label="chart"></svg>' });
  assert.match(html, /<title>Alphabet &amp; Co &lt;Holdings&gt; earnings Sankey<\/title>/);
  assert.match(html, /<svg aria-label="chart"><\/svg>/);
  assert.doesNotMatch(html, /<title>Alphabet & Co <Holdings>/);
});


test('builds encoded LinkedIn, X, and Facebook share destinations', () => {
  const pageUrl = 'https://example.com/results?view=chart&source=sample';
  const metadata = buildShareMetadata(statement, pageUrl);

  assert.deepEqual(metadata, {
    title: 'Alphabet & Co <Holdings> earnings Sankey',
    text: 'See Alphabet & Co <Holdings> (GOOGL) · Q1 FY2026 earnings as a Sankey diagram.',
    url: pageUrl,
  });

  const urls = buildSocialShareUrls(metadata);
  const linkedin = new URL(urls.linkedin);
  const x = new URL(urls.x);
  const facebook = new URL(urls.facebook);

  assert.equal(linkedin.origin + linkedin.pathname, 'https://www.linkedin.com/sharing/share-offsite/');
  assert.equal(linkedin.searchParams.get('url'), pageUrl);
  assert.equal(x.origin + x.pathname, 'https://twitter.com/intent/tweet');
  assert.equal(x.searchParams.get('text'), metadata.text);
  assert.equal(x.searchParams.get('url'), pageUrl);
  assert.equal(facebook.origin + facebook.pathname, 'https://www.facebook.com/sharer/sharer.php');
  assert.equal(facebook.searchParams.get('u'), pageUrl);
});


test('includes an SVG file in native share data only when the full payload is supported', () => {
  const metadata = buildShareMetadata(statement, 'https://example.com/result');
  const checked = [];
  class FakeFile {
    constructor(parts, name, options) {
      this.parts = parts;
      this.name = name;
      this.type = options.type;
    }
  }

  const shareData = buildNativeShareData(metadata, '<svg></svg>', 'chart.svg', {
    File: FakeFile,
    canShare(candidate) { checked.push(candidate); return true; },
  });

  assert.equal(checked.length, 1);
  assert.equal(checked[0].title, metadata.title);
  assert.equal(checked[0].text, metadata.text);
  assert.equal(checked[0].url, metadata.url);
  assert.equal(shareData.files[0].name, 'chart.svg');
  assert.equal(shareData.files[0].type, 'image/svg+xml');
  assert.deepEqual(shareData.files[0].parts, ['<svg></svg>']);
});


test('native share data falls back to metadata when file capability checks fail', () => {
  const metadata = buildShareMetadata(statement, 'https://example.com/result');
  class FakeFile {}

  assert.deepEqual(buildNativeShareData(metadata, '<svg/>', 'chart.svg', {
    File: FakeFile,
    canShare() { return false; },
  }), metadata);
  assert.deepEqual(buildNativeShareData(metadata, '<svg/>', 'chart.svg', {
    File: FakeFile,
    canShare() { throw new Error('capability unavailable'); },
  }), metadata);
  assert.deepEqual(buildNativeShareData(metadata, '<svg/>', 'chart.svg', {
    File: class { constructor() { throw new Error('file unavailable'); } },
    canShare() { return true; },
  }), metadata);
});


test('renders SVG to a two-times-resolution PNG and revokes its object URL', async () => {
  const events = [];
  let canvas;
  class FakeImage {
    constructor() {
      this.naturalWidth = 300;
      this.naturalHeight = 150;
    }
    set src(value) {
      events.push(['src', value]);
      queueMicrotask(() => this.onload());
    }
  }
  const document = {
    createElement(tag) {
      assert.equal(tag, 'canvas');
      canvas = {
        width: 0,
        height: 0,
        getContext(kind) {
          assert.equal(kind, '2d');
          return { drawImage(...args) { events.push(['draw', ...args.slice(1)]); } };
        },
        toBlob(callback, type) {
          events.push(['blob', type]);
          callback(new Blob(['png bytes'], { type }));
        },
      };
      return canvas;
    },
  };
  const url = {
    createObjectURL(blob) { events.push(['create', blob.type]); return 'blob:chart'; },
    revokeObjectURL(value) { events.push(['revoke', value]); },
  };

  const png = await renderSvgToPng('<svg viewBox="0 0 1280 720"></svg>', {
    Blob,
    Image: FakeImage,
    document,
    URL: url,
  }, 2);

  assert.equal(png.type, 'image/png');
  assert.equal(canvas.width, 2560);
  assert.equal(canvas.height, 1440);
  assert.deepEqual(events, [
    ['create', 'image/svg+xml'],
    ['src', 'blob:chart'],
    ['draw', 0, 0, 2560, 1440],
    ['blob', 'image/png'],
    ['revoke', 'blob:chart'],
  ]);
});


test('rejects failed PNG rendering and still revokes its object URL', async () => {
  const revoked = [];
  class BrokenImage {
    set src(value) { queueMicrotask(() => this.onerror(new Error(`cannot load ${value}`))); }
  }

  await assert.rejects(
    renderSvgToPng('<svg></svg>', {
      Blob,
      Image: BrokenImage,
      document: { createElement() { throw new Error('must not draw'); } },
      URL: {
        createObjectURL() { return 'blob:broken'; },
        revokeObjectURL(value) { revoked.push(value); },
      },
    }),
    /could not be rendered/i,
  );
  assert.deepEqual(revoked, ['blob:broken']);
});


test('starts a promise-backed PNG clipboard write synchronously from the user action', async () => {
  const png = new Blob(['png'], { type: 'image/png' });
  const writes = [];
  let resolvePng;
  const pendingPng = new Promise((resolve) => { resolvePng = resolve; });
  class FakeClipboardItem {
    constructor(content) { this.content = content; }
  }

  const copy = copyPngBlob(pendingPng, {
    ClipboardItem: FakeClipboardItem,
    clipboard: {
      async write(items) {
        writes.push(items);
        await items[0].content['image/png'];
      },
    },
  });
  assert.equal(writes.length, 1);
  assert.equal(writes[0][0].content['image/png'], pendingPng);
  resolvePng(png);
  assert.equal(await copy, true);

  assert.equal(await copyPngBlob(png, {}), false);
  assert.equal(await copyPngBlob(png, {
    ClipboardItem: FakeClipboardItem,
    clipboard: { async write() { throw new Error('denied'); } },
  }), false);
});


function fakeTab(mode) {
  return {
    dataset: { resultMode: mode },
    tabIndex: null,
    attributes: new Map(),
    setAttribute(name, value) { this.attributes.set(name, value); },
  };
}


test('selects one result tab and reveals only its matching panel', () => {
  const tabs = ['chart', 'svg', 'json'].map(fakeTab);
  const panels = ['chart', 'svg', 'json'].map((mode) => ({
    dataset: { resultPanel: mode },
    hidden: false,
  }));

  assert.equal(selectResultMode('json', tabs, panels), 'json');
  assert.deepEqual(tabs.map((tab) => tab.attributes.get('aria-selected')), ['false', 'false', 'true']);
  assert.deepEqual(tabs.map((tab) => tab.tabIndex), [-1, -1, 0]);
  assert.deepEqual(panels.map((panel) => panel.hidden), [true, true, false]);
  assert.equal(selectResultMode('unknown', tabs, panels), 'chart');
  assert.deepEqual(panels.map((panel) => panel.hidden), [false, true, true]);
});


test('copies with the Clipboard API when it succeeds', async () => {
  const writes = [];
  const copied = await copyText('raw svg', {
    clipboard: { async writeText(value) { writes.push(value); } },
  });

  assert.equal(copied, true);
  assert.deepEqual(writes, ['raw svg']);
});


test('falls back to a selected temporary textarea after Clipboard API rejection', async () => {
  const events = [];
  const area = {
    value: '',
    setAttribute(name, value) { events.push(['attribute', name, value]); },
    select() { events.push(['select', this.value]); },
    remove() { events.push(['remove']); },
  };
  const document = {
    body: { append(element) { events.push(['append', element.value]); } },
    createElement(tag) { events.push(['create', tag]); return area; },
    execCommand(command) { events.push(['command', command]); return true; },
  };

  const copied = await copyText('normalized json', {
    clipboard: { async writeText() { throw new Error('denied'); } },
    document,
  });

  assert.equal(copied, true);
  assert.deepEqual(events, [
    ['create', 'textarea'],
    ['attribute', 'readonly', ''],
    ['append', 'normalized json'],
    ['select', 'normalized json'],
    ['command', 'copy'],
    ['remove'],
  ]);
});


test('reports failure when neither clipboard strategy copies', async () => {
  const area = {
    value: '',
    setAttribute() {},
    select() {},
    remove() {},
  };
  const document = {
    body: { append() {} },
    createElement() { return area; },
    execCommand() { return false; },
  };

  assert.equal(await copyText('data', { document }), false);
  assert.equal(await copyText('data', {}), false);
});


test('reports failure and removes the fallback textarea when selection throws', async () => {
  const events = [];
  const area = {
    value: '',
    setAttribute() {},
    select() { events.push('select'); throw new Error('selection unavailable'); },
    remove() { events.push('remove'); },
  };
  const document = {
    body: { append() { events.push('append'); } },
    createElement() { return area; },
    execCommand() { throw new Error('must not be reached'); },
  };
  let copied;

  await assert.doesNotReject(async () => {
    copied = await copyText('data', { document });
  });
  assert.equal(copied, false);
  assert.deepEqual(events, ['append', 'select', 'remove']);
});
