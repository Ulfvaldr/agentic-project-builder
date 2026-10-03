import { buildComparison, fieldDateSummary, fixtureAsOfRange } from './comparison.js';
import { loadEtfFixtures } from './dataProvider.js';

const state = { etfs: [] };
const leftSelect = document.querySelector('#left-etf');
const rightSelect = document.querySelector('#right-etf');
const validationMessage = document.querySelector('#validation-message');
const table = document.querySelector('#comparison-table');
const explanationOutput = document.querySelector('#explanation-output');
const sourceList = document.querySelector('#source-list');
const fixtureAsOf = document.querySelector('#fixture-as-of');
const disclaimerText = document.querySelector('#disclaimer-text');

init().catch((error) => {
  validationMessage.textContent = error.message;
  console.error(error);
});

async function init() {
  state.etfs = await loadEtfFixtures();
  populateSelect(leftSelect, state.etfs, 'SPY');
  populateSelect(rightSelect, state.etfs, 'QQQ');
  leftSelect.addEventListener('change', render);
  rightSelect.addEventListener('change', render);
  renderSources(state.etfs);
  render();
}

function populateSelect(select, etfs, selectedTicker) {
  select.replaceChildren(...etfs.map((etf) => {
    const option = document.createElement('option');
    option.value = etf.ticker;
    option.textContent = `${etf.ticker} — ${etf.name}`;
    option.selected = etf.ticker === selectedTicker;
    return option;
  }));
}

function render() {
  const comparison = buildComparison(leftSelect.value, rightSelect.value, state.etfs);
  validationMessage.textContent = comparison.validation.message;
  if (!comparison.validation.valid) {
    table.innerHTML = '';
    explanationOutput.textContent = 'Comparison unavailable until the selection is valid.';
    return;
  }
  renderTable(comparison);
  renderExplanation(comparison.explanation);
}

function renderTable(comparison) {
  table.replaceChildren(row(['Field', comparison.left.ticker, comparison.right.ticker], true), ...comparison.rows.map((item) => row([item.label, item.left, item.right])));
}

function row(values, header = false) {
  const wrapper = document.createElement('div');
  wrapper.className = `comparison-row${header ? ' header' : ''}`;
  wrapper.setAttribute('role', 'row');
  values.forEach((value) => {
    const cell = document.createElement('div');
    cell.className = 'comparison-cell';
    cell.setAttribute('role', header ? 'columnheader' : 'cell');
    cell.textContent = value;
    wrapper.append(cell);
  });
  return wrapper;
}

function renderExplanation(messages) {
  const list = document.createElement('ul');
  messages.forEach((message) => {
    const item = document.createElement('li');
    item.textContent = message;
    list.append(item);
  });
  explanationOutput.replaceChildren(list);
}

function renderSources(etfs) {
  const uniqueSources = new Map();
  etfs.forEach((etf) => {
    etf.sources.forEach((source) => uniqueSources.set(source.url, source));
  });
  sourceList.replaceChildren(...Array.from(uniqueSources.values()).map((source) => {
    const item = document.createElement('li');
    const link = document.createElement('a');
    link.href = source.url;
    link.rel = 'noreferrer';
    link.textContent = source.label;
    item.append(link, ` — ${source.publisher}`);
    return item;
  }));
  const asOf = fixtureAsOfRange(etfs);
  fixtureAsOf.textContent = `Fixture field-date range: ${asOf}. Field-level dates: ${fieldDateSummary(etfs)}.`;
  disclaimerText.textContent = `For informational/educational purposes only. This is not investment advice and not a recommendation or offer to buy or sell any security. Data may be delayed or inaccurate; verify figures with the fund issuer. Fixture fields use the per-field as-of dates shown in the comparison rows and metadata, not one common date.`;
}
