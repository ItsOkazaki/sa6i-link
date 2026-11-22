// SPDX-License-Identifier: GPL-3.0-or-later
//! The Sa6i Link mark (`assets/brand/icon.svg`): a violet-to-blue shield with
//! a four-point spark, on the dark Sa6i tile. It is the same shield family as
//! the Sa6i Clean icon, so the two windows read as one product. Drawn in code
//! at any pixel size: the tray, window and toast icons at runtime, and the
//! executable's icon at build time (`build.rs` includes this file), so every
//! size is sharp without bitmap assets. At 32 px and below the shield fills
//! more of the tile and the spark is larger, as in the hand-tuned small sizes.

/// The tile, from violet-black at the top to near-black at the bottom, and its
/// edge.
const TILE_TOP: [f32; 3] = rgb(0x1B, 0x0D, 0x33);
const TILE_BOTTOM: [f32; 3] = rgb(0x0B, 0x05, 0x16);
const RIM: [f32; 3] = rgb(0x3A, 0x2A, 0x5E);
/// The shield, left to right, its outline, and the spark inside it.
const SHIELD_LEFT: [f32; 3] = rgb(0x9B, 0x5C, 0xF0);
const SHIELD_RIGHT: [f32; 3] = rgb(0x2F, 0x7B, 0xFF);
const SHIELD_RIM: [f32; 3] = rgb(0x8B, 0x6C, 0xE8);
const SPARK: [f32; 3] = rgb(0xF2, 0xEE, 0xFF);

/// The shield in the 100×100 design grid, clockwise from the top point: a
/// crested top, straight sides, then the point at the bottom.
const SHIELD: [(f32, f32); 10] = [
    (50.0, 24.0),
    (73.0, 32.0),
    (73.0, 52.0),
    (71.0, 62.0),
    (63.0, 72.0),
    (50.0, 81.0),
    (37.0, 72.0),
    (29.0, 62.0),
    (27.0, 52.0),
    (27.0, 32.0),
];

/// Supersampling grid per pixel (SS×SS samples) for smooth edges.
const SS: usize = 4;

const fn rgb(r: u8, g: u8, b: u8) -> [f32; 3] {
    [r as f32, g as f32, b as f32]
}

/// Sizes in the design grid: the small sizes are drawn bolder.
struct Geometry {
    inset: f32,
    corner: f32,
    shield_scale: f32,
    spark_outer: f32,
    spark_inner: f32,
}

impl Geometry {
    fn for_size(size: usize) -> Self {
        if size <= 32 {
            Geometry { inset: 2.0, corner: 22.0, shield_scale: 1.12, spark_outer: 13.0, spark_inner: 3.4 }
        } else {
            Geometry { inset: 3.0, corner: 22.0, shield_scale: 1.0, spark_outer: 11.0, spark_inner: 2.6 }
        }
    }
}

/// Renders the mark as straight-alpha RGBA, row by row, `size`×`size`.
pub fn render(size: usize) -> Vec<u8> {
    let g = Geometry::for_size(size);
    let unit = 100.0 / size as f32;
    let shield: Vec<(f32, f32)> = SHIELD
        .iter()
        .map(|&(x, y)| (50.0 + (x - 50.0) * g.shield_scale, 50.0 + (y - 50.0) * g.shield_scale))
        .collect();
    let spark = spark_points(50.0, 50.0, g.spark_outer, g.spark_inner);
    // The rim is at least about a pixel wide, so the tile keeps an edge on dark taskbars.
    let rim = (1.2f32).max(unit * 0.5);

    let mut out = vec![0u8; size * size * 4];
    for py in 0..size {
        for px in 0..size {
            let mut color = [0f32; 3];
            let mut covered = 0usize;
            for sy in 0..SS {
                for sx in 0..SS {
                    // The sample in the design grid.
                    let x = (px as f32 + (sx as f32 + 0.5) / SS as f32) * unit;
                    let y = (py as f32 + (sy as f32 + 0.5) / SS as f32) * unit;
                    let edge = rounded_square_distance(x, y, g.inset, g.corner);
                    if edge > 0.0 {
                        continue;
                    }
                    covered += 1;
                    let backdrop = mix(TILE_TOP, TILE_BOTTOM, (y / 100.0).clamp(0.0, 1.0));
                    let paint = if polygon_distance(&shield, (x, y)) < 0.0 {
                        let across = ((x - 25.0) / 50.0).clamp(0.0, 1.0);
                        if polygon_distance(&spark, (x, y)) < 0.0 {
                            SPARK
                        } else {
                            mix(SHIELD_LEFT, SHIELD_RIGHT, across)
                        }
                    } else if polygon_distance(&shield, (x, y)) < rim {
                        mix(backdrop, SHIELD_RIM, 0.55)
                    } else if -edge <= rim {
                        mix(backdrop, RIM, 0.8)
                    } else {
                        backdrop
                    };
                    for c in 0..3 {
                        color[c] += paint[c];
                    }
                }
            }
            if covered == 0 {
                continue;
            }
            let i = (py * size + px) * 4;
            for c in 0..3 {
                out[i + c] = (color[c] / covered as f32).round() as u8;
            }
            out[i + 3] = ((covered as f32 / (SS * SS) as f32) * 255.0).round() as u8;
        }
    }
    out
}

