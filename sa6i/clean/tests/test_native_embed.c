// SPDX-License-Identifier: GPL-3.0-or-later
// Deterministic simulation of Win32 calls, not a Windows integration test.
#include <assert.h>
#include <stdio.h>
#include <wchar.h>
#ifdef SA6I_SLOW_TEST
#include <stdatomic.h>
#include <time.h>
static atomic_int hold_reads, read_waiting;
#endif
#include "../native_embed.c"

#define PARENT ((HWND)(uintptr_t)1)
#define CHILD ((HWND)(uintptr_t)2)
#define CONTAINER ((HWND)(uintptr_t)7)
#define FILE_EXE ((HANDLE)(uintptr_t)3)
#define FILE_ASAR ((HANDLE)(uintptr_t)4)
#define PROCESS ((HANDLE)(uintptr_t)5)
#define THREAD ((HANDLE)(uintptr_t)6)

static DWORD last_error, hash_kind;
static int exe_reads, asar_reads, process_alive, child_exists, window_available;
static int fail_hash, fail_launch, fail_parent, fail_post, fail_wait, fail_show, launch_count, close_messages;
static int fail_temp, invalid_temp, fail_mkdir, force_collision, process_closed, layout_count, last_show, child_parented;
static int show_requests, last_command_theme;
static int container_exists, container_visible, container_destroyed, fail_container, fail_container_position;
static RECT child_rect;
static int made_count;
static wchar_t made_profiles[16][MAX_PATH];
static LONG_PTR style = WS_POPUP | WS_CAPTION | WS_THICKFRAME;
static RECT last_rect;
static void reset_mock(void) {
    last_error = hash_kind = 0;
    exe_reads = asar_reads = process_alive = child_exists = window_available = 0;
    fail_hash = fail_launch = fail_parent = fail_post = fail_wait = fail_show = launch_count = close_messages = 0;
    fail_temp = invalid_temp = fail_mkdir = force_collision = process_closed = layout_count = last_show = child_parented = 0;
    show_requests = 0; last_command_theme = 0;
    container_exists = container_visible = container_destroyed = fail_container = fail_container_position = 0;
    child_rect = (RECT){0,0,0,0};
    made_count = 0;
    style = WS_POPUP | WS_CAPTION | WS_THICKFRAME;
}

