// SPDX-License-Identifier: GPL-3.0-or-later
// Experimental native backend for a future Qt host. Not a release component.
#include "native_embed.h"
#include <wincrypt.h>
#include <wchar.h>

#if defined(_WIN32) && !defined(SA6I_EMBED_TEST)
#include "sa6i_clean_config.h"
#endif
#ifndef SA6I_CLEAN_FULL_FIXTURE
#define SA6I_CLEAN_FULL_FIXTURE 0
#endif

#define DISCOVERY_TICKS 150
#if SA6I_CLEAN_FULL_FIXTURE
// Full cleaner: only selected at build time for a separate experiment. It
// retains destructive cleanup and management operations; not a sandbox.
#define CLEAN_EXE_NAME L"\\Sa6i Clean Integration.exe"
static const BYTE expected_exe[32] = {
    0x43,0x59,0x23,0xfe,0x5a,0x74,0x04,0xfe,0xef,0x6b,0xdf,0x24,0x2b,0x44,0x4d,0xda,
    0x5d,0xef,0x1a,0x05,0xd6,0x8a,0x72,0x00,0x38,0xe4,0x12,0x94,0x08,0x6d,0xbb,0x4e
};
static const BYTE expected_asar[32] = {
    0x62,0xb7,0x54,0x6a,0x12,0xdd,0xac,0x85,0xb6,0xfc,0x50,0x6b,0x0f,0xb1,0x51,0xac,
    0xd1,0x59,0x44,0xce,0x3a,0x80,0x9f,0x9f,0x4c,0x83,0x90,0x96,0x5e,0xf1,0x08,0x0a
};
#else
#define CLEAN_EXE_NAME L"\\Sa6i Clean Win7 Probe.exe"
static const BYTE expected_exe[32] = {
    0x88,0x39,0x33,0x44,0x9d,0x34,0x3d,0xec,0x59,0x25,0xe9,0x06,0x8c,0x7e,0x81,0x05,
    0x26,0x78,0xa1,0x86,0xaf,0x71,0x8f,0xf6,0xa0,0x7c,0x15,0xd6,0xbb,0xb3,0x8a,0xbe
};
static const BYTE expected_asar[32] = {
    0x33,0x62,0x40,0x3c,0x15,0xda,0xee,0x28,0x46,0xc5,0x9d,0xc4,0x80,0xb4,0x55,0xa3,
    0xe3,0xfa,0x3c,0x24,0x19,0xa5,0xb5,0xa0,0x89,0xff,0x6b,0x85,0xfe,0x38,0xda,0x44
};
#endif

static BOOL verify(HANDLE file, const BYTE expected[32]) {
    HCRYPTPROV provider = 0;
    HCRYPTHASH hash = 0;
    BYTE buffer[32768], digest[32];
    DWORD count, size = sizeof(digest);
    BOOL ok = FALSE;
    if (!CryptAcquireContextW(&provider, NULL, NULL, PROV_RSA_AES, CRYPT_VERIFYCONTEXT)) goto done;
    if (!CryptCreateHash(provider, CALG_SHA_256, 0, 0, &hash)) goto done;
    for (;;) {
        if (!ReadFile(file, buffer, sizeof(buffer), &count, NULL)) goto done;
        if (!count) break;
        if (!CryptHashData(hash, buffer, count, 0)) goto done;
    }
    if (!CryptGetHashParam(hash, HP_HASHVAL, digest, &size, 0) || size != sizeof(digest)) goto done;
    ok = TRUE;
    for (unsigned int i = 0; i < sizeof(digest); ++i) {
        if (digest[i] != expected[i]) { ok = FALSE; break; }
    }
 done:
    if (hash) CryptDestroyHash(hash);
    if (provider) CryptReleaseContext(provider, 0);
    return ok;
}

static BOOL owned_child(const EmbedHost *host) {
    DWORD pid = 0;
    if (!host->child || !IsWindow(host->child) || !host->process ||
        WaitForSingleObject(host->process, 0) != WAIT_TIMEOUT) return FALSE;
    GetWindowThreadProcessId(host->child, &pid);
    return pid == host->process_id && GetParent(host->child) == host->parent;
}

