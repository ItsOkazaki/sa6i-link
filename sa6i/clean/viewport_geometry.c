// SPDX-License-Identifier: GPL-3.0-or-later
#include "viewport_geometry.h"
#include <math.h>

static double clamp(double value, double max) {
    if (value < 0.0) return 0.0;
    if (value > max) return max;
    return value;
}

int viewport_to_client(const ViewPoint p[4], double dpr,
                       int width, int height, ViewPixels *out) {
    const double epsilon = 1e-7;
    double left, right, top, bottom;
    if (!p || !out || width < 0 || height < 0 || !isfinite(dpr) || dpr <= 0) return 0;
    for (int i = 0; i < 4; ++i)
        if (!isfinite(p[i].x) || !isfinite(p[i].y)) return 0;
    // Only an upright axis-aligned quadrilateral is supported. A visible
    // native child cannot accurately follow Qt rotations, mirroring or skew.
    if (fabs(p[0].y - p[1].y) > epsilon || fabs(p[2].y - p[3].y) > epsilon ||
        fabs(p[0].x - p[2].x) > epsilon || fabs(p[1].x - p[3].x) > epsilon ||
        p[1].x < p[0].x || p[2].y < p[0].y) return 0;
    left = p[0].x * dpr; right = p[1].x * dpr;
    top = p[0].y * dpr; bottom = p[2].y * dpr;
    if (!isfinite(left) || !isfinite(right) || !isfinite(top) || !isfinite(bottom)) return 0;
    left = ceil(clamp(left, width)); right = floor(clamp(right, width));
    top = ceil(clamp(top, height)); bottom = floor(clamp(bottom, height));
    // Subpixel-only intersections are empty, not negative rectangles.
    if (right < left) right = left;
    if (bottom < top) bottom = top;
    out->left = (int)left; out->right = (int)right;
    out->top = (int)top; out->bottom = (int)bottom;
    return 1;
}
