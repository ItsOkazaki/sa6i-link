// SPDX-License-Identifier: GPL-3.0-or-later
//! What this application is called, in the spellings other software uses.
//!
//! The product name has never had one form. The window calls itself "Sa6i Link",
//! the binary is `sa6i-link.exe`, the install folder is `Sa6iLink`, and Windows
//! paths differ from each other only by case. Anything that compares a name has to
//! accept all of them or it will decide that a thing is not itself: the notification
//! filter treats its own notifications as somebody else's, the installer puts a copy
//! of the app inside its own folder, and a photo's path is not under the root it was
//! taken from.
//!
//! So the comparison here is on a squashed form: lowercase, with the separators
//! (`-`, `_`, space) removed. `Sa6i Link`, `sa6i-link` and `Sa6iLink` all squash to
//! `sa6ilink`, which is the name this application has.

/// The name with case and separators removed, for comparisons that should not care
/// about them.
pub fn squashed(name: &str) -> String {
    name.chars()
        .filter(|c| !matches!(c, '-' | '_' | ' '))
        .flat_map(char::to_lowercase)
        .collect()
}

/// Whether `name` is this application, in any of its spellings.
///
/// Only Windows code compares a name today - the installer's folder and the exe's
/// path - so on the other platforms this is here for the tests and for the next
/// caller, and saying so keeps `-D warnings` happy on Linux.
#[cfg_attr(not(windows), allow(dead_code))]
pub fn is_own_name(name: &str) -> bool {
    squashed(name) == "sa6ilink"
}

/// Whether two path components name the same thing.
///
/// Windows paths differ by case, and the application's own folder differs by case
/// *and* separator - `Sa6iLink` on disk, `sa6i-link` in the path a caller hands us.
/// Every other component is compared the way Windows compares it: case-insensitively,
/// and nothing more, because squashing `my-photos` and `myphotos` together would make
/// two different folders one.
#[cfg_attr(not(windows), allow(dead_code))]
pub fn same_component(a: &str, b: &str) -> bool {
    a.to_lowercase() == b.to_lowercase() || (is_own_name(a) && is_own_name(b))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_spelling_of_the_product_name_is_the_product_name() {
        for name in ["Sa6i Link", "sa6i-link", "Sa6iLink", "sa6i_link", "SA6I-LINK"] {
            assert!(is_own_name(name), "{name} is this application");
        }
        for name in ["NectarLink", "Sa6i", "sa6i-link.exe", "Firefox", "Signal Desktop"] {
            assert!(!is_own_name(name), "{name} is not");
        }
    }

    #[test]
    fn two_components_name_the_same_thing_only_when_they_do() {
        assert!(same_component("Sa6iLink", "sa6i-link"));
        assert!(same_component("Photos", "PHOTOS"));
        // Squashing everything would make these one folder, and they are not.
        assert!(!same_component("my-photos", "myphotos"));
        assert!(!same_component("Sa6iLink", "NectarLink"));
    }
}
