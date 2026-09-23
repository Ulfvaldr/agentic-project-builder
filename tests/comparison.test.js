import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { buildComparison, explainDifferences, fieldDateSummary, fixtureAsOfRange, validateSelection } from '../src/comparison.js';

const etfs = JSON.parse(await readFile(new URL('../fixtures/etfs.json', import.meta.url), 'utf8'));

test('validates distinct fixture-backed ETF selections', () => {
  assert.deepEqual(validateSelection('SPY', 'QQQ', etfs), { valid: true, message: '' });
  assert.equal(validateSelection('SPY', 'SPY', etfs).valid, false);
  assert.match(validateSelection('SPY', 'SPY', etfs).message, /distinct/i);
  assert.equal(validateSelection('SPY', 'NOPE', etfs).valid, false);
  assert.match(validateSelection('SPY', 'NOPE', etfs).message, /fixture list/i);
});

test('builds one display row for every researched comparison field with field dates', () => {
  const result = buildComparison('SPY', 'QQQ', etfs);
  assert.equal(result.validation.valid, true);
  assert.equal(result.rows.length, 8);
  assert.deepEqual(result.rows.map((row) => row.label), [
    'Issuer',
    'Net expense ratio',
    'Assets under management',
    'Inception date',
    'Benchmark / category',
    'Holdings count',
    'Largest sector exposures',
    'Performance snapshot'
  ]);
  assert.match(result.rows.find((row) => row.label === 'Assets under management').left, /\$806\.18B \(as of 2026-09-22\)/);
  assert.match(result.rows.find((row) => row.label === 'Performance snapshot').left, /YTD 13\.05%; 1-year 20\.17% \(as of 2026-08-31\)/);
});

test('explanation is deterministic and grounded in selected data', () => {
  const [spy, qqq] = ['SPY', 'QQQ'].map((ticker) => etfs.find((etf) => etf.ticker === ticker));
  assert.deepEqual(explainDifferences(spy, qqq), explainDifferences(spy, qqq));
  const explanation = explainDifferences(spy, qqq).join(' ');
  assert.match(explanation, /SPY has the lower net expense ratio/);
  assert.match(explanation, /SPY tracks S&P 500 Index/);
  assert.match(explanation, /QQQ's is Technology/);
});

test('invalid comparison returns no rows or explanation', () => {
  const result = buildComparison('VTI', 'VTI', etfs);
  assert.equal(result.validation.valid, false);
  assert.deepEqual(result.rows, []);
  assert.deepEqual(result.explanation, []);
});

test('fixture date helpers report field-level date range and summary', () => {
  assert.equal(fixtureAsOfRange(etfs), '2026-04-28 to 2026-09-23');
  const summary = fieldDateSummary(etfs);
  assert.match(summary, /SPY: profile 2026-09-22; performance 2026-08-31; AUM 2026-09-22; holdings\/sectors 2026-09-22\/2026-09-22/);
  assert.match(summary, /VTI: profile 2026-08-31; performance 2026-08-31; AUM 2026-08-31; holdings\/sectors 2026-08-31\/2026-08-31/);
});

test('official-source fixture spot checks prevent stale provenance regressions', () => {
  const spy = etfs.find((etf) => etf.ticker === 'SPY');
  assert.equal(spy.aum, 806.18442);
  assert.equal(spy.asOfDate, '2026-09-22');
  assert.equal(spy.fieldAsOfDates.expenseRatio, '2026-09-23');
  assert.deepEqual(spy.topSectors.slice(0, 3).map(({ name, weight }) => [name, weight]), [
    ['Information Technology', 39.28],
    ['Financials', 11.53],
    ['Communication Services', 10.00]
  ]);

  const vti = etfs.find((etf) => etf.ticker === 'VTI');
  assert.equal(vti.holdingsCount, 3507);
  assert.equal(vti.aum, 690.1);
  assert.equal(vti.fieldAsOfDates.expenseRatio, '2026-04-28');
  assert.deepEqual(vti.topSectors.slice(0, 3).map(({ name, weight }) => [name, weight]), [
    ['Technology', 40.90],
    ['Consumer Discretionary', 12.00],
    ['Industrials', 11.80]
  ]);
});
