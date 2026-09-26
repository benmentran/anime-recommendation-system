import { expect, test } from '@playwright/test';

// Frontend <-> BFF contract at the HTTP boundary (backend mocked).
const MOCK_ASK = {
  answer: 'Gợi ý: Gundam IBO vì chính trị nặng nề.',
  candidates: [
    { mal_id: 38000, title: 'Gundam IBO', score: 8.1 },
    { mal_id: 21, title: 'One Piece', score: 9.0 },
  ],
};

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/rag/ask', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json',
      body: JSON.stringify(MOCK_ASK) });
  });
  await page.goto('/chat');
});

test('chat asks AI and renders answer with candidate links', async ({ page }) => {
  await expect(page.getByTestId('chat-empty')).toBeVisible();
  await page.getByTestId('chat-input').fill('anime mecha chính trị?');
  await page.getByTestId('chat-send').click();
  await expect(page.getByTestId('chat-msg-assistant').last())
    .toContainText('Gundam IBO vì chính trị');
  const cand = page.getByTestId('chat-candidate-38000');
  await expect(cand).toBeVisible();
  expect(await cand.getAttribute('href')).toBe('/anime/38000');
});

test('chat shows error message when backend is down', async ({ page }) => {
  await page.unroute('**/api/v1/rag/ask');
  await page.route('**/api/v1/rag/ask', async (route) => {
    await route.fulfill({ status: 502, contentType: 'application/json',
      body: JSON.stringify({ detail: 'down' }) });
  });
  await page.getByTestId('chat-input').fill('hello?');
  await page.getByTestId('chat-send').click();
  await expect(page.getByTestId('chat-msg-assistant').last())
    .toContainText('không khả dụng');
});
