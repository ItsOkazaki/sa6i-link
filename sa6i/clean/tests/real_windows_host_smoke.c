// SPDX-License-Identifier: GPL-3.0-or-later
// Runs the real Win32 embed backend against our inert synthetic child process.
// This is NOT a test of Qt, Electron, Sa6i Clean, Windows 7, or cleanup safety.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <wchar.h>
#include "native_embed.h"

static void pump(void)
{
    MSG message;
    while (PeekMessageW(&message, NULL, 0, 0, PM_REMOVE)) {
        TranslateMessage(&message);
        DispatchMessageW(&message);
    }
    Sleep(25);
}

static int wait_attached(EmbedHost *host)
{
    for (int i = 0; i < 400; ++i) {
        pump();
        embed_poll(host);
        if (host->status == EMBED_ATTACHED) return 1;
        if (host->status == EMBED_UNATTACHED || !host->process) return 0;
    }
    return 0;
}

static int wait_visible(EmbedHost *host, BOOL visible)
{
    for (int i = 0; i < 160; ++i) {
        pump();
        embed_poll(host);
        if (host->status != EMBED_ATTACHED) return 0;
        if (!!IsWindowVisible(host->child) == !!visible) return 1;
    }
    return 0;
}

static int wait_rect(EmbedHost *host, RECT wanted)
{
    for (int i = 0; i < 160; ++i) {
        RECT got;
        pump();
        embed_poll(host);
        if (host->status != EMBED_ATTACHED || !GetWindowRect(host->child, &got)) return 0;
        MapWindowPoints(HWND_DESKTOP, host->parent, (POINT *)&got, 2);
        if (EqualRect(&got, &wanted)) return 1;
    }
    return 0;
}

static int wait_closed(EmbedHost *host)
{
    for (int i = 0; i < 400; ++i) {
        pump();
        if (embed_request_close(host)) return host->status == EMBED_CLOSED && !host->process;
    }
    return 0;
}

int wmain(int argc, wchar_t **argv)
{
    if (argc != 2 && argc != 3) return 2;
    int reject = argc == 3 && wcscmp(argv[2], L"--reject") == 0;
    if (argc == 3 && !reject) return 2;
    HWND parent = CreateWindowExW(0, L"STATIC", L"Sa6i synthetic host test",
        WS_OVERLAPPEDWINDOW, 40, 40, 1000, 800, NULL, NULL, GetModuleHandleW(NULL), NULL);
    if (!parent) { fprintf(stderr, "Could not create parent: %lu\n", GetLastError()); return 1; }
    ShowWindow(parent, SW_SHOW);
    EmbedHost host = {0};
    RECT rect = {10, 20, 500, 350};
    int result = 1;
#define CHECK(condition, description) do { if (!(condition)) { \
    fprintf(stderr, "FAIL %s: status=%d error=%lu last=%lu\n", description, \
        (int)host.status, host.error, GetLastError()); goto done; } } while (0)
    CHECK(embed_init(&host, parent), "initialize host");
    CHECK(embed_set_rect(&host, &rect), "set viewport");
    CHECK(embed_select(&host, TRUE), "select viewport");
    if (reject) {
        CHECK(!embed_start(&host, argv[1]), "reject modified fixture");
        CHECK(host.error == ERROR_INVALID_DATA && !host.process, "hash mismatch must not launch");
        puts("PASS: modified fixture rejected");
        result = 0;
        goto done;
    }
    CHECK(embed_start(&host, argv[1]), "start fixture");
    CHECK(host.process && host.status == EMBED_DISCOVERING, "track process");
    CHECK(!embed_start(&host, argv[1]), "reject duplicate launch");
    CHECK(wait_attached(&host), "attach child window");
    CHECK(host.child && GetParent(host.child) == parent, "verify child parent");
    CHECK((GetWindowLongPtrW(host.child, GWL_STYLE) & WS_CHILD) != 0, "verify child style");
    CHECK(wait_visible(&host, TRUE), "initial display");
    CHECK(wait_rect(&host, rect), "initial geometry");
    CHECK(embed_select(&host, FALSE), "queue hide");
    CHECK(wait_visible(&host, FALSE), "hide child");
    CHECK(embed_select(&host, TRUE), "queue show");
    CHECK(wait_visible(&host, TRUE), "show child");
    rect.left = 25; rect.top = 30; rect.right = 650; rect.bottom = 475;
    CHECK(embed_set_rect(&host, &rect), "queue resize");
    CHECK(wait_rect(&host, rect), "resize child");
    CHECK(!embed_request_close(&host), "close waits for fixture exit");
    CHECK(wait_closed(&host), "close and reap fixture");
    CHECK(!embed_start(&host, argv[1]), "closed host cannot restart");
    puts("PASS: launch, attach, hide, show, resize, close");
    if (host.profile[0]) RemoveDirectoryW(host.profile);

    CHECK(embed_init(&host, parent), "reinitialize host");
    CHECK(embed_set_rect(&host, &rect), "set second viewport");
    CHECK(embed_start(&host, argv[1]), "second launch");
    CHECK(!embed_request_close(&host), "close during discovery");
    CHECK(wait_closed(&host), "discover and close during launch");
    puts("PASS: close during discovery");
    result = 0;
 done:
    // This process is an inert fixture created by this dedicated test. On
    // failure, end only that known fixture so the disposable CI job can exit.
    if (host.process) {
        TerminateProcess(host.process, 1);
        WaitForSingleObject(host.process, 5000);
        CloseHandle(host.process);
    }
    if (host.profile[0]) RemoveDirectoryW(host.profile);
    DestroyWindow(parent);
    return result;
}
