// SPDX-License-Identifier: GPL-3.0-or-later
#include "../viewport_geometry.h"
#include <assert.h>
#include <limits.h>
#include <math.h>
#include <stdio.h>

static void expect(const ViewPoint *p, double dpr, int w, int h, ViewPixels expected) {
    ViewPixels got = {-1,-1,-1,-1};
    assert(viewport_to_client(p, dpr, w, h, &got));
    assert(got.left == expected.left && got.top == expected.top &&
           got.right == expected.right && got.bottom == expected.bottom);
}
int main(void) {
    ViewPoint p[4] = {{10,20},{810,20},{10,620},{810,620}};
    expect(p, 1, 1000, 800, (ViewPixels){10,20,810,620});
    expect(p, 1.25, 1000, 800, (ViewPixels){13,25,1000,775});
    ViewPoint clipped[4] = {{-10,-20},{10,-20},{-10,10},{10,10}};
    expect(clipped, 1.5, 100, 100, (ViewPixels){0,0,15,15});
    ViewPoint outside[4] = {{-50,0},{-10,0},{-50,20},{-10,20}};
    expect(outside, 1, 200, 200, (ViewPixels){0,0,0,20});
    ViewPoint tiny[4] = {{1.1,1.1},{1.4,1.1},{1.1,1.4},{1.4,1.4}};
    expect(tiny, 1, 100, 100, (ViewPixels){2,2,2,2});
    ViewPixels out;
    p[1].y = 21; assert(!viewport_to_client(p, 1, 1000, 800, &out)); // skew
    p[1].y = 20; p[1].x = 5; p[3].x = 5;
    assert(!viewport_to_client(p, 1, 1000, 800, &out)); // mirror
    p[1].x = p[3].x = 810; p[0].x = NAN;
    assert(!viewport_to_client(p, 1, 1000, 800, &out));
    p[0].x = p[2].x = 1e308; p[1].x = p[3].x = 1e308;
    assert(!viewport_to_client(p, 100, 1000, 800, &out)); // multiplication overflow
    assert(!viewport_to_client(NULL, 1, 1, 1, &out));
    assert(!viewport_to_client(p, NAN, 1, 1, &out));
    assert(!viewport_to_client(p, 0, 1, 1, &out));
    assert(!viewport_to_client(p, 1, -1, 1, &out));
    assert(!viewport_to_client(p, 1, 1, 1, NULL));
    ViewPoint large[4] = {{0,0},{INT_MAX,0},{0,INT_MAX},{INT_MAX,INT_MAX}};
    expect(large, 1, INT_MAX, INT_MAX, (ViewPixels){0,0,INT_MAX,INT_MAX});
    puts("viewport geometry tests passed");
}
