import { readFile } from 'node:fs/promises';

const requiredStringFields = ['ticker', 'name', 'issuer', 'inceptionDate', 'benchmark', 'asOfDate'];
const requiredFieldDates = ['expenseRatio', 'aum', 'inceptionDate', 'benchmark', 'holdingsCount', 'topSectors', 'topHoldings', 'performance'];
const officialSpotChecks = {
  SPY: {
    aum: 806.18442,
    asOfDate: '2026-09-22',
    fieldAsOfDates: { aum: '2026-09-22', holdingsCount: '2026-09-22', topSectors: '2026-09-22', performance: '2026-08-31' },
    holdingsCount: 504,
    topSectors: [
      ['Information Technology', 39.28],
      ['Financials', 11.53],
      ['Communication Services', 10.00]
    ],
    performance: { ytdReturn: 13.05, oneYearReturn: 20.17, asOfDate: '2026-08-31' },
    sourceUrlIncludes: 'ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy'
  },
  QQQ: {
    aum: 498.64,
    asOfDate: '2026-09-21',
    fieldAsOfDates: { aum: '2026-09-21', holdingsCount: '2026-09-21', topSectors: '2026-08-30', performance: '2026-08-30' },
    holdingsCount: 102,
    topSectors: [
      ['Technology', 66.36],
      ['Consumer Discretionary', 16.65],
      ['Telecommunications', 4.72]
    ],
    performance: { oneYearReturn: 26.27, asOfDate: '2026-08-30' },
    sourceUrlIncludes: 'invesco.com/qqq-etf/en/about.html'
  },
  VTI: {
    aum: 690.1,
    asOfDate: '2026-08-31',
    fieldAsOfDates: { expenseRatio: '2026-04-28', aum: '2026-08-31', holdingsCount: '2026-08-31', topSectors: '2026-08-31', performance: '2026-08-31' },
    holdingsCount: 3507,
    topSectors: [
      ['Technology', 40.90],
      ['Consumer Discretionary', 12.00],
      ['Industrials', 11.80]
    ],
    performance: { ytdReturn: 13.45, oneYearReturn: 20.24, asOfDate: '2026-08-31' },
    sourceUrlIncludes: 'investor.vanguard.com/investment-products/etfs/profile/vti'
  }
};

const etfs = JSON.parse(await readFile(new URL('../fixtures/etfs.json', import.meta.url), 'utf8'));
const errors = [];

if (!Array.isArray(etfs) || etfs.length < 2) errors.push('Fixture must contain at least two ETF records.');
const tickers = new Set();
for (const [index, etf] of etfs.entries()) {
  for (const field of requiredStringFields) {
    if (typeof etf[field] !== 'string' || etf[field].length === 0) errors.push(`ETF ${index} missing ${field}.`);
  }
  if (tickers.has(etf.ticker)) errors.push(`Duplicate ticker ${etf.ticker}.`);
  tickers.add(etf.ticker);
  if (typeof etf.expenseRatio !== 'number') errors.push(`${etf.ticker} expenseRatio must be a number.`);
  if (typeof etf.aum !== 'number') errors.push(`${etf.ticker} aum must be a number in billions.`);
  if (!Number.isInteger(etf.holdingsCount)) errors.push(`${etf.ticker} holdingsCount must be an integer.`);
  if (!Array.isArray(etf.topSectors) || etf.topSectors.length < 1) errors.push(`${etf.ticker} must list top sectors.`);
  if (!Array.isArray(etf.topHoldings) || etf.topHoldings.length < 1) errors.push(`${etf.ticker} must list top holdings for traceability.`);
  if (!etf.performance || typeof etf.performance.ytdReturn !== 'number' || typeof etf.performance.oneYearReturn !== 'number' || !etf.performance.asOfDate) errors.push(`${etf.ticker} missing performance snapshot.`);
  if (!etf.fieldAsOfDates || requiredFieldDates.some((field) => !isIsoDate(etf.fieldAsOfDates[field]))) errors.push(`${etf.ticker} must include ISO fieldAsOfDates for ${requiredFieldDates.join(', ')}.`);
  if (!Array.isArray(etf.sources) || etf.sources.length < 1 || etf.sources.some((source) => !source.url || !source.publisher || !source.label)) errors.push(`${etf.ticker} must include source links.`);
  checkOfficialSpotCheck(etf);
}

if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}
console.log(`Validated ${etfs.length} ETF fixture records with field-level provenance spot-checks.`);

function checkOfficialSpotCheck(etf) {
  const expected = officialSpotChecks[etf.ticker];
  if (!expected) return;
  for (const [field, value] of Object.entries(expected)) {
    if (field === 'fieldAsOfDates' || field === 'topSectors' || field === 'performance' || field === 'sourceUrlIncludes') continue;
    if (etf[field] !== value) errors.push(`${etf.ticker} ${field} expected ${value} from cited official source, got ${etf[field]}.`);
  }
  for (const [field, value] of Object.entries(expected.fieldAsOfDates ?? {})) {
    if (etf.fieldAsOfDates?.[field] !== value) errors.push(`${etf.ticker} ${field} as-of date expected ${value}, got ${etf.fieldAsOfDates?.[field]}.`);
  }
  expected.topSectors?.forEach(([name, weight], index) => {
    const actual = etf.topSectors?.[index];
    if (actual?.name !== name || actual?.weight !== weight) errors.push(`${etf.ticker} top sector ${index + 1} expected ${name} ${weight}%, got ${actual?.name} ${actual?.weight}%.`);
  });
  for (const [field, value] of Object.entries(expected.performance ?? {})) {
    if (etf.performance?.[field] !== value) errors.push(`${etf.ticker} performance ${field} expected ${value}, got ${etf.performance?.[field]}.`);
  }
  if (!etf.sources?.some((source) => source.url.includes(expected.sourceUrlIncludes))) errors.push(`${etf.ticker} missing required official source URL containing ${expected.sourceUrlIncludes}.`);
}

function isIsoDate(value) {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value);
}
