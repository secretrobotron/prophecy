#!/usr/bin/env python3
"""
Build stories.yml of Pentateuch source assignments (J/E/P/D)
by scraping Wikiversity: "Sources by Chapter and Verse".

Usage:
  python build_stories_yml.py --output stories.yml
  python build_stories_yml.py --explode --output stories_exploded.yml
"""

import re
import sys
import argparse
from collections import defaultdict

import requests
from bs4 import BeautifulSoup
import yaml

URL = "https://en.wikiversity.org/wiki/Sources_by_Chapter_and_Verse"

BOOK_MAP = {
    "Gen": "Genesis",
    "Exo": "Exodus",
    "Lev": "Leviticus",
    "Num": "Numbers",
    "Deu": "Deuteronomy",
}

SOURCE_HEADINGS = [
    (r"Jahwist", "J"),
    (r"Elohist", "E"),
    (r"Priestly", "P"),
    (r"Deuteronomist", "D"),
]

# Matches things like:
#   2:4b-4:26
#   7:1-5
#   7:10
#   7:13a
#   14:1-19
RANGE_TOKEN = r"\d+:\d+[a-z]?(\s*-\s*\d+(?::\d+)?[a-z]?)?"
RANGE_SPLIT = re.compile(r",\s*")
BOOK_LINE = re.compile(r"^(Gen|Exo|Lev|Num|Deu)\s+(.*)$")
SPACES = re.compile(r"\s+")

def clean_text(s: str) -> str:
    s = s.replace("\xa0", " ")
    s = SPACES.sub(" ", s).strip()
    # drop footnote asterisks or stray bullets
    s = s.replace("*", "")
    return s


def normalize_range_format(range_str: str) -> str:
    """
    Normalize range format to standard chapter:verse-chapter:verse format.
    
    Examples:
        '1:1-7' -> '1:1-1:7'  (same chapter)
        '2:4b-26' -> '2:4b-2:26'  (same chapter with suffix)
        '1:1-2:7' -> '1:1-2:7'  (cross chapter, already correct)
    """
    if '-' not in range_str:
        # Single verse, no normalization needed
        return range_str
        
    start, end = range_str.split('-', 1)
    
    # If end doesn't contain ':', it's a verse in the same chapter as start
    if ':' not in end:
        start_chapter = start.split(':')[0]
        end = f"{start_chapter}:{end}"
        
    return f"{start}-{end}"

def parse_bullet(txt: str, source_tag: str):
    """
    Parse a bullet like:
      'Gen 2:4b-4:26, 4:1-26'
    into (book='Genesis', ranges=['2:4b-4:26','4:1-26'], source='J')
    """
    txt = clean_text(txt)
    m = BOOK_LINE.match(txt)
    if not m:
        return None
    short_book, rest = m.groups()
    book = BOOK_MAP.get(short_book)
    if not book:
        return None

    # Split on commas, then normalize hyphen spacing
    parts = RANGE_SPLIT.split(rest)
    ranges = []
    for p in parts:
        p = p.strip()
        # normalize internal spaces around hyphens
        p = re.sub(r"\s*-\s*", "-", p)
        # quick sanity check: looks like X:Y or X:Y-Z[:Y]
        if re.fullmatch(RANGE_TOKEN, p):
            ranges.append(p)
        # Some items may contain commentary; try to extract ranges inside
        else:
            rngs = re.findall(RANGE_TOKEN, p)
            if rngs:
                ranges.extend(rngs)

    # Final cleanup: remove empties/dups while preserving order, and normalize format
    seen = set()
    clean_ranges = []
    for r in ranges:
        r = r.strip()
        if not r:
            continue
        # Normalize to standard format (e.g., "1:1-7" -> "1:1-1:7")
        r = normalize_range_format(r)
        if r not in seen:
            seen.add(r)
            clean_ranges.append(r)

    if not clean_ranges:
        return None
    return {"book": book, "ranges": clean_ranges, "source": source_tag, "full_line": txt}

def extract_source_list(soup: BeautifulSoup, heading_regex: str, tag: str):
    """
    Find the H2 whose text matches heading_regex, then collect all <li> items
    until the next H2.
    """
    h2s = soup.select("h2")
    target = None
    for h in h2s:
        text = clean_text(h.get_text(" "))
        if re.search(heading_regex, text, flags=re.I):
            target = h
            break
    if not target:
        return []

    items = []
    node = target.find_next_sibling()
    while node and node.name != "h2":
        if node.name in ("ul", "ol"):
            for li in node.select("li"):
                txt = clean_text(li.get_text(" "))
                if txt:
                    row = parse_bullet(txt, tag)
                    if row:
                        items.append(row)
        node = node.find_next_sibling()

    return items

def build_yaml(entries, explode=False):
    """
    Group entries so each YAML item represents
      (book, source, first_range) -> list of ranges
    unless explode=True (one range per item).
    """
    if explode:
        # one entry per single range
        out = {}
        for e in entries:
            book = e["book"]
            src = e["source"]
            for rng in e["ranges"]:
                key = f"{book} {rng} ({src})"
                out[key] = {"book": book, "verses": [rng], "source": src}
        return out

    # group by (book, source, first_range)
    grouped = defaultdict(lambda: {"book": None, "source": None, "verses": []})
    for e in entries:
        book = e["book"]
        src = e["source"]
        first = e["ranges"][0]
        key = (book, src, first)
        g = grouped[key]
        g["book"] = book
        g["source"] = src
        g["verses"].extend(e["ranges"])

    # stable keys
    out = {}
    for (book, src, first), row in sorted(grouped.items()):
        # dedupe while preserving order
        seen = set()
        verses = []
        for r in row["verses"]:
            if r not in seen:
                seen.add(r)
                verses.append(r)
        key = f"{book} {first} ({src})"
        out[key] = {"book": book, "verses": verses, "source": src}
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", "-o", default="stories.yml", help="YAML output path")
    ap.add_argument("--explode", action="store_true", help="One entry per single range")
    ap.add_argument("--url", default=URL, help="Override source URL if needed")
    args = ap.parse_args()

    resp = requests.get(args.url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    entries = []
    for regex, tag in SOURCE_HEADINGS:
        entries.extend(extract_source_list(soup, regex, tag))

    if not entries:
        print("No entries found. The page structure may have changed.", file=sys.stderr)
        sys.exit(2)

    yaml_obj = build_yaml(entries, explode=args.explode)

    with open(args.output, "w", encoding="utf-8") as f:
        yaml.safe_dump(yaml_obj, f, sort_keys=False, allow_unicode=True)

    print(f"Wrote {len(yaml_obj)} stories to {args.output}")

if __name__ == "__main__":
    main()