BOOL IsWindow(HWND w) { return w == PARENT || (w == CHILD && child_exists) || (w == CONTAINER && container_exists); }
BOOL IsWindowVisible(HWND w) { return w == CHILD && window_available; }
HWND GetWindow(HWND w, unsigned int cmd) { (void)w; (void)cmd; return NULL; }
HWND GetParent(HWND w) {
    if (w == CONTAINER && container_exists) return PARENT;
    return w == CHILD && child_parented ? CONTAINER : NULL;
}
DWORD GetWindowThreadProcessId(HWND w, DWORD *pid) { *pid = w == CHILD && child_exists ? 42 : 0; return 1; }
DWORD WaitForSingleObject(HANDLE h, DWORD t) {
    (void)t; assert(h == PROCESS);
    if (fail_wait) { last_error = 6; return (DWORD)-1; }
    return process_alive ? WAIT_TIMEOUT : WAIT_OBJECT_0;
}
BOOL GetClientRect(HWND w, RECT *r) { assert(w == PARENT); *r = (RECT){0,0,1000,800}; return TRUE; }
HWND CreateWindowExW(DWORD ex, LPCWSTR cls, LPCWSTR title, DWORD s, int x, int y, int w, int h,
                     HWND parent, HANDLE menu, HANDLE instance, void *param) {
    (void)ex; (void)title; (void)x; (void)y; (void)w; (void)h; (void)menu; (void)instance; (void)param;
    assert(!wcscmp(cls, L"STATIC") && parent == PARENT && (s & WS_CHILD) && (s & WS_CLIPCHILDREN));
    if (fail_container) { last_error = ERROR_ACCESS_DENIED; return NULL; }
    assert(!container_exists); container_exists = 1; return CONTAINER;
}
BOOL DestroyWindow(HWND w) {
    assert(w == CONTAINER && container_exists);
    assert(!child_parented || !process_alive); // never destroy a live foreign child
    container_exists = container_visible = 0; ++container_destroyed; return TRUE;
}
BOOL SetWindowPos(HWND w, HWND after, int x, int y, int width, int height, unsigned int flags) {
    (void)after; assert(w == CHILD || (w == CONTAINER && container_exists));
    if (w == CONTAINER) {
        if (fail_container_position && !(flags & SWP_HIDEWINDOW)) {
            last_error = ERROR_ACCESS_DENIED;
            return FALSE;
        }
        if (!(flags & SWP_NOMOVE)) { last_rect = (RECT){x,y,x+width,y+height}; ++layout_count; }
        if (flags & SWP_SHOWWINDOW) container_visible = 1;
        if (flags & SWP_HIDEWINDOW) container_visible = 0;
    } else if (!(flags & SWP_NOMOVE)) child_rect = (RECT){x,y,x+width,y+height};
    return TRUE;
}
BOOL ShowWindowAsync(HWND w, int show) {
    assert(w == CHILD);
    if (fail_show) { if (fail_show == 1) last_error = ERROR_ACCESS_DENIED; return FALSE; }
    last_show = show;
    if (show == SW_SHOWNA) ++show_requests;
    return TRUE;
}
DWORD GetTempPathW(DWORD size, LPWSTR out) {
    if (fail_temp) { last_error = ERROR_ACCESS_DENIED; return 0; }
    const wchar_t *path = invalid_temp == 1 ? L"relative\\" : invalid_temp == 2 ? L"C:\\bad\"quote\\" :
                          L"C:\\Users\\Test User\\Temp\\";
    DWORD length = (DWORD)wcslen(path);
    if (size <= length) return length + 1;
    wcscpy(out, path);
    return length;
}
DWORD GetCurrentProcessId(void) { return 123; }
BOOL CreateDirectoryW(LPCWSTR path, void *security) {
    (void)security;
    if (fail_mkdir) { last_error = ERROR_ACCESS_DENIED; return FALSE; }
    if (force_collision) { last_error = ERROR_ALREADY_EXISTS; return FALSE; }
    for (int i = 0; i < made_count; ++i) {
        if (!wcscmp(path, made_profiles[i])) { last_error = ERROR_ALREADY_EXISTS; return FALSE; }
    }
    assert(made_count < 16 && wcslen(path) < MAX_PATH);
    wcscpy(made_profiles[made_count++], path);
    return TRUE;
}
HANDLE CreateFileW(LPCWSTR path, DWORD access, DWORD share, void *a, DWORD create, DWORD flags, HANDLE template) {
    (void)access; (void)share; (void)a; (void)create; (void)flags; (void)template;
    if (wcsstr(path, CLEAN_EXE_NAME + 1)) { exe_reads = 0; return FILE_EXE; }
    if (wcsstr(path, L"resources\\app.asar")) { asar_reads = 0; return FILE_ASAR; }
    last_error = 2; return INVALID_HANDLE_VALUE;
}
BOOL ReadFile(HANDLE f, void *out, DWORD length, DWORD *n, void *overlapped) {
    (void)length; (void)overlapped;
#ifdef SA6I_SLOW_TEST
    if (atomic_load(&hold_reads)) {
        const struct timespec pause = {0, 1000000};
        atomic_store(&read_waiting, 1);
        while (atomic_load(&hold_reads)) nanosleep(&pause, NULL);
    }
#endif
    int *reads = f == FILE_EXE ? &exe_reads : &asar_reads;
    if ((*reads)++ == 0) { *(BYTE *)out = f == FILE_EXE ? 1 : 2; *n = 1; }
    else *n = 0;
    return TRUE;
}
BOOL CloseHandle(HANDLE h) { if (h == PROCESS) ++process_closed; return TRUE; }
BOOL CreateProcessW(LPCWSTR exe, LPWSTR command, void *a, void *b, BOOL inherit, DWORD flags,
                    void *env, LPCWSTR dir, STARTUPINFOW *startup, PROCESS_INFORMATION *out) {
    (void)a; (void)b; (void)inherit; (void)flags; (void)env; (void)dir;
    assert(wcsstr(exe, CLEAN_EXE_NAME + 1));
    assert(startup->cb == sizeof(*startup) && made_count > 0);
    wchar_t expected[2 * MAX_PATH + 64];
    assert(swprintf(expected, sizeof(expected) / sizeof(expected[0]),
                    L"\"%ls\" \"--user-data-dir=%ls\"", exe, made_profiles[made_count - 1]) > 0);
    last_command_theme = wcsstr(command, L" --sa6i-theme-light") ? 1 :
                         wcsstr(command, L" --sa6i-theme-dark") ? 2 : 0;
    if (last_command_theme == 1) wcscat(expected, L" --sa6i-theme-light");
    else if (last_command_theme == 2) wcscat(expected, L" --sa6i-theme-dark");
    assert(wcscmp(command, expected) == 0);
    ++launch_count;
    if (fail_launch) { last_error = 193; return FALSE; }
    process_alive = 1; out->hProcess = PROCESS; out->hThread = THREAD; out->dwProcessId = 42;
    return TRUE;
}
int lstrlenW(LPCWSTR s) { return (int)wcslen(s); }
LPWSTR lstrcpyW(LPWSTR a, LPCWSTR b) { return wcscpy(a,b); }
LPWSTR lstrcatW(LPWSTR a, LPCWSTR b) { return wcscat(a,b); }
BOOL EnumWindows(BOOL (CALLBACK *callback)(HWND, LPARAM), LPARAM data) {
    if (window_available && child_exists) callback(CHILD, data);
    return TRUE;
}
LONG_PTR GetWindowLongPtrW(HWND w, int field) { assert(w == CHILD && field == GWL_STYLE); return style; }
LONG_PTR SetWindowLongPtrW(HWND w, int field, LONG_PTR value) {
    assert(w == CHILD && field == GWL_STYLE); LONG_PTR old = style; style = value; return old;
}
HWND SetParent(HWND child, HWND parent) {
    assert(child == CHILD && parent == CONTAINER && container_exists);
    if (fail_parent) { last_error = 5; return NULL; }
    child_parented = 1; return NULL; // Success may return NULL for a former top-level window.
}
void SetLastError(DWORD error) { last_error = error; }
DWORD GetLastError(void) { return last_error; }
BOOL PostMessageW(HWND w, unsigned int msg, uintptr_t wp, intptr_t lp) {
    (void)wp; (void)lp; assert(w == CHILD && msg == WM_CLOSE); ++close_messages;
    if (fail_post) { last_error = 5; return FALSE; }
    return TRUE;
}
BOOL CryptAcquireContextW(HCRYPTPROV *p, const wchar_t *container, const wchar_t *provider, DWORD type, DWORD flags) {
    (void)container; (void)provider; (void)type; (void)flags; *p = 1; return TRUE;
}
BOOL CryptCreateHash(HCRYPTPROV p, DWORD alg, uintptr_t key, DWORD flags, HCRYPTHASH *h) {
    (void)p; (void)alg; (void)key; (void)flags; *h = 1; return TRUE;
}
BOOL CryptHashData(HCRYPTHASH h, const BYTE *bytes, DWORD n, DWORD flags) {
    (void)h; (void)flags; assert(n == 1); hash_kind = bytes[0]; return TRUE;
}
BOOL CryptGetHashParam(HCRYPTHASH h, DWORD param, BYTE *out, DWORD *size, DWORD flags) {
    (void)h; (void)param; (void)flags; assert(*size == 32);
    memcpy(out, hash_kind == 1 ? expected_exe : expected_asar, 32);
    if (fail_hash) out[0] ^= 1;
    return TRUE;
}
BOOL CryptDestroyHash(HCRYPTHASH h) { (void)h; return TRUE; }
BOOL CryptReleaseContext(HCRYPTPROV p, DWORD flags) { (void)p; (void)flags; return TRUE; }

