// SPDX-License-Identifier: GPL-3.0-or-later
// Sa6i cache-root guard, minified for insertion into the packaged bundle.
// harden_cleaner.py inserts this file's code (comment lines removed) verbatim;
// tests/test_guard_snippet.mjs evaluates it with a fake filesystem binding.
// Keep it on one line so the packaged bundle stays minified.
var Sa6iRootChecks=new Map;async function Sa6iUnredirectedRoot(r){var i=String(r).replace(/[\\/]+$/,""),e=Sa6iRootChecks.get(i.toLowerCase());if(e!==void 0)return e;var t=!0,s=i;try{for(;;){if((await st.lstat(s)).isSymbolicLink()){t=!1;break}var o=q.dirname(s);if(o===s)break;s=o}}catch{t=!1}return Sa6iRootChecks.set(i.toLowerCase(),t),t}
