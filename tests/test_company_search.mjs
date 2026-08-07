import assert from 'node:assert/strict';
import test from 'node:test';

import {
  fiscalYearChoices,
  formatCompany,
  moveCompanySelection,
  rankCompanyMatches,
  resolveCompanyTicker,
} from '../web/company-search.mjs';


const companies = [
  { ticker: 'GOOGL', name: 'Alphabet Inc.' },
  { ticker: 'APP', name: 'AppLovin Corp' },
  { ticker: 'AAPL', name: 'Apple Inc.' },
  { ticker: 'PAPL', name: 'Pineapple Energy Inc.' },
  { ticker: 'MSFT', name: 'Microsoft Corp' },
  { ticker: 'META', name: 'Meta Platforms, Inc.' },
  { ticker: 'AMZN', name: 'Amazon.com, Inc.' },
  { ticker: 'AMD', name: 'Advanced Micro Devices, Inc.' },
  { ticker: 'AMGN', name: 'Amgen Inc.' },
  { ticker: 'AMAT', name: 'Applied Materials, Inc.' },
];


test('formats a company as a readable name and ticker', () => {
  assert.equal(formatCompany(companies[0]), 'Alphabet Inc. (GOOGL)');
});


test('ranks exact ticker before ticker prefix, name prefix, and substring matches', () => {
  assert.deepEqual(
    rankCompanyMatches(companies, 'app').map(({ ticker }) => ticker),
    ['APP', 'AAPL', 'AMAT', 'PAPL'],
  );
});


test('search is case-insensitive, trims input, and caps results at eight', () => {
  assert.deepEqual(
    rankCompanyMatches(companies, '  A  ').map(({ ticker }) => ticker),
    ['APP', 'AAPL', 'AMZN', 'AMD', 'AMGN', 'AMAT', 'GOOGL', 'PAPL'],
  );
});


test('resolves a selected company or a manually entered ticker', () => {
  assert.equal(resolveCompanyTicker('Alphabet Inc. (GOOGL)', companies[0]), 'GOOGL');
  assert.equal(resolveCompanyTicker(' aapl ', null), 'AAPL');
  assert.equal(resolveCompanyTicker('brk-b', null), 'BRK-B');
  assert.equal(resolveCompanyTicker('Apple Incorporated', null), null);
});


test('moves the active company option with wraparound keyboard behavior', () => {
  assert.equal(moveCompanySelection(-1, 'ArrowDown', 3), 0);
  assert.equal(moveCompanySelection(2, 'ArrowDown', 3), 0);
  assert.equal(moveCompanySelection(0, 'ArrowUp', 3), 2);
  assert.equal(moveCompanySelection(1, 'Enter', 3), 1);
  assert.equal(moveCompanySelection(-1, 'ArrowDown', 0), -1);
});


test('builds descending fiscal years from next year through 2009', () => {
  const choices = fiscalYearChoices(2026);
  assert.deepEqual(choices.slice(0, 3), [2027, 2026, 2025]);
  assert.equal(choices.at(-1), 2009);
});
