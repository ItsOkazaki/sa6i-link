// SPDX-License-Identifier: GPL-3.0-or-later
// Windows runner probe for the Sa6i cache-root guard.
//
// Runs on a disposable Windows CI machine, never on a user's PC. It bundles the
// pinned upstream trash.ts (already patched by harden_upstream.py) with its
// Electron/disk imports replaced by inert stubs, then touches only files it
// created under one temporary directory. No Electron, no cleaner UI, no real
// caches, no Recycle Bin.
//
// What it answers on real NTFS: does the guard accept an ordinary cache root,
// including one spelled with different letter case; does it refuse a root
// reached through a junction; and does the existing rule still refuse a
// junction as the deletion target?
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { mkdtemp, mkdir, lstat, readdir, readFile, rm, symlink, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';

if (process.platform !== 'win32') throw new Error('This probe is for Windows runners only');
const source = process.argv[2] && path.resolve(process.argv[2]);
if (!source) throw new Error('Pass the hardened Cleanly v0.2.0 source directory as the first argument');
const expectGuard = true; // this workflow always runs the hardened source
const pinned = {
  'electron/services/trash.ts': 'a768fff423b6cdec80bb134a324d3a13f964d09a710ccc319243bca571ee0cc1',
  'electron/services/walk.ts': 'ec40101e574b4746129f440ba330cbd5a38a5b509bb58938d24a26667d63da62',
};
for (const [name, expected] of Object.entries(pinned)) {
  const hash = createHash('sha256').update(await readFile(path.join(source, name))).digest('hex');
  assert.equal(hash, expected, `Unknown hardened source file ${name}; refusing to run`);
}
// esbuild is installed in the workflow's scratch folder, not in the checkout.
const esbuildDir = process.env.ESBUILD_DIR || path.join(process.cwd(), 'probe-tools');
const { build } = createRequire(path.join(esbuildDir, 'package.json'))('esbuild');
const exists = async (p) => {
  try { await lstat(p); return true; } catch (err) {
    if (err.code !== 'ENOENT') throw err;
    return false;
  }
};
const results = {};
const work = await mkdtemp(path.join(os.tmpdir(), 'sa6i-win-probe-'));
try {
  const bundle = path.join(work, 'trash.mjs');
  await build({
    entryPoints: [path.join(source, 'electron/services/trash.ts')],
    outfile: bundle, bundle: true, platform: 'node', format: 'esm',
    plugins: [{ name: 'inert-electron', setup(builder) {
      builder.onResolve({ filter: /^electron$/ }, () => ({ path: 'electron', namespace: 'inert' }));
      builder.onResolve({ filter: /^\.\/disk$/ }, () => ({ path: 'disk', namespace: 'inert' }));
      builder.onLoad({ filter: /.*/, namespace: 'inert' }, (args) => ({
        contents: args.path === 'disk' ? 'export const dataDriveMounts = async () => [];' :
          'export const shell = {trashItem: async () => {throw Error("disabled")}}; export const app = {getPath() {throw Error("disabled")}};',
        loader: 'js',
      }));
    }}],
  });
  const { deleteCacheEntry, isUnredirectedRoot } = await import(pathToFileURL(bundle));
  assert.equal(typeof isUnredirectedRoot, 'function', 'The guard is missing from the bundle');

  // A. Junction as the deletion target: must still be refused.
  const sandboxA = path.join(work, 'a');
  const realA = path.join(sandboxA, 'real');
  await mkdir(realA, { recursive: true });
  await writeFile(path.join(realA, 'sentinel.txt'), 'fixture');
  const linkA = path.join(sandboxA, 'junction');
  await symlink(realA, linkA, 'junction');
  results.junctionReportedAsLinkByLstat = (await lstat(linkA)).isSymbolicLink();
  const direct = await deleteCacheEntry(linkA, sandboxA);
  results.junctionTargetRefused = direct.refused;
  results.junctionTargetSentinelSurvived = await exists(path.join(realA, 'sentinel.txt'));

  // B. Ordinary cache folder: the guard must allow cleaning, and deleting must
  //    stay inside the root.
  const cache = path.join(work, 'cache');
  await mkdir(path.join(cache, 'nested'), { recursive: true });
  await writeFile(path.join(cache, 'nested', 'junk.bin'), 'fixture');
  await writeFile(path.join(work, 'keep.txt'), 'fixture');
  const resolvedCache = path.resolve(cache);
  const realCache = await (await import('node:fs/promises')).realpath(cache);
  results.realpathEqualsResolveForNormalRoot = realCache === resolvedCache;
  results.realpathValue = realCache;
  results.resolvedValue = resolvedCache;
  results.guardAcceptsPlainRoot = await isUnredirectedRoot(cache);
  const plain = await deleteCacheEntry(path.join(cache, 'nested'), cache);
  results.plainCacheRemoved = plain.removed === 1 && plain.refused === false;
  results.plainCacheRootEmptied = (await readdir(cache)).length === 0;
  results.neighbourSurvived = await exists(path.join(work, 'keep.txt'));

  // C. The same folder spelled with different letter case must still be cleaned:
  //    Windows paths are case-insensitive even though realpath returns disk case.
  const cacheCase = path.join(work, 'CaseCache');
  await mkdir(cacheCase, { recursive: true });
  await writeFile(path.join(cacheCase, 'old.tmp'), 'fixture');
  const upperRoot = cacheCase.toUpperCase();
  results.guardAcceptsUpperCasedRoot = await isUnredirectedRoot(upperRoot);
  const upper = await deleteCacheEntry(path.join(upperRoot, 'old.tmp'), upperRoot);
  results.uppercasedRootCleaned = upper.removed === 1 && upper.refused === false;

  // D. A cache root reached through a junction above it: the guard must refuse
  //    and nothing behind the junction may be deleted.
  const sandboxD = path.join(work, 'd');
  const realD = path.join(sandboxD, 'real', 'cache');
  await mkdir(realD, { recursive: true });
  await writeFile(path.join(realD, 'sentinel.txt'), 'fixture');
  await writeFile(path.join(sandboxD, 'real', 'outside-cache.txt'), 'fixture');
  const alias = path.join(sandboxD, 'alias');
  await symlink(path.join(sandboxD, 'real'), alias, 'junction');
  const redirectedRoot = path.join(alias, 'cache');
  results.redirectedRootLooksLikeDirectory = (await lstat(redirectedRoot)).isDirectory();
  results.guardRejectsRedirectedRoot = (await isUnredirectedRoot(redirectedRoot)) === false;
  const through = await deleteCacheEntry(path.join(redirectedRoot, 'sentinel.txt'), redirectedRoot);
  results.redirectedDeletionRefused = through.refused;
  results.redirectedSentinelSurvived = await exists(path.join(realD, 'sentinel.txt'));
  results.siblingOutsideCacheSurvived = await exists(path.join(sandboxD, 'real', 'outside-cache.txt'));

  console.log('PROBE_RESULT=' + JSON.stringify(results));
  console.log(JSON.stringify(results, null, 2));

  const failures = [];
  if (!results.junctionTargetRefused || !results.junctionTargetSentinelSurvived) failures.push('junction target not refused');
  if (!results.guardAcceptsPlainRoot || !results.plainCacheRemoved || !results.plainCacheRootEmptied) failures.push('ordinary cache not cleaned');
  if (!results.neighbourSurvived) failures.push('deletion escaped its root');
  if (!results.guardAcceptsUpperCasedRoot || !results.uppercasedRootCleaned) failures.push('case-insensitive root refused');
  if (!results.guardRejectsRedirectedRoot || !results.redirectedDeletionRefused) failures.push('redirected root not refused');
  if (!results.redirectedSentinelSurvived || !results.siblingOutsideCacheSurvived) failures.push('data deleted through a redirect');
  if (failures.length) throw new Error('Guard probe failed: ' + failures.join('; '));
  console.log('Hardened guard behaved as intended on real NTFS.');
} finally {
  await rm(work, { recursive: true, force: true });
}
