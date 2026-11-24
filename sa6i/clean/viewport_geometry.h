// SPDX-License-Identifier: GPL-3.0-or-later
// Qt-independent mapping of an axis-aligned scene rectangle to client pixels.
#ifndef SA6I_VIEWPORT_GEOMETRY_H
#define SA6I_VIEWPORT_GEOMETRY_H

#ifdef __cplusplus
extern "C" {
#endif

typedef struct { double x, y; } ViewPoint;
typedef struct { int left, top, right, bottom; } ViewPixels;

// Corners are Qt mapToScene() results: top-left, top-right, bottom-left,
// bottom-right. dpr is the QQuickWindow devicePixelRatio and client dimensions
// are physical pixels from GetClientRect. Computes an INWARD-rounded,
// client-clipped rectangle. Rotation, mirroring, skew, invalid/non-finite
// input and non-positive DPR are rejected. Empty clipped areas are valid.
// This does not account for arbitrary ancestor clipping, occlusion or another
// process's DPI awareness; the Qt owner must independently handle those.
int viewport_to_client(const ViewPoint corners[4], double dpr,
                       int client_width, int client_height, ViewPixels *out);
#ifdef __cplusplus
}
#endif
#endif
