export const COMPARISON_FIELDS = [
  { key: 'issuer', label: 'Issuer' },
  { key: 'expenseRatio', label: 'Net expense ratio', format: formatPercent, asOfKey: 'expenseRatio' },
  { key: 'aum', label: 'Assets under management', format: formatCurrencyBillions, asOfKey: 'aum' },
  { key: 'inceptionDate', label: 'Inception date', asOfKey: 'inceptionDate' },
  { key: 'benchmark', label: 'Benchmark / category', asOfKey: 'benchmark' },
  { key: 'holdingsCount', label: 'Holdings count', format: formatInteger, asOfKey: 'holdingsCount' },
  { key: 'topSectors', label: 'Largest sector exposures', format: formatTopSectors, asOfKey: 'topSectors' },
  { key: 'performance', label: 'Performance snapshot', format: formatPerformance }
];

export function validateSelection(leftTicker, rightTicker, etfs) {
  const tickers = new Set(etfs.map((etf) => etf.ticker));
  if (!tickers.has(leftTicker) || !tickers.has(rightTicker)) {
    return { valid: false, message: 'Choose two ETFs from the fixture list.' };
  }
  if (leftTicker === rightTicker) {
    return { valid: false, message: 'Choose two distinct ETFs before comparing.' };
  }
  return { valid: true, message: '' };
}

export function buildComparison(leftTicker, rightTicker, etfs) {
  const validation = validateSelection(leftTicker, rightTicker, etfs);
  if (!validation.valid) return { validation, rows: [], explanation: [] };

  const left = etfs.find((etf) => etf.ticker === leftTicker);
  const right = etfs.find((etf) => etf.ticker === rightTicker);
  const rows = COMPARISON_FIELDS.map((field) => ({
    label: field.label,
    left: formatFieldValue(left, field),
    right: formatFieldValue(right, field)
  }));

  return { validation, left, right, rows, explanation: explainDifferences(left, right) };
}

export function explainDifferences(left, right) {
  const messages = [];
  const erDiff = Number((left.expenseRatio - right.expenseRatio).toFixed(4));
  if (erDiff === 0) {
    messages.push(`${left.ticker} and ${right.ticker} have the same net expense ratio in this fixture.`);
  } else {
    const cheaper = erDiff < 0 ? left : right;
    const costlier = cheaper === left ? right : left;
    messages.push(`${cheaper.ticker} has the lower net expense ratio (${formatPercent(cheaper.expenseRatio)} vs. ${formatPercent(costlier.expenseRatio)}).`);
  }

  const larger = left.aum >= right.aum ? left : right;
  const smaller = larger === left ? right : left;
  messages.push(`${larger.ticker} has the larger asset base (${formatCurrencyBillions(larger.aum)} vs. ${formatCurrencyBillions(smaller.aum)}).`);

  if (left.benchmark !== right.benchmark) {
    messages.push(`${left.ticker} tracks ${left.benchmark}; ${right.ticker} tracks ${right.benchmark}.`);
  }

  const holdingsDiff = Math.abs(left.holdingsCount - right.holdingsCount);
  if (holdingsDiff > 50) {
    const broader = left.holdingsCount > right.holdingsCount ? left : right;
    const narrower = broader === left ? right : left;
    messages.push(`${broader.ticker} is broader by holdings count (${formatInteger(broader.holdingsCount)} vs. ${formatInteger(narrower.holdingsCount)}).`);
  }

  const leftTop = left.topSectors[0];
  const rightTop = right.topSectors[0];
  if (leftTop?.name && rightTop?.name) {
    messages.push(`${left.ticker}'s largest sector exposure is ${leftTop.name}; ${right.ticker}'s is ${rightTop.name}.`);
  }

  const ytdDiff = Number((left.performance.ytdReturn - right.performance.ytdReturn).toFixed(2));
  if (ytdDiff !== 0) {
    const leader = ytdDiff > 0 ? left : right;
    const lagger = leader === left ? right : left;
    messages.push(`${leader.ticker} has the higher YTD return in the fixture snapshot (${formatPercent(leader.performance.ytdReturn)} vs. ${formatPercent(lagger.performance.ytdReturn)}).`);
  }

  return messages;
}

export function fixtureAsOfRange(etfs) {
  const dates = Array.from(new Set(etfs.flatMap((etf) => [etf.asOfDate, ...Object.values(etf.fieldAsOfDates ?? {})]))).sort();
  return dates.length === 1 ? dates[0] : `${dates[0]} to ${dates[dates.length - 1]}`;
}

export function fieldDateSummary(etfs) {
  return etfs.map((etf) => `${etf.ticker}: profile ${etf.asOfDate}; performance ${etf.performance.asOfDate}; AUM ${etf.fieldAsOfDates?.aum ?? etf.asOfDate}; holdings/sectors ${etf.fieldAsOfDates?.holdingsCount ?? etf.asOfDate}/${etf.fieldAsOfDates?.topSectors ?? etf.asOfDate}`).join(' | ');
}

export function formatPercent(value) {
  const numeric = Number(value);
  const digits = Math.abs(numeric) > 0 && Math.abs(numeric) < 0.1 ? 4 : 2;
  return `${numeric.toFixed(digits)}%`;
}

export function formatCurrencyBillions(value) {
  return `$${Number(value).toLocaleString('en-US', { maximumFractionDigits: 2 })}B`;
}

export function formatInteger(value) {
  return Number(value).toLocaleString('en-US');
}

export function formatTopSectors(sectors) {
  return sectors.map((sector) => `${sector.name} ${formatPercent(sector.weight)}`).join('; ');
}

export function formatPerformance(performance) {
  return `YTD ${formatPercent(performance.ytdReturn)}; 1-year ${formatPercent(performance.oneYearReturn)} (as of ${performance.asOfDate})`;
}

function formatFieldValue(etf, field) {
  const raw = etf[field.key];
  const formatted = field.format ? field.format(raw) : raw;
  const asOfDate = field.asOfKey ? etf.fieldAsOfDates?.[field.asOfKey] : undefined;
  return asOfDate ? `${formatted} (as of ${asOfDate})` : formatted;
}
