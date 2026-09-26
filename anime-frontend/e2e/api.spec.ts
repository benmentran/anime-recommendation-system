import { expect, test } from '@playwright/test';

// Service<->service contract against a LIVE backend (BFF :8000 by default).
// Skipped automatically when no backend is reachable (CI without docker).
const BFF = process.env.E2E_API_URL ?? 'http://localhost:8000';

async function backendUp(request: any): Promise<boolean> {
  try {
    const r = await request.get(`${BFF}/health`, { timeout: 5000 });
    return r.ok();
  } catch {
    return false;
  }
}

test('BFF /api/v1/rag/ask keeps {answer, candidates} shape', async ({ request }) => {
  test.skip(!(await backendUp(request)), 'no live backend');
  const r = await request.post(`${BFF}/api/v1/rag/ask`, {
    data: { query: 'mecha anime with heavy politics?', k: 2 },
    timeout: 120_000,
  });
  expect(r.status()).toBe(200);
  const body = await r.json();
  expect(typeof body.answer).toBe('string');
  expect(Array.isArray(body.candidates)).toBe(true);
  expect(body.candidates.length).toBeLessThanOrEqual(2);
  for (const c of body.candidates) {
    expect(typeof c.mal_id).toBe('number');
    expect(typeof c.title).toBe('string');
  }
});
