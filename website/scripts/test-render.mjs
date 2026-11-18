import assert from 'node:assert/strict';
import { createElement } from 'react';
import { renderToString } from 'react-dom/server';
import { createServer } from 'vite';

const server = await createServer({
  server: { middlewareMode: true },
  appType: 'custom',
  optimizeDeps: { noDiscovery: true, include: [] },
  logLevel: 'error'
});
try {
  const { default: App } = await server.ssrLoadModule('/src/App.jsx');
  const html = renderToString(createElement(App));
  assert.match(html, /Your devices/);
  assert.match(html, /in sync\./);
  assert.match(html, /Download Windows ZIP/);
  assert.match(html, /Download Android APK/);
  assert.match(html, /sa6i-link\.png/);
  assert.match(html, /Interactive example only/);
  assert.match(html, /keep your original as a backup/i);
  assert.doesNotMatch(html, /class="notice"/);
  assert.match(html, /aria-expanded="false"/);
  assert.doesNotMatch(html, /Arabic test|test builds?|experimental builds/i);
  console.log('React render smoke test passed');
} finally {
  await server.close();
}
