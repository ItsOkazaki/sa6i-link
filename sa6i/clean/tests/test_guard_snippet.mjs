// SPDX-License-Identifier: GPL-3.0-or-later
// Evaluates the exact minified guard inserted into the packaged bundle.
// Linux only, synthetic paths only, no cleaner code and no deletion.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, rm, symlink } from 'node:fs/promises';
import realFs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { readFile } from 'node:fs/promises';

const snippetPath = path.join(import.meta.dirname, '..', 'guard_snippet.js');
const code = (await readFile(snippetPath, 'utf8')).split('\n')
  .filter((line) => line.trim() && !line.trimStart().startsWith('//')).join('\n');

function load({ st = realFs } = {}) {
  // `q` is the bundle's node:path namespace; `st` is its fs.promises binding.
  return new Function('st', 'q', `${code}; return Sa6iUnredirectedRoot;`)(st, path);
}

test('accepts an ordinary directory, with or without a trailing separator', async () => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'guard-snippet-'));
  try {
    const guard = load();
    assert.equal(await guard(root), true);
    assert.equal(await guard(root + path.sep), true);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test('refuses a directory reached through a symlink anywhere above it', async () => {
  const base = await mkdtemp(path.join(os.tmpdir(), 'guard-snippet-'));
  try {
    const real = path.join(base, 'real', 'cache');
    await mkdir(real, { recursive: true });
    await symlink(path.join(base, 'real'), path.join(base, 'alias'), 'dir');
    const guard = load();
    assert.equal(await guard(path.join(base, 'alias', 'cache')), false);
  } finally {
    await rm(base, { recursive: true, force: true });
  }
});

test('refuses a symlink as the root itself and an unresolvable path', async () => {
  const base = await mkdtemp(path.join(os.tmpdir(), 'guard-snippet-'));
  try {
    await mkdir(path.join(base, 'target'));
    await symlink(path.join(base, 'target'), path.join(base, 'link'), 'dir');
    const guard = load();
    assert.equal(await guard(path.join(base, 'link')), false);
    assert.equal(await guard(path.join(base, 'missing')), false);
  } finally {
    await rm(base, { recursive: true, force: true });
  }
});

test('spelling differences alone, such as 8.3 short names, are not refused', async () => {
  // Every component reports as a real directory; only the spelling differs from
  // whatever the filesystem would canonicalise to.
  const seen = [];
  const st = { lstat: async (p) => { seen.push(p); return { isSymbolicLink: () => false }; } };
  const guard = load({ st });
  assert.equal(await guard('/users/RUNNER~1/AppData/Local/Temp'), true);
  assert.ok(seen.includes('/users/RUNNER~1/AppData/Local/Temp'));
});

test('remembers the verdict for a root instead of walking again', async () => {
  let calls = 0;
  const st = { lstat: async () => { calls += 1; return { isSymbolicLink: () => false }; } };
  const guard = load({ st });
  assert.equal(await guard('/data/cache'), true);
  const afterFirst = calls;
  assert.ok(afterFirst > 1, 'the walk should inspect every component');
  assert.equal(await guard('/data/cache/'), true);
  assert.equal(calls, afterFirst, 'the cached verdict must not re-walk');
});