fn mix(a: [f32; 3], b: [f32; 3], t: f32) -> [f32; 3] {
    [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]
}

/// A four-point spark: eight alternating radii, starting at the top point.
fn spark_points(cx: f32, cy: f32, outer: f32, inner: f32) -> Vec<(f32, f32)> {
    (0..8)
        .map(|i| {
            let angle = std::f32::consts::FRAC_PI_2 + i as f32 * std::f32::consts::FRAC_PI_4;
            let radius = if i % 2 == 0 { outer } else { inner };
            (cx + radius * angle.cos(), cy + radius * angle.sin())
        })
        .collect()
}

/// How far (x, y) is outside the rounded square from `inset` to
/// `100 - inset` with corner radius `r` (negative inside).
fn rounded_square_distance(x: f32, y: f32, inset: f32, r: f32) -> f32 {
    let half = 50.0 - inset;
    let qx = (x - 50.0).abs() - (half - r);
    let qy = (y - 50.0).abs() - (half - r);
    let ax = qx.max(0.0);
    let ay = qy.max(0.0);
    (ax * ax + ay * ay).sqrt() + qx.max(qy).min(0.0) - r
}

/// Signed distance to a closed polygon (negative inside), by the nearest edge
/// and a ray-cast parity test.
fn polygon_distance(points: &[(f32, f32)], p: (f32, f32)) -> f32 {
    let mut distance = f32::INFINITY;
    let mut inside = false;
    for (i, &a) in points.iter().enumerate() {
        let b = points[(i + 1) % points.len()];
        distance = distance.min(dist_to_segment(p, a, b));
        if (a.1 <= p.1) != (b.1 <= p.1)
            && p.0 < (b.0 - a.0) * (p.1 - a.1) / (b.1 - a.1) + a.0
        {
            inside = !inside;
        }
    }
    if inside { -distance } else { distance }
}

fn dist_to_segment(p: (f32, f32), a: (f32, f32), b: (f32, f32)) -> f32 {
    let (dx, dy) = (b.0 - a.0, b.1 - a.1);
    let len2 = dx * dx + dy * dy;
    let t = if len2 == 0.0 { 0.0 } else { (((p.0 - a.0) * dx + (p.1 - a.1) * dy) / len2).clamp(0.0, 1.0) };
    let (qx, qy) = (a.0 + t * dx, a.1 + t * dy);
    ((p.0 - qx).powi(2) + (p.1 - qy).powi(2)).sqrt()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pixel(img: &[u8], size: usize, x: usize, y: usize) -> [u8; 4] {
        let i = (y * size + x) * 4;
        [img[i], img[i + 1], img[i + 2], img[i + 3]]
    }

    #[test]
    fn corners_are_transparent_and_the_spark_sits_in_the_middle() {
        let size = 64;
        let img = render(size);
        assert_eq!(img.len(), size * size * 4);
        assert_eq!(pixel(&img, size, 0, 0)[3], 0, "rounded corner");
        assert_eq!(pixel(&img, size, 32, 32), [0xF2, 0xEE, 0xFF, 255], "the spark");
        // Near the top edge, above the shield: the dark tile.
        let tile = pixel(&img, size, 32, 8);
        assert!(tile[0] < 0x30 && tile[3] == 255, "{tile:?}");
    }

    #[test]
    fn the_shield_is_violet_on_the_left_and_blue_on_the_right() {
        let size = 128;
        let img = render(size);
        let left = pixel(&img, size, 42, 64);
        let right = pixel(&img, size, 86, 64);
        assert!(left[2] > 0xC0 && left[0] > right[0], "left {left:?}");
        assert!(right[2] > 0xC0 && right[2] > right[1], "right {right:?}");
    }

    #[test]
    fn renders_every_tray_size() {
        for size in [16, 20, 24, 32, 48, 64, 256] {
            let img = render(size);
            assert!(img.chunks(4).any(|p| p[3] == 255), "{size}px has an opaque tile");
        }
    }
}