static BOOL place_child(EmbedHost *host) {
    if (!owned_child(host)) {
        host->error = ERROR_INVALID_WINDOW_HANDLE;
        if (host->status != EMBED_CLOSING) host->status = EMBED_UNATTACHED;
        host->child = NULL;
        return FALSE;
    }
    int width = host->rect.right - host->rect.left;
    int height = host->rect.bottom - host->rect.top;
    if (!SetWindowPos(host->child, NULL, host->rect.left, host->rect.top,
                      width, height, SWP_NOZORDER | SWP_NOACTIVATE | SWP_ASYNCWINDOWPOS)) {
        host->error = GetLastError();
        ShowWindowAsync(host->child, SW_HIDE);
        return FALSE;
    }
    SetLastError(0);
    if (!ShowWindowAsync(host->child, host->selected && width && height ? SW_SHOWNA : SW_HIDE)) {
        DWORD error = GetLastError();
        // ShowWindowAsync may not provide an extended error on failure.
        host->error = error ? error : ERROR_GEN_FAILURE;
        return FALSE;
    }
    // Success only means the visibility request was queued, not completed.
    return TRUE;
}

BOOL embed_init(EmbedHost *host, HWND parent) {
    if (!host || !parent || !IsWindow(parent)) return FALSE;
    ZeroMemory(host, sizeof(*host));
    host->parent = parent;
    host->status = EMBED_IDLE;
    return TRUE;
}

BOOL embed_set_rect(EmbedHost *host, const RECT *rect) {
    RECT client;
    if (!host || !rect || !IsWindow(host->parent) || !GetClientRect(host->parent, &client) ||
        rect->left < 0 || rect->top < 0 || rect->right < rect->left || rect->bottom < rect->top ||
        rect->right > client.right || rect->bottom > client.bottom) {
        if (host) {
            host->error = ERROR_INVALID_PARAMETER;
            // Forget stale coordinates so a later selection cannot show them.
            ZeroMemory(&host->rect, sizeof(host->rect));
            if ((host->status == EMBED_ATTACHED || host->status == EMBED_CLOSING) && owned_child(host))
                ShowWindowAsync(host->child, SW_HIDE);
        }
        return FALSE;
    }
    host->rect = *rect;
    // Closing can be indefinite; continue keeping the child within its viewport
    // even while waiting. An unattached closing process has no child to place.
    if (host->status == EMBED_ATTACHED || (host->status == EMBED_CLOSING && host->child))
        return place_child(host);
    return TRUE;
}

BOOL embed_select(EmbedHost *host, BOOL selected) {
    if (!host || host->status == EMBED_CLOSING || host->status == EMBED_CLOSED) return FALSE;
    host->selected = !!selected;
    if (host->status == EMBED_ATTACHED) return place_child(host);
    return TRUE;
}

// A newly created folder prevents accidental reuse of an existing Electron
// profile. The parent temp directory is not a security boundary; OS profile,
// downloads, network and other machine paths remain accessible to the app.
static BOOL make_test_profile(EmbedHost *host) {
    wchar_t temp[MAX_PATH], suffix[64];
    DWORD length = GetTempPathW(MAX_PATH, temp);
    if (!length || length >= MAX_PATH) {
        host->error = length ? ERROR_INVALID_PARAMETER : GetLastError();
        return FALSE;
    }
    if (length < 3 || temp[1] != L':' || (temp[2] != L'\\' && temp[2] != L'/') ||
        wcschr(temp, L'\"') || temp[length - 1] != L'\\' || length + 63 >= MAX_PATH) {
        host->error = ERROR_INVALID_PARAMETER;
        return FALSE;
    }
    for (unsigned int i = 0; i < 256; ++i) {
        int written = swprintf(suffix, sizeof(suffix) / sizeof(suffix[0]),
                               L"Sa6i-Clean-HostTest-%lu-%u", (unsigned long)GetCurrentProcessId(), i);
        if (written <= 0 || (unsigned int)written >= sizeof(suffix) / sizeof(suffix[0])) {
            host->error = ERROR_INVALID_PARAMETER;
            return FALSE;
        }
        lstrcpyW(host->profile, temp);
        lstrcatW(host->profile, suffix);
        if (CreateDirectoryW(host->profile, NULL)) return TRUE;
        DWORD error = GetLastError();
        host->profile[0] = L'\0';
        if (error != ERROR_ALREADY_EXISTS) { host->error = error; return FALSE; }
    }
    host->error = ERROR_ALREADY_EXISTS;
    return FALSE;
}

