#!/usr/bin/env python3
"""Fixes the rotation order in corner / t_connection / end_piece (lists of 4 sprites).

Old Undead pack order (counterclockwise): corner [NW, SW, SE, NE], t_connection [N, W, S, E], end_piece [S, E, N, W].
Order the game expects (clockwise):       corner [NW, NE, SE, SW], t_connection [N, E, S, W], end_piece [S, W, N, E].
That is, elements 1 and 3 need to be swapped.

The script is IDEMPOTENT: the order is determined by the relative rank of the sprite numbers in the list.
  ranks (0,1,2,3) or (1,3,2,0)  -> old order     -> swap 1<->3
  ranks (0,3,2,1) or (1,0,2,3)  -> already new   -> skip
  anything else (repeats, atypical) -> leave untouched, list in the report
Only sheets BEFORE --stop-sheet are processed (default tiles.png, i.e. the main Undead pack).
Works with both lists of integers and weighted variants {"weight":..,"sprite":[4 numbers]}.

Usage:
  python fix_rotation_order.py tile_config.json [-o out.json] [--stop-sheet tiles.png] [--rotates] [--dry-run]
  --rotates  additionally sets "rotates": true for multitile entries f_* and t_*wall*
Without -o it overwrites the input file (and makes a .bak).
"""
import json, sys, shutil, argparse, collections

KEYS = ("corner", "t_connection", "end_piece")
OLD = {(0, 1, 2, 3), (1, 3, 2, 0)}
NEW = {(0, 3, 2, 1), (1, 0, 2, 3)}

def ranks(l):
    if len(set(l)) != 4:
        return None
    s = sorted(l)
    return tuple(s.index(x) for x in l)

def sw(l):
    return [l[0], l[3], l[2], l[1]]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("-o", "--out")
    ap.add_argument("--stop-sheet", default="tiles.png")
    ap.add_argument("--rotates", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    raw = open(a.config, encoding="utf-8").read()
    d = json.loads(raw)
    stat = collections.Counter()
    odd = collections.defaultdict(list)
    rot = 0
    main_part = True
    for s in d["tiles-new"]:
        if s["file"] == a.stop_sheet:
            main_part = False
        if not main_part:
            continue
        for e in s["tiles"]:
            if e.get("multitile") is not True:
                continue
            ids = e["id"] if isinstance(e["id"], list) else [e["id"]]
            if a.rotates and e.get("rotates") is False and any(
                    i.startswith("f_") or (i.startswith("t_") and "wall" in i) for i in ids):
                e["rotates"] = True
                rot += 1
            for sub in e.get("additional_tiles", []) or []:
                if sub.get("id") not in KEYS:
                    continue
                fg = sub.get("fg")
                holders = []  # (container, key) where the list of 4 sprites lives
                if isinstance(fg, list) and len(fg) == 4 and all(isinstance(x, int) for x in fg):
                    holders.append((sub, "fg"))
                elif isinstance(fg, list) and fg and all(isinstance(x, dict) for x in fg):
                    for v in fg:
                        sp = v.get("sprite")
                        if isinstance(sp, list) and len(sp) == 4 and all(isinstance(x, int) for x in sp):
                            holders.append((v, "sprite"))
                for cont, key in holders:
                    r = ranks(cont[key])
                    if r in OLD:
                        cont[key] = sw(cont[key]); stat["changed"] += 1
                    elif r in NEW:
                        stat["already in new order"] += 1
                    else:
                        stat["left untouched (atypical)"] += 1
                        odd[ids[0]].append((sub["id"], cont[key]))

    print("Sheets processed: up to", a.stop_sheet)
    for k, v in stat.items():
        print(f"  {k}: {v}")
    if a.rotates:
        print(f"  rotates false -> true: {rot}")
    if odd:
        print(f"Atypical (unchanged), {len(odd)} entries:")
        for i, lst in list(odd.items())[:40]:
            print("  ", i, lst[:2])
    if a.dry_run:
        print("Dry run, file not written."); return
    out = a.out or a.config
    if not a.out:
        shutil.copyfile(a.config, a.config + ".bak")
    with open(out, "w", encoding="utf-8") as f:
        f.write(json.dumps(d, indent=2, ensure_ascii=False) + ("\n" if raw.endswith("\n") else ""))
    print("Written:", out)

if __name__ == "__main__":
    main()