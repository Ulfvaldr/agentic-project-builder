# Agentic Project Builder

A lean Hermes team demo that takes a high-level software goal and turns it into a working artifact through the existing Kanban task graph:

User goal → Odin plans → Bao researches → Brokkr implements → Veritas independently reviews → Human approves release.

This repository contains the first demo artifact: a zero-framework ETF comparison web app backed by committed fixture data.

## Demo behavior

- Choose two distinct ETFs from `fixtures/etfs.json`.
- See researched fields side by side: ticker/name, issuer, expense ratio, AUM, inception date, benchmark/category, holdings/sector exposure, and dated performance snapshot.
- Read a deterministic explanation of material differences between the selected funds.
- See source links, fixture field-level as-of dates, and a non-advice/data-freshness disclaimer.
- Same or invalid selections are reported instead of compared.
- No backend, database, authentication, secrets, trading, portfolio advice, live data calls, or deployment is included.

## Run locally

Requirements: Python 3.11+ and Node.js 20+ (or any recent Node version with the built-in `node --test` runner).

The browser still executes the existing JavaScript implementation while Python parity is reviewed. Run both stacks from this directory:

    PYTHONPATH=src python -m agentic_project_builder validate-fixtures
    PYTHONPATH=src python -m unittest discover -s tests_python -v
    PYTHONPATH=src python -m agentic_project_builder serve

In another terminal, check the Python-served page with the Python browser checker:

    PYTHONPATH=src python -m agentic_project_builder check-browser

The original JavaScript commands remain supported and are required during parity validation:

    npm run validate:fixtures
    npm test
    npm start

With the server running, the headless Chrome console/log regression check can be run in another terminal:

    npm run check:browser

Then open:

    http://localhost:4173

To use a different port:

    PORT=5000 npm start

## Project layout

- `index.html` — static page shell
- `src/styles.css` — responsive CSS
- `src/main.js` — browser rendering and event handling
- `src/comparison.js` — validation, comparison rows, explanation logic, formatting helpers
- `src/dataProvider.js` — data-access seam for fixture loading
- `fixtures/etfs.json` — committed ETF fixture data and source links
- `tests/comparison.test.js` — Node built-in unit tests
- `scripts/serve.mjs` — small local static server for the demo
- `scripts/validate-fixtures.mjs` — schema sanity checks for fixture records
- `src/agentic_project_builder/` — parallel dependency-free Python models, comparison, validation, CLI, server, and browser checker
- `tests_python/` — Python unit, CLI, server-safety, and JS/Python cross-runtime parity tests
- `pyproject.toml` — Python 3.11+ package and console-script metadata (no runtime dependencies)
- `docs/fixture-schema.md` — fixture contract and refresh seam
- `docs/workflow-note.md` — Odin → Bao → Brokkr → Veritas workflow evidence

## Data and disclaimer

Fixture values are hand-curated from cited issuer product pages/fact sheets surfaced by Bao's research and browser-accessible source checks. They are static point-in-time values for a workflow demo, not a live financial data product.

For informational/educational purposes only. This is not investment advice and not a recommendation or offer to buy or sell any security. Data may be delayed or inaccurate; verify figures with the fund issuer.

## Rebuild checklist

1. Update `fixtures/etfs.json` only from issuer/SEC sources.
2. Run `npm run validate:fixtures`.
3. Run `npm test`.
4. Run `npm start` and manually check the page in a browser.
5. Run `npm run check:browser` against the running local server to catch console/log errors, including missing static assets.
6. Do not publish or deploy until Veritas passes and a human explicitly approves release.
