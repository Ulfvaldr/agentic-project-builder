# ETF fixture schema

The browser app loads `fixtures/etfs.json` through the narrow `src/dataProvider.js` seam. Later work can replace that provider with a refresh script or service without changing the comparison or rendering logic.

Each ETF record must include:

- `ticker`, `name`, `issuer`
- `expenseRatio`: net annual expense ratio as a percent, e.g. `0.03` means 0.03%
- `aum`: assets under management in USD billions
- `inceptionDate`: ISO date
- `benchmark`: benchmark and broad category text
- `holdingsCount`: integer
- `topSectors`: ordered `{ name, weight }` percent list
- `topHoldings`: ordered company-name list for source traceability
- `performance`: `{ ytdReturn, oneYearReturn, asOfDate }`, with returns expressed as percent values
- `asOfDate`: date for the issuer profile/fact-sheet snapshot, not a promise that every field shares that date
- `fieldAsOfDates`: ISO date map for `expenseRatio`, `aum`, `inceptionDate`, `benchmark`, `holdingsCount`, `topSectors`, `topHoldings`, and `performance`
- `sources`: one or more `{ label, publisher, url }` entries

Validation command:

    npm run validate:fixtures

Refresh seam:

1. A human retrieves current issuer pages/fact sheets and, optionally, SEC EDGAR N-PORT holdings as a cross-check.
2. The human updates only `fixtures/etfs.json`, preserving the schema above.
3. Run `npm run validate:fixtures`, `npm test`, and the browser console check before committing.

The app intentionally performs no live network calls beyond loading its local committed JSON fixture.
