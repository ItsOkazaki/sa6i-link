import assert from 'node:assert/strict';
import { test } from 'node:test';
import { CLEAN_METHODS, createCleanBridge } from './renderer-bridge.mjs';

test('every bundled preload method forwards its name, arguments, and result', async () => {
  const calls = [];
  const bridge = createCleanBridge(async (name, args) => {
    calls.push([name, args]);
    return { name, args };
  });
  for (const method of CLEAN_METHODS) {
    const value = await bridge.api[method]('one', { two: 2 });
    assert.deepEqual(value, { name: method, args: ['one', { two: 2 }] });
  }
  assert.equal(calls.length, CLEAN_METHODS.length);
  assert.equal(bridge.api.nonexistent, undefined);
  assert.ok(Object.isFrozen(bridge.api));
});

test('backend errors reach the renderer', async () => {
  const bridge = createCleanBridge(async () => { throw new Error('denied'); });
  await assert.rejects(bridge.api.cleanJunk(['test']), /denied/);
});

test('progress can be unsubscribed and close disables the adapter', async () => {
  const received = [];
  const bridge = createCleanBridge(async () => 'ok');
  const stop = bridge.api.onProgress(event => received.push(event));
  bridge.progress({ task: 'junk', done: 1 });
  stop();
  bridge.progress({ task: 'junk', done: 2 });
  assert.deepEqual(received, [{ task: 'junk', done: 1 }]);
  bridge.close();
  await assert.rejects(bridge.api.system(), /closed/);
  assert.throws(() => bridge.api.onProgress(() => {}), /closed/);
});