static EmbedHost fresh(void) {
    EmbedHost h; RECT rect = {10,20,800,600};
    reset_mock(); assert(embed_init(&h, PARENT)); assert(embed_set_rect(&h, &rect));
    return h;
}
static void normal(void) {
    EmbedHost h = fresh();
    assert(!embed_start(&h, L"relative")); assert(h.error == ERROR_INVALID_PARAMETER && !launch_count);
    fail_hash = 1; assert(!embed_start(&h, L"C:\\test")); assert(h.error == ERROR_INVALID_DATA && !launch_count);
    fail_hash = 0; assert(embed_select(&h, TRUE)); assert(embed_start(&h, L"C:\\test"));
    assert(!embed_start(&h, L"C:\\test") && launch_count == 1);
    child_exists = window_available = 1; embed_poll(&h);
    assert(h.status == EMBED_ATTACHED && child_parented && layout_count == 1);
    assert(last_rect.left == 10 && last_rect.top == 20 && last_rect.right == 800 && last_rect.bottom == 600);
    assert(h.container == CONTAINER && container_visible);
    assert(child_rect.left == 0 && child_rect.top == 0 && child_rect.right == 790 && child_rect.bottom == 580);
    assert(last_show == SW_SHOWNA && (style & WS_CHILD));
    assert(embed_select(&h, FALSE) && last_show == SW_HIDE && !container_visible);
    assert(embed_select(&h, TRUE) && last_show == SW_SHOWNA && container_visible);
    RECT bad = {0,0,1001,800}; assert(!embed_set_rect(&h, &bad));
    assert(last_show == SW_HIDE && embed_select(&h, TRUE) && last_show == SW_HIDE);
    RECT restored = {10,20,800,600}; assert(embed_set_rect(&h, &restored) && last_show == SW_SHOWNA);
    assert(!embed_request_close(&h) && close_messages == 1 && h.status == EMBED_CLOSING);
    assert(!embed_request_close(&h) && close_messages == 1);
    RECT during_close = {20,30,700,500};
    assert(embed_set_rect(&h, &during_close));
    assert(last_rect.left == 20 && last_rect.bottom == 500 && h.status == EMBED_CLOSING);
    assert(!embed_set_rect(&h, &bad) && last_show == SW_HIDE && h.status == EMBED_CLOSING);
    assert(embed_set_rect(&h, &restored) && last_show == SW_HIDE);
    process_alive = 0;
    assert(!embed_set_rect(&h, &restored) && h.status == EMBED_CLOSING && h.child == NULL);
    assert(embed_request_close(&h));
    assert(h.status == EMBED_CLOSED && process_closed == 1);
    assert(!h.container && !container_exists && container_destroyed == 1);
    assert(!embed_start(&h, L"C:\\test"));
}
static void isolated_profile_creation(void) {
    EmbedHost h = fresh();
    assert(!embed_start(&h, L"C:\\bad\"path") && !launch_count && !made_count);
    fail_temp = 1;
    assert(!embed_start(&h, L"C:\\test") && h.error == ERROR_ACCESS_DENIED && !made_count && !launch_count);
    fail_temp = 0; invalid_temp = 1;
    assert(!embed_start(&h, L"C:\\test") && h.error == ERROR_INVALID_PARAMETER && !made_count && !launch_count);
    invalid_temp = 2;
    assert(!embed_start(&h, L"C:\\test") && h.error == ERROR_INVALID_PARAMETER && !made_count && !launch_count);
    invalid_temp = 0; fail_mkdir = 1;
    assert(!embed_start(&h, L"C:\\test") && h.error == ERROR_ACCESS_DENIED && !made_count && !launch_count);
    fail_mkdir = 0; force_collision = 1;
    assert(!embed_start(&h, L"C:\\test") && h.error == ERROR_ALREADY_EXISTS && !made_count && !launch_count && !h.profile[0]);
    force_collision = 0; fail_hash = 1;
    assert(!embed_start(&h, L"C:\\test") && h.error == ERROR_INVALID_DATA && !made_count && !launch_count);
    fail_hash = 0; fail_launch = 1;
    assert(!embed_start(&h, L"C:\\test") && h.error == 193 && made_count == 1);
    assert(!wcscmp(h.profile, made_profiles[0])); // retained even after failure
    fail_launch = 0;
    assert(embed_start(&h, L"C:\\test") && made_count == 2);
    assert(wcscmp(made_profiles[0], made_profiles[1]) && !wcscmp(h.profile, made_profiles[1]));
    process_alive = 0; embed_poll(&h); assert(!h.process && h.status == EMBED_IDLE);
    assert(embed_start(&h, L"C:\\test") && made_count == 3);
    assert(wcscmp(made_profiles[1], made_profiles[2]));
    process_alive = 0; embed_poll(&h);
}
static void timeout(void) {
    EmbedHost h = fresh(); assert(embed_start(&h, L"C:\\test"));
    for (int i=0; i<150; ++i) embed_poll(&h);
    assert(h.status == EMBED_UNATTACHED && h.error == ERROR_TIMEOUT && h.process == PROCESS);
    assert(!embed_start(&h, L"C:\\test") && launch_count == 1);
    assert(!embed_request_close(&h) && close_messages == 0);
    process_alive = 0; embed_poll(&h); assert(h.status == EMBED_CLOSED && process_closed == 1);
}
static void failure(void) {
    EmbedHost h = fresh(); fail_launch = 1; assert(!embed_start(&h, L"C:\\test"));
    assert(h.status == EMBED_IDLE && h.error == 193 && !h.process);
    fail_launch = 0; assert(embed_start(&h, L"C:\\test"));
    child_exists = window_available = fail_parent = 1; embed_poll(&h);
    assert(h.status == EMBED_UNATTACHED && h.error == 5 && h.process == PROCESS);
    assert(style == (WS_POPUP | WS_CAPTION | WS_THICKFRAME));
    assert(!embed_start(&h, L"C:\\test") && launch_count == 2);
}
static void window_lost(void) {
    EmbedHost h = fresh(); assert(embed_start(&h, L"C:\\test"));
    child_exists = window_available = 1; embed_poll(&h); assert(h.status == EMBED_ATTACHED);
    child_exists = 0; embed_poll(&h);
    assert(h.status == EMBED_UNATTACHED && h.process == PROCESS);
    assert(!embed_start(&h, L"C:\\test"));
}
static void cancel_closing(void) {
    EmbedHost h = fresh();
    assert(!embed_cancel_close(&h));
    assert(embed_start(&h, L"C:\\test"));
    // Close while discovering, then keep window open and resume discovery.
    assert(!embed_request_close(&h) && h.status == EMBED_CLOSING);
    assert(embed_cancel_close(&h) && h.status == EMBED_DISCOVERING);
    child_exists = window_available = 1; embed_poll(&h);
    assert(h.status == EMBED_ATTACHED);
    assert(!embed_request_close(&h) && close_messages == 1);
    // An already-posted WM_CLOSE may still take effect after cancel.
    assert(embed_cancel_close(&h) && h.status == EMBED_ATTACHED && h.process == PROCESS);
    assert(!embed_start(&h, L"C:\\test") && launch_count == 1);
    assert(!embed_request_close(&h) && close_messages == 2);
    child_exists = 0;
    assert(embed_cancel_close(&h) && h.status == EMBED_UNATTACHED && h.process == PROCESS);
    assert(!embed_request_close(&h) && h.status == EMBED_CLOSING && close_messages == 2);
    fail_wait = 1; assert(!embed_cancel_close(&h));
    assert(h.status == EMBED_CLOSING && h.process == PROCESS && h.error == 6);
    fail_wait = 0; process_alive = 0;
    assert(!embed_cancel_close(&h));
    assert(h.status == EMBED_CLOSED && !h.process && process_closed == 1);
}
static void cancel_preserves_discovery_timeout_and_exit_tracking(void) {
    EmbedHost h = fresh(); assert(embed_start(&h, L"C:\\test"));
    for (int i = 0; i < 148; ++i) embed_poll(&h);
    assert(h.status == EMBED_DISCOVERING && h.discovery_ticks == 148);
    // request_close polls once; cancellation must not reset elapsed ticks.
    assert(!embed_request_close(&h));
    assert(embed_cancel_close(&h) && h.discovery_ticks == 149);
    embed_poll(&h); assert(h.status == EMBED_UNATTACHED && h.error == ERROR_TIMEOUT);
    assert(!embed_request_close(&h));
    assert(embed_cancel_close(&h) && h.status == EMBED_UNATTACHED);
    process_alive = 0; embed_poll(&h);
    assert(h.status == EMBED_IDLE && !h.process && process_closed == 1);
    assert(embed_start(&h, L"C:\\test") && launch_count == 2);
}
static void close_while_discovering(void) {
    EmbedHost h = fresh();
    assert(embed_select(&h, TRUE) && embed_start(&h, L"C:\\test"));
    assert(!embed_request_close(&h) && h.status == EMBED_CLOSING && !h.selected);
    assert(close_messages == 0 && h.before_close == EMBED_DISCOVERING);
    embed_poll(&h);
    assert(h.status == EMBED_CLOSING && close_messages == 0);
    child_exists = window_available = 1;
    embed_poll(&h);
    assert(h.status == EMBED_CLOSING && h.before_close == EMBED_ATTACHED);
    assert(child_parented && last_show == SW_HIDE && close_messages == 1 && h.process == PROCESS);
    embed_poll(&h); assert(close_messages == 1);
    assert(embed_cancel_close(&h) && h.status == EMBED_ATTACHED && h.process == PROCESS);
    assert(embed_select(&h, TRUE) && last_show == SW_SHOWNA);
    assert(!embed_request_close(&h) && last_show == SW_HIDE && close_messages == 2);
    process_alive = 0; assert(embed_request_close(&h) && h.status == EMBED_CLOSED);
}
static void close_at_discovery_does_not_queue_show(void) {
    EmbedHost h = fresh();
    assert(embed_select(&h, TRUE) && embed_start(&h, L"C:\\test"));
    // Window becomes visible immediately before request_close's own poll.
    child_exists = window_available = 1;
    assert(!embed_request_close(&h));
    assert(h.status == EMBED_CLOSING && h.before_close == EMBED_ATTACHED);
    assert(!h.selected && child_parented && last_show == SW_HIDE && show_requests == 0);
    assert(close_messages == 1 && h.process == PROCESS);
    process_alive = 0; assert(embed_request_close(&h));
}
static void closing_discovery_failure_retains_process(void) {
    EmbedHost h = fresh(); assert(embed_start(&h, L"C:\\test"));
    assert(!embed_request_close(&h));
    // Timeout is shared with discovery, and never grants close approval.
    for (int i = 0; i < 150; ++i) embed_poll(&h);
    assert(h.status == EMBED_CLOSING && h.before_close == EMBED_UNATTACHED);
    assert(h.error == ERROR_TIMEOUT && h.process == PROCESS && !close_messages);
    assert(embed_cancel_close(&h) && h.status == EMBED_UNATTACHED);
    process_alive = 0; embed_poll(&h); assert(!h.process);

    h = fresh(); assert(embed_start(&h, L"C:\\test"));
    assert(!embed_request_close(&h));
    child_exists = window_available = fail_parent = 1;
    embed_poll(&h);
    assert(h.status == EMBED_CLOSING && h.before_close == EMBED_UNATTACHED);
    assert(h.error == 5 && !close_messages && h.process == PROCESS);
    process_alive = 0; assert(embed_request_close(&h));

    h = fresh(); assert(embed_start(&h, L"C:\\test"));
    assert(!embed_request_close(&h));
    child_exists = window_available = fail_post = 1;
    embed_poll(&h);
    assert(h.status == EMBED_CLOSING && h.before_close == EMBED_ATTACHED);
    assert(h.error == 5 && close_messages == 1 && h.process == PROCESS);
    embed_poll(&h); assert(close_messages == 1);
    assert(embed_cancel_close(&h) && h.status == EMBED_ATTACHED);
    fail_post = 0; assert(!embed_request_close(&h) && close_messages == 2);
    process_alive = 0; assert(embed_request_close(&h));
}
static void visibility_failure_is_reported_and_tracking_is_retained(void) {
    EmbedHost h = fresh(); assert(embed_select(&h, TRUE) && embed_start(&h, L"C:\\test"));
    child_exists = window_available = 1; embed_poll(&h);
    assert(h.status == EMBED_ATTACHED && last_show == SW_SHOWNA);
    fail_show = 1;
    assert(!embed_select(&h, FALSE) && h.error == ERROR_ACCESS_DENIED);
    assert(!h.selected && h.process == PROCESS && h.status == EMBED_ATTACHED);
    assert(!container_visible); // The same-process clipping parent is hidden synchronously.
    assert(last_show == SW_SHOWNA); // A failed foreign hide cannot be assumed complete.
    fail_show = 2;
    assert(!embed_select(&h, FALSE) && h.error == ERROR_GEN_FAILURE);
    fail_show = 0;
    assert(embed_select(&h, FALSE) && last_show == SW_HIDE && h.process == PROCESS);
    fail_show = 1;
    assert(!embed_select(&h, TRUE) && h.error == ERROR_ACCESS_DENIED);
    assert(last_show == SW_HIDE && h.process == PROCESS); // show was not queued
    fail_show = 0;
    assert(!embed_request_close(&h) && close_messages == 1);
    process_alive = 0; assert(embed_request_close(&h));
}
static void container_position_failure_hides_and_keeps_tracking(void) {
    EmbedHost h = fresh();
    assert(embed_select(&h, TRUE) && embed_start(&h, L"C:\\test"));
    child_exists = window_available = 1; embed_poll(&h);
    assert(h.status == EMBED_ATTACHED && container_visible);
    fail_container_position = 1;
    assert(!embed_select(&h, TRUE) && h.error == ERROR_ACCESS_DENIED);
    assert(!container_visible && h.process == PROCESS && h.status == EMBED_ATTACHED);
    fail_container_position = 0;
    assert(!embed_request_close(&h));
    process_alive = 0;
    assert(embed_request_close(&h) && !container_exists);
}
static void container_creation_failure_keeps_tracking(void) {
    EmbedHost h = fresh();
    assert(embed_select(&h, TRUE) && embed_start(&h, L"C:\\test"));
    child_exists = window_available = fail_container = 1;
    embed_poll(&h);
    assert(h.status == EMBED_UNATTACHED && h.error == ERROR_ACCESS_DENIED);
    assert(!h.container && !container_exists && h.process == PROCESS && !child_parented);
    assert(!embed_request_close(&h));
    process_alive = 0;
    assert(embed_request_close(&h) && h.status == EMBED_CLOSED);
}
static void post_failure_can_cancel_and_retry(void) {
    EmbedHost h = fresh(); assert(embed_start(&h, L"C:\\test"));
    child_exists = window_available = 1; embed_poll(&h);
    fail_post = 1;
    assert(!embed_request_close(&h) && h.status == EMBED_CLOSING && h.error == 5);
    assert(!embed_request_close(&h) && close_messages == 1);
    assert(embed_cancel_close(&h) && h.status == EMBED_ATTACHED);
    fail_post = 0; assert(!embed_request_close(&h) && close_messages == 2);
    process_alive = 0; assert(embed_request_close(&h));
}
static void initial_theme_switches(void) {
    EmbedHost h = fresh(); h.initial_theme = 1;
    assert(embed_start(&h, L"C:\\test") && last_command_theme == 1);
    h = fresh(); h.initial_theme = 2;
    assert(embed_start(&h, L"C:\\test") && last_command_theme == 2);
    h = fresh(); h.initial_theme = 0;
    assert(embed_start(&h, L"C:\\test") && last_command_theme == 0);
}
int main(void) {
    initial_theme_switches(); normal(); isolated_profile_creation(); timeout(); failure(); window_lost(); cancel_closing();
    cancel_preserves_discovery_timeout_and_exit_tracking(); close_while_discovering();
    close_at_discovery_does_not_queue_show(); closing_discovery_failure_retains_process();
    visibility_failure_is_reported_and_tracking_is_retained();
    container_creation_failure_keeps_tracking(); container_position_failure_hides_and_keeps_tracking();
    post_failure_can_cancel_and_retry();
    puts("native backend simulation passed"); return 0;
}
