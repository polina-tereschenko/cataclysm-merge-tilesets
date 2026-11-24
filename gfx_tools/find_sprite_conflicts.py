#!/usr/bin/env python3
"""
Finds sprites (PNG files) that have the SAME file name in two tileset source
folders but DIFFERENT pixels. compose.py keeps only one sprite per root name,
so such a pair means one pack's JSON may end up using the other pack's image.

Usage:
    python3 find_sprite_conflicts.py PACK_A_DIR PACK_B_DIR [--filter REGEX]
    python3 find_sprite_conflicts.py MERGED_DIR            # duplicates inside one tree

Examples:
    python3 find_sprite_conflicts.py ./packA/pngs ./packB/pngs --filter "bed|sofa|couch|chair"

Requires Pillow:  pip install pillow
"""
import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image


def index_pngs(root: Path):
    found = defaultdict(list)
    for p in root.rglob("*.png"):
        found[p.stem].append(p)
    return found


def pixels(path: Path):
    im = Image.open(path).convert("RGBA")
    return im.size, im.tobytes()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dir_a", type=Path)
    ap.add_argument("dir_b", type=Path, nargs="?")
    ap.add_argument("--filter", default=None, help="regex on the file name (stem)")
    args = ap.parse_args()
    rx = re.compile(args.filter) if args.filter else None

    a = index_pngs(args.dir_a)

    if args.dir_b is None:
        print(f"Duplicate names inside {args.dir_a}:")
        n = 0
        for stem, paths in sorted(a.items()):
            if len(paths) > 1 and (rx is None or rx.search(stem)):
                n += 1
                print(f"  {stem}")
                for p in paths:
                    print(f"      {p}")
        print(f"{n} duplicated name(s)")
        return 0

    b = index_pngs(args.dir_b)
    common = sorted(set(a) & set(b))
    same = 0
    differ = []
    for stem in common:
        if rx is not None and not rx.search(stem):
            continue
        if pixels(a[stem][0]) == pixels(b[stem][0]):
            same += 1
        else:
            differ.append(stem)

    print(f"Names present in both packs: {len(common)}")
    print(f"  identical image: {same}")
    print(f"  DIFFERENT image: {len(differ)}")
    for stem in differ:
        print(f"    {stem}")
        print(f"        A: {a[stem][0]}")
        print(f"        B: {b[stem][0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())