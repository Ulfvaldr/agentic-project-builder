import { readFile } from 'node:fs/promises';
import {
  buildComparison,
  fieldDateSummary,
  fixtureAsOfRange,
  formatCurrencyBillions,
  formatInteger,
  formatPercent
} from '../src/comparison.js';

const etfs = JSON.parse(await readFile(new URL('../fixtures/etfs.json', import.meta.url), 'utf8'));
const tickers = etfs.map((etf) => etf.ticker);
const comparisons = {};
for (const left of tickers) {
  for (const right of tickers) {
    const result = buildComparison(left, right, etfs);
    comparisons[`${left}:${right}`] = {
      validation: result.validation,
      leftTicker: result.left?.ticker ?? null,
      rightTicker: result.right?.ticker ?? null,
      rows: result.rows,
      explanation: result.explanation
    };
  }
}
const values = [
  0, 0.03, 0.1, -0.001, -0.00001, 1.005, 2.675, 690.1, 806.18442, 3507, 1.5,
  1e21, -1e21, 1.2345678901234568e21, -9.876543210987655e22
];
const selectionComparisons = {};
for (const [left, right] of [['', 'QQQ'], ['SPY', ''], ['NOPE', 'QQQ'], ['SPY', 'NOPE']]) {
  const result = buildComparison(left, right, etfs);
  selectionComparisons[`${left}:${right}`] = {
    validation: result.validation,
    leftTicker: result.left?.ticker ?? null,
    rightTicker: result.right?.ticker ?? null,
    rows: result.rows,
    explanation: result.explanation
  };
}
console.log(JSON.stringify({
  comparisons,
  selectionComparisons,
  fixtureAsOfRange: fixtureAsOfRange(etfs),
  fieldDateSummary: fieldDateSummary(etfs),
  formatting: values.map((value) => ({
    value,
    percent: formatPercent(value),
    currency: formatCurrencyBillions(value),
    integer: formatInteger(value)
  }))
}));
