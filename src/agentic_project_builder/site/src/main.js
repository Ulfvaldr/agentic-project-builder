const state = { data: null };
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
  const response = await fetch('browser-data.json', { cache: 'no-store' });
  if (!response.ok) throw new Error(`Unable to load browser data: ${response.status}`);
  state.data = await response.json();
  populateSelect(leftSelect, state.data.funds, 'SPY');
  populateSelect(rightSelect, state.data.funds, 'QQQ');
  leftSelect.addEventListener('change', render);
  rightSelect.addEventListener('change', render);
  renderMetadata();
  render();
}

function populateSelect(select, funds, selectedTicker) {
  select.replaceChildren(...funds.map((fund) => {
    const option = document.createElement('option');
    option.value = fund.ticker;
    option.textContent = `${fund.ticker} — ${fund.name}`;
    option.selected = fund.ticker === selectedTicker;
    return option;
  }));
}

function render() {
  const comparison = state.data.comparisons[`${leftSelect.value}:${rightSelect.value}`];
  validationMessage.textContent = comparison.validation.message;
  if (!comparison.validation.valid) {
    table.replaceChildren();
    explanationOutput.textContent = 'Comparison unavailable until the selection is valid.';
    return;
  }
  table.replaceChildren(
    row(['Field', comparison.leftTicker, comparison.rightTicker], true),
    ...comparison.rows.map((item) => row([item.label, item.left, item.right])),
  );
  const list = document.createElement('ul');
  comparison.explanation.forEach((message) => {
    const item = document.createElement('li');
    item.textContent = message;
    list.append(item);
  });
  explanationOutput.replaceChildren(list);
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

function renderMetadata() {
  sourceList.replaceChildren(...state.data.sources.map((source) => {
    const item = document.createElement('li');
    const link = document.createElement('a');
    link.href = source.url;
    link.rel = 'noreferrer';
    link.textContent = source.label;
    item.append(link, ` — ${source.publisher}`);
    return item;
  }));
  fixtureAsOf.textContent = state.data.fixtureMetadata;
  disclaimerText.textContent = state.data.disclaimer;
}
