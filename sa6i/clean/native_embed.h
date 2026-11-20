// SPDX-License-Identifier: GPL-3.0-or-later
// Experimental Win32 embedding backend, guarded in the Sa6i Link source.
// No full app build or Windows integration test has been completed.
// Only supports the exact restricted Windows 7 probe executable and ASAR.
#ifndef SA6I_NATIVE_EMBED_H
#define SA6I_NATIVE_EMBED_H

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    EMBED_IDLE, EMBED_DISCOVERING, EMBED_ATTACHED,
    EMBED_UNATTACHED, EMBED_CLOSING, EMBED_CLOSED
} EmbedStatus;

typedef struct {
    HWND parent;
    HWND child;
    HANDLE process;
    DWORD process_id;
    unsigned int discovery_ticks;
    RECT rect;
    // Fresh per-launch test profile; never automatically deleted. May be
    // non-empty after a failed launch if directory creation already succeeded.
    wchar_t profile[MAX_PATH];
    BOOL selected;
    EmbedStatus status;
    EmbedStatus before_close;
    DWORD error;
} EmbedHost;

// parent is the Qt top-level native HWND; rect is in parent CLIENT physical
// pixels. The Qt caller must map/clip its viewport and update it on DPI,
// geometry and visibility changes. All operations on a given EmbedHost must
// be serialized. Window operations belong on the UI thread; an isolated copy
// with no process may be passed to embed_start on a worker and handed back
// only after that worker has finished, as in the experimental Qt adapter.
BOOL embed_init(EmbedHost *host, HWND parent);
BOOL embed_set_rect(EmbedHost *host, const RECT *rect);
BOOL embed_select(EmbedHost *host, BOOL selected);

// Starts only the exact restricted probe binary, once at a time. directory is
// its absolute folder, containing the expected resources/app.asar. The input
// is never modified. Each attempt creates a new temporary Electron user-data
// directory after hash verification; inability to create it aborts the launch.
// This is not a filesystem/security sandbox. Failure does not launch an
// alternative executable. Test profiles are retained, including after failure.
BOOL embed_start(EmbedHost *host, const wchar_t *directory);

// Poll from a UI timer every 100 ms. Timeout retains the process handle and
// disallows duplicates. Exit releases the handle and transitions to IDLE, or
// CLOSED if a close was requested; CLOSED cannot be restarted.
void embed_poll(EmbedHost *host);

// Requests hiding and graceful close of a verified attached window; never kills
// a process. If still discovering, polling continues discovery while closing,
// attaches hidden and posts WM_CLOSE once if a window appears before timeout.
// FALSE means process still tracked: do NOT destroy parent or discard host.
// A failed PostMessage is recorded in error; status still becomes CLOSING.
// Poll and call again until TRUE. An unattached process must be closed by the
// user; this operation intentionally does not target unverified windows.
// Hiding uses asynchronous Win32 calls and is not a visibility guarantee.
// embed_select and embed_set_rect return FALSE if the visibility request could
// not be queued; TRUE does not mean the requested visibility has taken effect.
BOOL embed_request_close(EmbedHost *host);

// Abandon a pending shell close without dropping the process handle. Returns
// FALSE if close is no longer pending or the process wait cannot be verified.
// A previously posted WM_CLOSE cannot be recalled: the cleaner may still exit.
// A caller must keep polling and notify the user; this does not guarantee that
// the embedded window survives. Never permits restart while a process is held.
BOOL embed_cancel_close(EmbedHost *host);

#ifdef __cplusplus
}
#endif
#endif
