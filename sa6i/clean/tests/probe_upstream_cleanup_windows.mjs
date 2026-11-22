// SPDX-License-Identifier: GPL-3.0-or-later
// Windows runner probe for Cleanly 0.2.0 deletion guards.
//
// Runs on a disposable Windows CI machine, never on a user's PC. It bundles the
// pinned upstream trash.ts with esbuild, replaces its Electron/disk imports with
// inert stubs, and then only touches files it created under one temporary
// directory. No Electron, no cleaner UI, no real caches, no Recycle Bin.
//
// What it answers: on real NTFS, does a junction count as a link when it is the
// deletion target, and does deleting through a junction *above* a cache root
// reach the junction target? The second is the documented limitation; this
// records what Windows actually does instead of assuming Linux behaviour carries
// over.
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { mkdtemp, mkdir, lstat, readdir, readFile, rm, symlink, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';

if (process.platform !== 'win32') throw new Error('This probe is for Windows runners only');
const source = process.argv[2] && path.resolve(process.argv[2]);
if (!source) throw new Error('Pass the pinned Cleanly v0.2.0 source directory as the first argument');
const pinned = {
  'electron/services/trash.ts': '28a2f68426ec7511fcbd0e20ce96763dd3042770d8ef314975d5e93b6cde2252',
  'electron/services/walk.ts': 'ec40101e574b4746129f440ba330cbd5a38a5b509bb58938d24a26667d63da62',
};
for (const [name, expected] of Object.entries(pinned)) {
  const hash = createHash('sha256').update(await readFile(path.join(source, name))).digest('hex');
  assert.equal(hash, expected, `Unknown upstream file ${name}; refusing to run`);
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
  const { deleteCacheEntry, isSafeUserPath } = await import(pathToFileURL(bundle));

  // A. A junction that is itself the deletion target.
  const sandbox = path.join(work, 'a');
  const realA = path.join(sandbox, 'real');
  await mkdir(realA, { recursive: true });
  await writeFile(path.join(realA, 'sentinel.txt'), 'fixture');
  const linkA = path.join(sandbox, 'junction');
  await symlink(realA, linkA, 'junction');
  const linkStat = await lstat(linkA);
  results.junctionReportedAsLinkByLstat = linkStat.isSymbolicLink();
  const direct = await deleteCacheEntry(linkA, sandbox);
  results.junctionTargetRefused = direct.refused;
  results.junctionTargetSentinelSurvived = await exists(path.join(realA, 'sentinel.txt'));

  // B. A cache root reached through a junction above it.
  const sandboxB = path.join(work, 'b');
  const realCache = path.join(sandboxB, 'real', 'cache');
  await mkdir(realCache, { recursive: true });
  await writeFile(path.join(realCache, 'sentinel.txt'), 'fixture');
  await writeFile(path.join(sandboxB, 'real', 'outside-cache.txt'), 'fixture');
  const alias = path.join(sandboxB, 'alias');
  await symlink(path.join(sandboxB, 'real'), alias, 'junction');
  const redirectedRoot = path.join(alias, 'cache');
  const rootStat = await lstat(redirectedRoot);
  results.redirectedRootLooksLikeDirectory = rootStat.isDirectory() && !rootStat.isSymbolicLink();
  const through = await deleteCacheEntry(path.join(redirectedRoot, 'sentinel.txt'), redirectedRoot);
  results.deletedThroughRedirectedRoot = !(await exists(path.join(realCache, 'sentinel.txt')));
  results.siblingOutsideCacheSurvived = await exists(path.join(sandboxB, 'real', 'outside-cache.txt'));
  results.redirectedRootResult = through;

  // C. Ordinary cache deletion stays inside its root.
  const sandboxC = path.join(work, 'c');
  const cache = path.join(sandboxC, 'cache');
  await mkdir(path.join(cache, 'nested'), { recursive: true });
  await writeFile(path.join(cache, 'nested', 'junk.bin'), 'fixture');
  await writeFile(path.join(sandboxC, 'keep.txt'), 'fixture');
  const plain = await deleteCacheEntry(path.join(cache, 'nested'), cache);
  results.plainCacheRemoved = plain.removed === 1;
  results.plainCacheRootEmptied = (await readdir(cache)).length === 0;
  results.neighbourSurvived = await exists(path.join(sandboxC, 'keep.txt'));

  // D. Lexical path guard on real Windows paths.
  const home = os.homedir();
  // isSafeUserPath returns true when deletion is ALLOWED, so protected paths
  // must come back false.
  results.guardAllowsWindowsSystem = isSafeUserPath('C:\\Windows\\System32\\drivers\\etc\\hosts');
  results.guardAllowsDesktop = isSafeUserPath(path.join(home, 'Desktop'));
  results.guardAllowsSshKey = isSafeUserPath(path.join(home, '.ssh', 'id_rsa'));
  results.guardAllowsOrdinaryUserFile = isSafeUserPath(path.join(home, 'sa6i-probe-fixture', 'notes.txt'));
  results.guardAllowsRelativePath = isSafeUserPath('notes.txt');

  // One compact line is re-emitted as a GitHub annotation: job logs live in
  // storage some environments cannot reach, annotations are readable via API.
  console.log('PROBE_RESULT=' + JSON.stringify(results));
  console.log(JSON.stringify(results, null, 2));
  // Only a regression of the documented guard fails the run. The redirected-root
  // result is an observation for SAFETY-REVIEW.md, not an assertion about safety.
  if (!results.junctionTargetRefused || !results.junctionTargetSentinelSurvived) {
    throw new Error('Upstream guard no longer refuses a junction deletion target');
  }
  if (!results.plainCacheRemoved || !results.neighbourSurvived || !results.plainCacheRootEmptied) {
    throw new Error('Ordinary cache deletion behaved unexpectedly');
  }
  if (results.guardAllowsWindowsSystem || results.guardAllowsDesktop || results.guardAllowsSshKey
      || !results.guardAllowsOrdinaryUserFile || results.guardAllowsRelativePath) {
    throw new Error('Lexical path guard behaved unexpectedly');
  }
} finally {
  await rm(work, { recursive: true, force: true });
}
