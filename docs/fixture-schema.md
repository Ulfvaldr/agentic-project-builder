# ETF fixture schema

Python loads and validates `fixtures/etfs.json` (with an identical packaged copy at `src/agentic_project_builder/site/fixtures/etfs.json`). Python then generates `browser-data.json`, which is the browser's static, preformatted input. The browser performs no domain comparison or formatting.

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

Validation and generation commands:

    PYTHONPATH=src python -m agentic_project_builder validate-fixtures
    PYTHONPATH=src python -m agentic_project_builder build-browser-data

Refresh procedure:

1. A human retrieves current issuer pages/fact sheets and, optionally, SEC EDGAR N-PORT holdings as a cross-check.
2. Update both committed fixture copies, preserving the schema above.
3. Validate fixtures and regenerate both browser-data copies with the commands above.
4. Run the full Python suite and live browser smoke test documented in the README.

The app performs no live network calls beyond loading its local committed static JSON.
