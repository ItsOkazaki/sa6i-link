// SPDX-License-Identifier: GPL-3.0-or-later
// Test-only bridge to instantiate the Qt adapter in a PySide test process.
#include "../qt_embed_adapter.h"
extern "C" {
QtEmbedAdapter *test_adapter_create() { return new QtEmbedAdapter; }
bool test_adapter_bind(QtEmbedAdapter *adapter) { return adapter && adapter->bindNativeParent(1); }
void test_adapter_destroy(QtEmbedAdapter *adapter) { delete adapter; }
}
