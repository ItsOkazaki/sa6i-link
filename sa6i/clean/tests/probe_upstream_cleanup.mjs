// SPDX-License-Identifier: GPL-3.0-or-later
// Isolated Linux-only source investigation of Cleanly 0.2.0 cleanup guards.
// This NEVER runs the packaged app, Electron, scanJunk, cleanJunk, the Recycle
// Bin, uninstallers or startup tools. The pinned upstream deleteCacheEntry
// function receives ONLY paths created under one temporary directory, and its
// import of Electron and drive enumeration is replaced with inert stubs.
// It documents two behaviours of upstream code; it is not a Windows test.
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { mkdtemp, mkdir, lstat, readFile, rm, symlink, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';

if (process.platform !== 'linux') throw new Error('Run this controlled investigation on Linux only');
const expectGuard = !process.argv.includes('--expect-unguarded');
const source = process.argv[2] && path.resolve(process.argv[2]);
if (!source) throw new Error('Pass the pinned Cleanly v0.2.0 source directory (with esbuild installed)');
const upstreamTrash = '28a2f68426ec7511fcbd0e20ce96763dd3042770d8ef314975d5e93b6cde2252';
const hardenedTrash = 'f24e1c0be3fc1766c599df796cff4eeead57c0dd50102c236842021f706156ac';
const pinned = {
  'electron/services/trash.ts': expectGuard ? hardenedTrash : upstreamTrash,
  'electron/services/walk.ts': 'ec40101e574b4746129f440ba330cbd5a38a5b509bb58938d24a26667d63da62',
};
for (const [name, expected] of Object.entries(pinned)) {
  const hash = createHash('sha256').update(await readFile(path.join(source, name))).digest('hex');
  assert.equal(hash, expected, `Unknown ${name} for this mode; refusing execution`);
}
// expectGuard is read before the pin table, so hoist it above the imports' use.

const esbuildDir = process.env.ESBUILD_DIR || source;
const { build } = createRequire(path.join(esbuildDir, 'package.json'))('esbuild');
const exists = async (p) => {
  try { await lstat(p); return true; } catch (err) {
    if (err.code !== 'ENOENT') throw err;
    return false;
  }
};
const dir = await mkdtemp(path.join(os.tmpdir(), 'sa6i-clean-safety-'));
try {
  const output = path.join(dir, 'probe.mjs');
  await build({
    entryPoints: [path.join(source, 'electron/services/trash.ts')],
    outfile: output, bundle: true, platform: 'node', format: 'esm',
    plugins: [{ name: 'disable-electron-and-disk', setup(builder) {
      builder.onResolve({ filter: /^electron$/ }, () => ({ path: 'electron', namespace: 'inert' }));
      builder.onResolve({ filter: /^\.\/disk$/ }, () => ({ path: 'disk', namespace: 'inert' }));
      builder.onLoad({ filter: /.*/, namespace: 'inert' }, (args) => ({
        contents: args.path === 'disk' ? 'export const dataDriveMounts = async () => [];' :
          'export const shell = {trashItem: async () => {throw Error("disabled")}}; export const app = {getPath() {throw Error("disabled")}};',
        loader: 'js',
      }));
    }}],
  });
  const trash = await import(pathToFileURL(output));
  const { deleteCacheEntry, isUnredirectedRoot } = trash;
  if (expectGuard && typeof isUnredirectedRoot !== 'function') {
    throw new Error('This source has no Sa6i cache-root guard; run harden_upstream.py first');
  }

  // 1. A link entry that is itself the deletion target must be refused.
  const root1 = path.join(dir, 'guard-root');
  await mkdir(path.join(dir, 'guard-outside'), { recursive: true });
  await mkdir(root1, { recursive: true });
  await writeFile(path.join(dir, 'guard-outside', 'sentinel'), 'fixture only');
  await symlink(path.join(dir, 'guard-outside'), path.join(root1, 'link'), 'dir');
  const direct = await deleteCacheEntry(path.join(root1, 'link'), root1);
  assert.equal(direct.refused, true, 'Upstream no longer refuses a link target');
  assert.equal(await exists(path.join(dir, 'guard-outside', 'sentinel')), true);

  // 2. A cache root reached through a redirecting ancestor is not re-validated:
  //    upstream only lstat()s the root, so the root itself looks like a real
  //    directory and its contents are deleted through the redirect. This is a
  //    documented limitation of the reviewed code, not a Windows exploit proof.
  const real = path.join(dir, 'real', 'cache');
  const alias = path.join(dir, 'redirect');
  await mkdir(real, { recursive: true });
  await symlink(path.join(dir, 'real'), alias, 'dir');
  const redirectedRoot = path.join(alias, 'cache');
  await writeFile(path.join(real, 'sentinel.txt'), 'fixture only');
  const rootStat = await lstat(redirectedRoot);
  assert(rootStat.isDirectory() && !rootStat.isSymbolicLink());
  const throughRedirect = await deleteCacheEntry(path.join(redirectedRoot, 'sentinel.txt'), redirectedRoot);
  const survived = await exists(path.join(real, 'sentinel.txt'));
  const rootIsUnguarded = expectGuard ? await isUnredirectedRoot(redirectedRoot) : undefined;
  const plainRootIsUnguarded = expectGuard ? await isUnredirectedRoot(path.join(dir, 'guard-root')) : undefined;
  if (expectGuard) {
    assert.equal(rootIsUnguarded, false, 'Guard must reject a root reached through a redirect');
    assert.equal(plainRootIsUnguarded, true, 'Guard must accept an ordinary directory');
    assert.equal(throughRedirect.refused, true, 'A redirected root must be refused');
    assert.equal(survived, true, 'Nothing may be deleted through a redirected root');
  }
  console.log(JSON.stringify({
    linkTargetRefused: direct.refused,
    redirectedRootAcceptedAsRealDirectory: true,
    guardRejectsRedirectedRoot: rootIsUnguarded === false,
    guardAcceptsPlainRoot: plainRootIsUnguarded === true,
    redirectedDeletionRefused: throughRedirect.refused,
    deletedThroughRedirectedAncestor: !survived,
    result: throughRedirect,
  }, null, 2));
  if (expectGuard && survived) {
    console.log('Hardened source: deletion through a redirected root was refused.');
  } else if (!expectGuard && !survived) {
    console.error('Unguarded upstream reproduced the redirect gap (isolated fixture).');
  } else {
    console.error('Unexpected result for this mode; update SAFETY-REVIEW.md.');
    process.exitCode = 1;
  }
} finally {
  await rm(dir, { recursive: true, force: true });
}
