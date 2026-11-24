#!/usr/bin/env python3
"""Fixes tile_config.json after compose.py (two known compose.py defects).

1. Single weighted variant: compose.py collapses a one-element list into the
   element itself, so "bg": [{"weight": 1, "sprite": 5}] becomes
   "bg": {"weight": 1, "sprite": 5}, which the game does not accept
   ("Invalid or misplaced field name bg"). The script wraps such objects
   back into a list.

2. Leaking filler duplicates: in entries with several IDs ("id": ["a","b","c"])
   compose.py removes duplicates from the list while iterating over that same
   list and skips every second one. As a result, some IDs from filler sheets
   remain in the file, and the game takes the LAST definition of an ID, so
   the filler overrides the winner. The script keeps the first definition of
   each ID (regular sheets come before filler) and removes the rest.

Usage:  python fix_tile_config.py path/to/tile_config.json
"""
import json, sys


def wrap(entry):
    n = 0
    for k in ("fg", "bg"):
        if isinstance(entry.get(k), dict):
            entry[k] = [entry[k]]
            n += 1
    for a in entry.get("additional_tiles") or []:
        n += wrap(a)
    return n


path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    data = json.load(f)

wrapped = removed_ids = dropped = 0
seen = set()
for sheet in data.get("tiles-new", []):
    kept = []
    for t in sheet.get("tiles", []):
        ids = t.get("id")
        lst = [ids] if isinstance(ids, str) else list(ids or [])
        if lst:
            new = []
            for i in lst:
                if i in seen:
                    removed_ids += 1
                else:
                    seen.add(i)
                    new.append(i)
            if not new:
                dropped += 1
                continue
            t["id"] = new if isinstance(ids, list) and len(new) > 1 else new[0] if len(new) == 1 else new
        wrapped += wrap(t)
        kept.append(t)
    sheet["tiles"] = kept

with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)
print(f"Fields wrapped into a list: {wrapped}")
print(f"Duplicate IDs removed: {removed_ids} (entries removed entirely: {dropped})")