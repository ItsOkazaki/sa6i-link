// SPDX-License-Identifier: GPL-3.0-or-later
// Expose the existing fake-Win32 simulation to the QtCore adapter test.
// This compiles the real native_embed.c against fake Win32/crypto functions.
#define main native_backend_simulation_main
#include "test_native_embed.c"
#undef main

void simulation_reset(void) {
    reset_mock();
#ifdef SA6I_SLOW_TEST
    atomic_store(&hold_reads, 0); atomic_store(&read_waiting, 0);
#endif
}
#ifdef SA6I_SLOW_TEST
void simulation_block_reads(void) { atomic_store(&read_waiting, 0); atomic_store(&hold_reads, 1); }
int simulation_read_waiting(void) { return atomic_load(&read_waiting); }
void simulation_release_reads(void) { atomic_store(&hold_reads, 0); }
#endif
void simulation_make_window(void) { child_exists = window_available = 1; }
void simulation_exit(void) { process_alive = 0; }
int simulation_starts(void) { return launch_count; }
int simulation_last_theme(void) { return last_command_theme; }
int simulation_last_software(void) { return last_command_software; }
int simulation_close_messages(void) { return close_messages; }
int simulation_show(void) { return last_show; }
int simulation_show_requests(void) { return show_requests; }
long simulation_rect_left(void) { return last_rect.left; }
long simulation_rect_bottom(void) { return last_rect.bottom; }
void simulation_fail_launch(void) { fail_launch = 1; }
void simulation_set_fail_show(int mode) { fail_show = mode; }
