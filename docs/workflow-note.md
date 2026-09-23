# Workflow note: Odin → Bao → Brokkr → Veritas

Public workflow evidence:

- Odin converted the user goal into an implementation plan and acceptance criteria.
- Bao supplied fixture-source research and provenance guidance.
- Brokkr implemented the ETF comparison demo and completed correction cycle 1.
- Veritas independently reviewed the artifact and release evidence.

Acceptance criteria captured for this implementation:

- User can select two distinct fixture-backed ETFs and every comparison field updates side by side.
- A deterministic plain-language explanation identifies material differences without giving investment advice.
- Source URLs, data as-of date, and data-freshness/non-advice disclaimer are visible.
- Same or invalid selections are blocked or clearly reported.
- App is keyboard-usable and responsive.
- App starts and tests pass from clean documented commands with no secrets, network dependency, or backend.
- Repository documentation records the direct agent path, commands, failures/retries, and design changes.

Design decisions:

- Zero-framework static HTML/CSS/ES-module JavaScript.
- Committed ETF fixtures are the data source of record.
- `src/dataProvider.js` isolates the local fixture-loading seam for later refresh-provider replacement.
- Node's built-in test runner is the only automated test dependency.
- No backend, database, authentication, live trading, portfolio advice, persistent agents, production deployment, or orchestration service was added.

Commands used by Brokkr:

    npm run validate:fixtures
    npm test
    npm start
    npm run check:browser
    chrome --headless=new --disable-gpu --no-sandbox --virtual-time-budget=3000 --dump-dom http://127.0.0.1:4173

Failures/retries/design changes:

- Initial unit test run had one assertion mismatch in explanation wording; Brokkr tightened the assertion to the actual deterministic sentence and re-ran `npm test` successfully.
- Invesco's downloadable fact-sheet URL surfaced a country/role splash during extraction, so the fixture keeps the fact-sheet URL as attribution but relies on the accessible Invesco QQQ overview page for page-extracted holdings/AUM/performance values.
- QQQ total expense ratio on the overview extraction appeared as `0%`, inconsistent with Invesco search/fact-sheet snippets showing `0.18%`; the fixture uses `0.18%` and cites the Invesco fact sheet/product materials.
- Correction cycle 1 fixed the missing favicon browser-log regression by adding an inline SVG favicon and a dependency-free `npm run check:browser` CDP smoke test that records Runtime, Log, and HTTP 4xx/5xx failures across initial load and reload.
- Correction cycle 1 reconciled fixture values with browser-extracted official issuer pages: SPY AUM is `$806,184.42M` as of 2026-09-22; SPY sectors are 39.28/11.53/10.00 as of 2026-09-22; VTI stock count is 3,507, share-class net assets are `$690.1B`, and top sectors are Technology 40.90%, Consumer Discretionary 12.00%, and Industrials 11.80% as of 2026-08-31.
- Fixture records now carry `fieldAsOfDates`, comparison rows show field-level dates, and the metadata/disclaimer no longer implies a single shared as-of date across mixed-source fields.
- Correction cycle 1 evidence: `npm run validate:fixtures` validated 3 records with field-level provenance spot-checks; `npm test` passed 6/6; `npm run check:browser` passed clean initial load and reload against `http://127.0.0.1:4173/`.
- No release or deployment was attempted; Veritas must pass before any human approval gate can be considered.
