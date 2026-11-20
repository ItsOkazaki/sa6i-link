// SPDX-License-Identifier: GPL-3.0-or-later
#include "host_lifecycle.h"
#include <assert.h>
#include <stdio.h>

static void success_and_switch(void) {
    HostLifecycle s = {HOST_IDLE, 0};
    assert(host_transition(&s, HOST_SELECT_CLEAN) == HOST_LAUNCH);
    assert(host_transition(&s, HOST_SELECT_CLEAN) == HOST_NO_ACTION);
    assert(host_transition(&s, HOST_LAUNCH_OK) == HOST_KEEP_TRACKING);
    assert(host_transition(&s, HOST_SELECT_HOME) == HOST_NO_ACTION);
    assert(host_transition(&s, HOST_ATTACH_OK) == (HOST_KEEP_TRACKING | HOST_HIDE));
    assert(host_transition(&s, HOST_SELECT_CLEAN) == HOST_SHOW);
    assert(host_transition(&s, HOST_SELECT_HOME) == HOST_HIDE);
    assert(host_transition(&s, HOST_REQUEST_CLOSE) == (HOST_REQUEST_CHILD_CLOSE | HOST_KEEP_TRACKING));
    assert(host_transition(&s, HOST_PROCESS_EXITED) == (HOST_RELEASE_PROCESS | HOST_CLOSE_SHELL));
    assert(s.phase == HOST_CLOSED);
}

static void timeout_still_tracks(void) {
    HostLifecycle s = {HOST_IDLE, 0};
    assert(host_transition(&s, HOST_SELECT_CLEAN) == HOST_LAUNCH);
    assert(host_transition(&s, HOST_LAUNCH_OK) == HOST_KEEP_TRACKING);
    assert(host_transition(&s, HOST_DISCOVERY_TIMEOUT) == HOST_KEEP_TRACKING);
    assert(host_transition(&s, HOST_SELECT_CLEAN) == HOST_KEEP_TRACKING);
    assert(host_transition(&s, HOST_PROCESS_EXITED) == HOST_RELEASE_PROCESS);
    assert(host_transition(&s, HOST_SELECT_CLEAN) == HOST_LAUNCH);
    assert(host_transition(&s, HOST_LAUNCH_ERROR) == HOST_NO_ACTION);
    assert(s.phase == HOST_IDLE);
}

static void failure_close_and_invalid(void) {
    HostLifecycle s = {HOST_IDLE, 0};
    assert(host_transition(&s, HOST_ATTACH_OK) == HOST_INVALID_EVENT);
    assert(host_transition(&s, HOST_SELECT_CLEAN) == HOST_LAUNCH);
    assert(host_transition(&s, HOST_LAUNCH_OK) == HOST_KEEP_TRACKING);
    assert(host_transition(&s, HOST_ATTACH_ERROR) == HOST_KEEP_TRACKING);
    assert(host_transition(&s, HOST_REQUEST_CLOSE) == HOST_KEEP_TRACKING);
    assert(host_transition(&s, HOST_SELECT_CLEAN) == HOST_INVALID_EVENT);
    assert(host_transition(&s, HOST_PROCESS_EXITED) == (HOST_RELEASE_PROCESS | HOST_CLOSE_SHELL));
    assert(host_transition(&s, HOST_SELECT_CLEAN) == HOST_INVALID_EVENT);
}

static void child_loss_does_not_relaunch(void) {
    HostLifecycle s = {HOST_IDLE, 0};
    host_transition(&s, HOST_SELECT_CLEAN);
    host_transition(&s, HOST_LAUNCH_OK);
    host_transition(&s, HOST_ATTACH_OK);
    assert(host_transition(&s, HOST_CHILD_LOST) == HOST_KEEP_TRACKING);
    assert(host_transition(&s, HOST_SELECT_CLEAN) == HOST_KEEP_TRACKING);
    assert(host_transition(&s, HOST_PROCESS_EXITED) == HOST_RELEASE_PROCESS);
    assert(s.phase == HOST_IDLE);
}

static void close_during_launch(void) {
    HostLifecycle s = {HOST_IDLE, 0};
    assert(host_transition(&s, HOST_SELECT_CLEAN) == HOST_LAUNCH);
    assert(host_transition(&s, HOST_REQUEST_CLOSE) == HOST_NO_ACTION);
    assert(s.phase == HOST_CLOSING_LAUNCH);
    assert(host_transition(&s, HOST_SELECT_CLEAN) == HOST_INVALID_EVENT);
    assert(host_transition(&s, HOST_LAUNCH_OK) == HOST_KEEP_TRACKING);
    assert(s.phase == HOST_CLOSING);
    assert(host_transition(&s, HOST_PROCESS_EXITED) == (HOST_RELEASE_PROCESS | HOST_CLOSE_SHELL));
    s.phase = HOST_IDLE;
    assert(host_transition(&s, HOST_SELECT_CLEAN) == HOST_LAUNCH);
    assert(host_transition(&s, HOST_REQUEST_CLOSE) == HOST_NO_ACTION);
    assert(host_transition(&s, HOST_LAUNCH_ERROR) == HOST_CLOSE_SHELL);
    assert(s.phase == HOST_CLOSED);
}

int main(void) {
    success_and_switch(); timeout_still_tracks(); failure_close_and_invalid(); child_loss_does_not_relaunch(); close_during_launch();
    puts("host lifecycle model tests passed");
    return 0;
}
