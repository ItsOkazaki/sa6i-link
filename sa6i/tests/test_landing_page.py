"""Basic local checks for the download page; not a network or device test."""

import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []
        self.images = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self.hrefs.append(attrs.get("href", ""))
        elif tag == "img":
            self.images.append(attrs.get("src", ""))


class LandingPageTests(unittest.TestCase):
    def test_download_links_and_local_assets(self):
        site = ROOT / "website"
        page = (site / "src/App.jsx").read_text(encoding="utf-8")
        parsed = Links()
        parsed.feed(page)
        self.assertIn("https://github.com/ItsOkazaki/sa6i-link-public/releases/download/download/Sa6i.Link.zip", parsed.hrefs)
        self.assertIn("https://github.com/ItsOkazaki/sa6i-link-public/releases/download/download/Sa6i.Link.apk", parsed.hrefs)
        self.assertTrue(all((site / "public" / path.lstrip("/")).is_file() for path in parsed.images))
        self.assertTrue((site / "styles.css").is_file())
        self.assertNotIn("Experimental builds", page)
        self.assertNotIn("TEST BUILD", page)
        self.assertNotIn("Arabic test", page)
        self.assertNotIn('className="notice"', page)
        self.assertIn("keep your original as a backup", page)
        self.assertIn("Not an installer", page)


if __name__ == "__main__":
    unittest.main()
