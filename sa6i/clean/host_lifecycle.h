// SPDX-License-Identifier: GPL-3.0-or-later
// Pure state model for an experimental host; no Windows or Qt operations.
#ifndef SA6I_CLEAN_HOST_LIFECYCLE_H
#define SA6I_CLEAN_HOST_LIFECYCLE_H

typedef enum {
    HOST_IDLE, HOST_LAUNCHING, HOST_DISCOVERING, HOST_EMBEDDED,
    HOST_UNATTACHED, HOST_CLOSING_LAUNCH, HOST_CLOSING, HOST_CLOSED
} HostPhase;

typedef enum {
    HOST_SELECT_CLEAN, HOST_SELECT_HOME, HOST_LAUNCH_OK, HOST_LAUNCH_ERROR,
    HOST_ATTACH_OK, HOST_ATTACH_ERROR, HOST_DISCOVERY_TIMEOUT,
    HOST_CHILD_LOST, HOST_PROCESS_EXITED, HOST_REQUEST_CLOSE
} HostEvent;

enum HostAction {
    HOST_NO_ACTION = 0,
    HOST_LAUNCH = 1 << 0,
    HOST_SHOW = 1 << 1,
    HOST_HIDE = 1 << 2,
    HOST_REQUEST_CHILD_CLOSE = 1 << 3,
    HOST_KEEP_TRACKING = 1 << 4,
    HOST_RELEASE_PROCESS = 1 << 5,
    HOST_CLOSE_SHELL = 1 << 6,
    HOST_INVALID_EVENT = 1 << 7
};

typedef struct {
    HostPhase phase;
    int clean_selected;
} HostLifecycle;

// The caller retains the real process handle until HOST_RELEASE_PROCESS and
// must never treat this model as proof that Windows operations succeeded.
unsigned int host_transition(HostLifecycle *state, HostEvent event);
#endif
