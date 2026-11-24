// Experimental renderer-side adapter for Sa6i Clean's bundled UI.
// It does not implement cleanup or transport. A future host MUST authenticate
// the renderer and validate every method and argument on the privileged side.
export const CLEAN_METHODS = Object.freeze([
  'system', 'disk', 'disks', 'fileIcons', 'scanJunk', 'cleanJunk',
  'scanSpaces', 'scanLargeFiles', 'scanDuplicates', 'trashPaths', 'revealPath',
  'startupItems', 'setStartupItem', 'installedApps', 'uninstallApp',
  'protection', 'getSettings', 'setSettings', 'setApiKey', 'askAi',
  'tipsProfile', 'startTip', 'sendFeedback', 'openExternal',
]);

/**
 * Adapts a future request transport to the API expected by Cleanly's renderer.
 * `request(method, args)` returns a promise. The host feeds progress events to
 * `progress(event)`. There is deliberately no implicit global or network setup.
 */
export function createCleanBridge(request) {
  if (typeof request !== 'function') throw new TypeError('request must be a function');
  const listeners = new Set();
  const api = Object.create(null);
  let closed = false;
  for (const method of CLEAN_METHODS) {
    api[method] = async (...args) => {
      if (closed) throw new Error('Sa6i Clean bridge is closed');
      return await request(method, args);
    };
  }
  api.onProgress = callback => {
    if (closed) throw new Error('Sa6i Clean bridge is closed');
    if (typeof callback !== 'function') throw new TypeError('progress callback must be a function');
    listeners.add(callback);
    return () => listeners.delete(callback);
  };
  Object.freeze(api);
  return Object.freeze({
    api,
    progress(event) {
      if (!closed) for (const listener of [...listeners]) listener(event);
    },
    close() {
      closed = true;
      listeners.clear();
    },
  });
}