BOOL embed_start(EmbedHost *host, const wchar_t *directory) {
    wchar_t exe[MAX_PATH], asar[MAX_PATH], command[2 * MAX_PATH + 32];
    HANDLE exe_file = INVALID_HANDLE_VALUE, asar_file = INVALID_HANDLE_VALUE;
    STARTUPINFOW startup;
    PROCESS_INFORMATION process;
    BOOL ok = FALSE;
    DWORD length;
    if (!host || !directory || host->status != EMBED_IDLE || host->process || !IsWindow(host->parent)) return FALSE;
    host->profile[0] = L'\0';
    length = (DWORD) lstrlenW(directory);
    // Avoid path ambiguity and legacy Windows path-length problems.
    if (length < 3 || length + 32 >= MAX_PATH || directory[1] != L':' || wcschr(directory, L'\"') ||
        (directory[2] != L'\\' && directory[2] != L'/')) {
        host->error = ERROR_INVALID_PARAMETER;
        return FALSE;
    }
    lstrcpyW(exe, directory); lstrcatW(exe, CLEAN_EXE_NAME);
    lstrcpyW(asar, directory); lstrcatW(asar, L"\\resources\\app.asar");
    exe_file = CreateFileW(exe, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (exe_file == INVALID_HANDLE_VALUE) { host->error = GetLastError(); goto done; }
    asar_file = CreateFileW(asar, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (asar_file == INVALID_HANDLE_VALUE) { host->error = GetLastError(); goto done; }
    if (!verify(exe_file, expected_exe) || !verify(asar_file, expected_asar)) {
        host->error = ERROR_INVALID_DATA;
        goto done;
    }
    if (!make_test_profile(host)) goto done;
    // Both paths are drive-absolute, contain no quote and do not end in a
    // backslash. Quote each complete argument for Windows command parsing.
    lstrcpyW(command, L"\""); lstrcatW(command, exe);
    lstrcatW(command, L"\" \"--user-data-dir="); lstrcatW(command, host->profile);
    lstrcatW(command, L"\"");
    ZeroMemory(&startup, sizeof(startup)); ZeroMemory(&process, sizeof(process));
    startup.cb = sizeof(startup);
    if (!CreateProcessW(exe, command, NULL, NULL, FALSE, 0, NULL, directory, &startup, &process)) {
        host->error = GetLastError();
        goto done;
    }
    CloseHandle(process.hThread);
    host->process = process.hProcess;
    host->process_id = process.dwProcessId;
    host->discovery_ticks = 0;
    host->error = 0;
    host->status = EMBED_DISCOVERING;
    ok = TRUE;
 done:
    if (asar_file != INVALID_HANDLE_VALUE) CloseHandle(asar_file);
    if (exe_file != INVALID_HANDLE_VALUE) CloseHandle(exe_file);
    return ok;
}

static BOOL CALLBACK find_window(HWND window, LPARAM data) {
    EmbedHost *host = (EmbedHost *)data;
    DWORD pid = 0;
    GetWindowThreadProcessId(window, &pid);
    if (pid == host->process_id && IsWindowVisible(window) && !GetWindow(window, GW_OWNER)) {
        host->child = window;
        return FALSE;
    }
    return TRUE;
}

static void try_attach(EmbedHost *host) {
    LONG_PTR old_style;
    HWND previous;
    host->child = NULL;
    EnumWindows(find_window, (LPARAM)host);
    if (!host->child) {
        if (++host->discovery_ticks >= DISCOVERY_TICKS) {
            host->status = EMBED_UNATTACHED;
            host->error = ERROR_TIMEOUT;
        }
        return;
    }
    // Verify the process is still alive immediately before manipulating HWND.
    if (WaitForSingleObject(host->process, 0) != WAIT_TIMEOUT || !IsWindow(host->parent)) {
        host->child = NULL;
        host->status = EMBED_UNATTACHED;
        host->error = ERROR_INVALID_WINDOW_HANDLE;
        return;
    }
    SetLastError(0);
    old_style = GetWindowLongPtrW(host->child, GWL_STYLE);
    if (!old_style && GetLastError()) goto failed;
    SetLastError(0);
    if (!SetWindowLongPtrW(host->child, GWL_STYLE,
                           (old_style & ~(WS_POPUP | WS_CAPTION | WS_THICKFRAME)) | WS_CHILD) && GetLastError()) goto failed;
    SetLastError(0);
    previous = SetParent(host->child, host->parent);
    if (!previous && GetLastError()) {
        DWORD error = GetLastError();
        // Best effort rollback, only while the handle still belongs to our process.
        DWORD pid = 0;
        GetWindowThreadProcessId(host->child, &pid);
        if (pid == host->process_id) {
            SetWindowLongPtrW(host->child, GWL_STYLE, old_style);
            SetWindowPos(host->child, NULL, 0, 0, 0, 0,
                         SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED | SWP_ASYNCWINDOWPOS);
        }
        SetLastError(error);
        goto failed;
    }
    host->status = EMBED_ATTACHED;
    SetWindowPos(host->child, NULL, 0, 0, 0, 0,
                 SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED | SWP_ASYNCWINDOWPOS);
    place_child(host);
    return;
 failed:
    host->error = GetLastError();
    host->child = NULL;
    host->status = EMBED_UNATTACHED;
}

// Only ever target a window successfully attached to our tracked process.
static void post_attached_close(EmbedHost *host) {
    if (host->status == EMBED_ATTACHED && owned_child(host)) {
        if (!PostMessageW(host->child, WM_CLOSE, 0, 0)) host->error = GetLastError();
    }
}

void embed_poll(EmbedHost *host) {
    if (!host || !host->process) return;
    DWORD wait = WaitForSingleObject(host->process, 0);
    if (wait == WAIT_OBJECT_0) {
        CloseHandle(host->process);
        host->process = NULL;
        host->process_id = 0;
        host->child = NULL;
        host->status = host->status == EMBED_CLOSING ? EMBED_CLOSED : EMBED_IDLE;
        return;
    }
    if (wait != WAIT_TIMEOUT) {
        host->error = GetLastError();
        // Keep tracking even if the wait failed. Never start another process.
        if (host->status != EMBED_CLOSING) host->status = EMBED_UNATTACHED;
        return;
    }
    if (host->status == EMBED_DISCOVERING) try_attach(host);
    else if (host->status == EMBED_CLOSING && host->before_close == EMBED_DISCOVERING) {
        // A close can arrive before the first window exists, including while
        // the launch worker is running. Keep discovering under the same time
        // limit, attach hidden, then request close exactly once. Never approve
        // teardown until the process handle signals exit.
        try_attach(host);
        if (host->status == EMBED_ATTACHED) {
            post_attached_close(host);
            host->before_close = EMBED_ATTACHED;
            host->status = EMBED_CLOSING;
        } else if (host->status == EMBED_UNATTACHED) {
            host->before_close = EMBED_UNATTACHED;
            host->status = EMBED_CLOSING;
        }
    }
    else if (host->status == EMBED_ATTACHED && !owned_child(host)) {
        host->child = NULL;
        host->status = EMBED_UNATTACHED;
        host->error = ERROR_INVALID_WINDOW_HANDLE;
    }
}

BOOL embed_request_close(EmbedHost *host) {
    if (!host) return FALSE;
    // Clear selection before polling: that poll may discover and attach a
    // newly visible top-level window. If selection remained true until after
    // discovery, try_attach could queue a show immediately before the hide.
    // For an already attached child this also requests a hide before polling.
    // Both visibility and positioning requests are asynchronous on Win32.
    if (host->status != EMBED_CLOSING && host->status != EMBED_CLOSED)
        embed_select(host, FALSE);
    embed_poll(host);
    if (!host->process) {
        host->status = EMBED_CLOSED;
        return TRUE;
    }
    if (host->status == EMBED_CLOSING) return FALSE;
    host->before_close = host->status;
    post_attached_close(host);
    // No unverified window is targeted or process terminated. UI must wait or
    // ask the user to close an unattached process; do not destroy the parent.
    host->status = EMBED_CLOSING;
    return FALSE;
}

BOOL embed_cancel_close(EmbedHost *host) {
    DWORD wait;
    if (!host || host->status != EMBED_CLOSING || !host->process) return FALSE;
    wait = WaitForSingleObject(host->process, 0);
    if (wait == WAIT_OBJECT_0) {
        // Closing has completed; caller must not revive a closed host.
        embed_poll(host);
        return FALSE;
    }
    if (wait != WAIT_TIMEOUT) {
        host->error = GetLastError();
        return FALSE;
    }
    if (host->before_close == EMBED_ATTACHED && !owned_child(host)) {
        host->child = NULL;
        host->status = EMBED_UNATTACHED;
        host->error = ERROR_INVALID_WINDOW_HANDLE;
    } else if (host->before_close == EMBED_ATTACHED || host->before_close == EMBED_DISCOVERING ||
               host->before_close == EMBED_UNATTACHED) {
        host->status = host->before_close;
    } else {
        // Unknown prior state: hold the process, don't rediscover or relaunch.
        host->status = EMBED_UNATTACHED;
        host->error = ERROR_INVALID_DATA;
    }
    return TRUE;
}
