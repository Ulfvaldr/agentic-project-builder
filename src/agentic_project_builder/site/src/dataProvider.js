export async function loadEtfFixtures(fetcher = fetch) {
  const response = await fetcher('fixtures/etfs.json', { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`Unable to load ETF fixtures: ${response.status}`);
  }
  return response.json();
}
