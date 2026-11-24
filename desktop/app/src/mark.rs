// SPDX-License-Identifier: GPL-3.0-or-later
//! The Sa6i Link mark: the laptop, the phone and the swap arrows inside the
//! violet-blue swoosh, on the dark Sa6i tile. It is pre-rendered at the sizes
//! the executable's icon, the tray, the taskbar and the notifications use, so
//! the shipped art is the supplied brand artwork rather than a redrawing of
//! it. Any other size is a box-filtered reduction of the nearest stored one.
//!
//! `desktop/app/assets/mark/<size>.rgba` holds straight-alpha RGBA, row by
//! row; regenerate the files with the same crop as `assets/brand/icon-512.png`
//! when the artwork changes. `build.rs` includes this file to write the
//! executable's `.ico`, so the icon and the runtime icons never drift apart.

/// The stored sizes, smallest first.
const SIZES: [usize; 10] = [16, 20, 24, 32, 40, 48, 64, 128, 256, 512];

static ART: [&[u8]; 10] = [
    include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/assets/mark/16.rgba")),
    include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/assets/mark/20.rgba")),
    include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/assets/mark/24.rgba")),
    include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/assets/mark/32.rgba")),
    include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/assets/mark/40.rgba")),
    include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/assets/mark/48.rgba")),
    include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/assets/mark/64.rgba")),
    include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/assets/mark/128.rgba")),
    include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/assets/mark/256.rgba")),
    include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/assets/mark/512.rgba")),
];

/// Renders the mark as straight-alpha RGBA, row by row, `size`×`size`.
pub fn render(size: usize) -> Vec<u8> {
    if size == 0 {
        return Vec::new();
    }
    if let Some(index) = SIZES.iter().position(|&s| s == size) {
        return ART[index].to_vec();
    }
    // The smallest stored size that is still at least as large, so a reduction
    // never invents detail; beyond the largest, enlarge the largest.
    let index = SIZES.iter().position(|&s| s >= size).unwrap_or(SIZES.len() - 1);
    let source = SIZES[index];
    if source > size { downscale(ART[index], source, size) } else { upscale(ART[index], source, size) }
}

/// Averages the source box behind each target pixel ("area" reduction).
fn downscale(source: &[u8], from: usize, to: usize) -> Vec<u8> {
    let mut out = vec![0u8; to * to * 4];
    for y in 0..to {
        let y0 = y * from / to;
        let y1 = ((y + 1) * from / to).max(y0 + 1);
        for x in 0..to {
            let x0 = x * from / to;
            let x1 = ((x + 1) * from / to).max(x0 + 1);
            let mut sums = [0u32; 4];
            let mut count = 0u32;
            for sy in y0..y1 {
                for sx in x0..x1 {
                    let i = (sy * from + sx) * 4;
                    for c in 0..4 {
                        sums[c] += source[i + c] as u32;
                    }
                    count += 1;
                }
            }
            let o = (y * to + x) * 4;
            for c in 0..4 {
                out[o + c] = (sums[c] / count) as u8;
            }
        }
    }
    out
}

/// Nearest-neighbour enlargement, for the rare icon larger than 512 px.
fn upscale(source: &[u8], from: usize, to: usize) -> Vec<u8> {
    let mut out = vec![0u8; to * to * 4];
    for y in 0..to {
        let sy = y * from / to;
        for x in 0..to {
            let sx = x * from / to;
            let i = (sy * from + sx) * 4;
            let o = (y * to + x) * 4;
            out[o..o + 4].copy_from_slice(&source[i..i + 4]);
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_stored_size_is_a_full_square() {
        for (index, &size) in SIZES.iter().enumerate() {
            assert_eq!(ART[index].len(), size * size * 4, "{size}px");
        }
    }

    #[test]
    fn the_corners_are_clear_and_the_middle_is_ink() {
        let size = 64;
        let img = render(size);
        assert_eq!(img.len(), size * size * 4);
        let alpha = |x: usize, y: usize| img[(y * size + x) * 4 + 3];
        assert_eq!(alpha(0, 0), 0, "rounded corner");
        assert_eq!(alpha(size - 1, size - 1), 0, "rounded corner");
        assert_eq!(alpha(size / 2, size / 2), 255, "the devices");
    }

    #[test]
    fn other_sizes_are_reduced_from_a_stored_one() {
        for size in [18, 25, 96, 200, 1024] {
            let img = render(size);
            assert_eq!(img.len(), size * size * 4, "{size}px");
            assert!(img.chunks(4).any(|p| p[3] == 255), "{size}px has ink");
        }
    }
}
