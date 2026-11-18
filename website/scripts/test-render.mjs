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
  assert.match(html, /sa6i-link\.jpg/);
  assert.match(html, /Interactive example only/);
  assert.match(html, /Keep your working version/);
  assert.match(html, /aria-expanded="false"/);
  assert.doesNotMatch(html, /Arabic test|test builds?|experimental builds/i);
  console.log('React render smoke test passed');
} finally {
  await server.close();
}
