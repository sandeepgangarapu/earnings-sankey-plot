import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildShareMetadata,
  buildSocialShareUrls,
  buildStandaloneHtml,
  copyText,
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
