// SPDX-License-Identifier: GPL-3.0-or-later
#include "host_lifecycle.h"

unsigned int host_transition(HostLifecycle *s, HostEvent e) {
    if (!s) return HOST_INVALID_EVENT;
    if (e == HOST_SELECT_HOME) {
        if (s->phase == HOST_CLOSED || s->phase == HOST_CLOSING || s->phase == HOST_CLOSING_LAUNCH) return HOST_INVALID_EVENT;
        s->clean_selected = 0;
        return s->phase == HOST_EMBEDDED ? HOST_HIDE : HOST_NO_ACTION;
    }
    if (e == HOST_SELECT_CLEAN) {
        if (s->phase == HOST_CLOSED || s->phase == HOST_CLOSING || s->phase == HOST_CLOSING_LAUNCH) return HOST_INVALID_EVENT;
        s->clean_selected = 1;
        if (s->phase == HOST_IDLE) { s->phase = HOST_LAUNCHING; return HOST_LAUNCH; }
        if (s->phase == HOST_EMBEDDED) return HOST_SHOW;
        // Includes timeout/attach failure: do not launch a duplicate process.
        return s->phase == HOST_UNATTACHED ? HOST_KEEP_TRACKING : HOST_NO_ACTION;
    }
    switch (e) {
    case HOST_LAUNCH_OK:
        if (s->phase == HOST_CLOSING_LAUNCH) {
            s->phase = HOST_CLOSING;
            return HOST_KEEP_TRACKING;
        }
        if (s->phase != HOST_LAUNCHING) break;
        s->phase = HOST_DISCOVERING;
        return HOST_KEEP_TRACKING;
    case HOST_LAUNCH_ERROR:
        if (s->phase == HOST_CLOSING_LAUNCH) {
            s->phase = HOST_CLOSED;
            return HOST_CLOSE_SHELL;
        }
        if (s->phase != HOST_LAUNCHING) break;
        s->phase = HOST_IDLE;
        return HOST_NO_ACTION;
    case HOST_ATTACH_OK:
        if (s->phase != HOST_DISCOVERING) break;
        s->phase = HOST_EMBEDDED;
        return HOST_KEEP_TRACKING | (s->clean_selected ? HOST_SHOW : HOST_HIDE);
    case HOST_ATTACH_ERROR:
    case HOST_DISCOVERY_TIMEOUT:
        if (s->phase != HOST_DISCOVERING) break;
        s->phase = HOST_UNATTACHED;
        return HOST_KEEP_TRACKING;
    case HOST_CHILD_LOST:
        if (s->phase != HOST_EMBEDDED) break;
        s->phase = HOST_UNATTACHED;
        return HOST_KEEP_TRACKING;
    case HOST_PROCESS_EXITED:
        if (s->phase == HOST_DISCOVERING || s->phase == HOST_EMBEDDED || s->phase == HOST_UNATTACHED) {
            s->phase = HOST_IDLE;
            return HOST_RELEASE_PROCESS;
        }
        if (s->phase == HOST_CLOSING) {
            s->phase = HOST_CLOSED;
            return HOST_RELEASE_PROCESS | HOST_CLOSE_SHELL;
        }
        break;
    case HOST_REQUEST_CLOSE:
        if (s->phase == HOST_IDLE) { s->phase = HOST_CLOSED; return HOST_CLOSE_SHELL; }
        if (s->phase == HOST_EMBEDDED) {
            s->phase = HOST_CLOSING;
            return HOST_REQUEST_CHILD_CLOSE | HOST_KEEP_TRACKING;
        }
        if (s->phase == HOST_DISCOVERING || s->phase == HOST_UNATTACHED) {
            // Do not terminate or close an unverified external window.
            s->phase = HOST_CLOSING;
            return HOST_KEEP_TRACKING;
        }
        if (s->phase == HOST_LAUNCHING) {
            // Defer until launch result; never lose a newly created process.
            s->phase = HOST_CLOSING_LAUNCH;
            return HOST_NO_ACTION;
        }
        break;
    default: break;
    }
    return HOST_INVALID_EVENT;
}
