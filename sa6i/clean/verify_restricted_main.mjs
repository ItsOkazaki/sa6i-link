// Verifies the exact restricted Electron IPC dispatch table, not the entire app.
// Usage: node verify_restricted_main.mjs /path/to/extracted/dist-electron/main.js
import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
const file = process.argv[2];
if (!file) throw new Error('Pass the extracted restricted main.js path');
const source = await readFile(file, 'utf8');
assert.equal(createHash('sha256').update(source).digest('hex'),
  '040c5f55105b38e369c11829a14bdadeb511ca78fa81a47985fb2536aeff133f',
  'Refusing to evaluate an unknown bundled file');
const begin = source.indexOf('var lC={');
const end = source.indexOf('};function uC()', begin);
assert.ok(begin >= 0 && end > begin, 'Expected dispatch table not found');
// The table in the hash-locked supplied build consists of arrow function
// definitions. No cleaner function is invoked when constructing it.
const table = Function(`return (${source.slice(begin + 7, end + 1)})`)();
const disabled = ['cleanJunk', 'trashPaths', 'revealPath', 'setStartupItem',
  'uninstallApp', 'setSettings', 'setApiKey', 'askAi', 'tipsProfile',
  'startTip', 'sendFeedback', 'openExternal'];
for (const name of disabled) {
  await assert.rejects(table[name]('probe'), /Disabled in the Sa6i integration experiment/);
}
console.log(`Verified ${disabled.length} restricted IPC handlers reject calls.`);
