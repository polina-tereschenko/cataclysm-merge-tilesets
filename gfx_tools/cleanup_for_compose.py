#!/usr/bin/env python3
"""Cleans up the merged folder before compose.py.

Does three things (by default only shows what it would do; use --apply to write):
 1. PNGs with a dot in the name (e.g. 22441_.30810mag_0.png) are not seen by
    compose.py (suffixes != ['.png']) -> renames the dot to '_' and fixes
    the references.
 2. Removes references in fg/bg to sprites that do not exist on disk
    (compose drops them anyway, but complains with an ERROR).
 3. Duplicate IDs within regular (non-filler) sheets: in the game the LAST
    entry wins (cata_tiles.cpp: "Must overwrite existing tile"), while
    compose.py keeps the FIRST. So IDs that are redefined later are removed
    from the earlier entries.

Usage:
  python cleanup_for_compose.py <folder_with_tile_info.json>           # report only
  python cleanup_for_compose.py <folder_with_tile_info.json> --apply   # write changes
Make a copy of the folder first!
"""
import argparse, json, os, sys
from pathlib import Path


def load_sheets(src):
    info = json.load(open(src / "tile_info.json", encoding="utf-8"))
    g = info[0]
    sheets = []
    for e in info[1:]:
        (name, specs), = e.items()
        w = specs.get("sprite_width", g["width"])
        h = specs.get("sprite_height", g["height"])
        fb = bool(specs.get("fallback"))
        sheets.append(dict(
            name=name, fallback=fb,
            filler=(not fb) and bool(specs.get("filler")),
            dir=src / f"pngs_{name.split('.png')[0]}_{w}x{h}"))
    return sheets


def walk(d):
    """Same order as in compose.py: folders by path, files by name."""
    for root, _dirs, files in sorted(os.walk(d, followlinks=True), key=lambda t: t[0]):
        for f in sorted(files):
            yield Path(root) / f


def layer_names(layer):
    out = []
    if isinstance(layer, str):
        out.append(layer)
    elif isinstance(layer, list):
        for it in layer:
            if isinstance(it, dict):
                s = it.get("sprite")
                out += [s] if isinstance(s, str) else list(s or [])
            elif isinstance(it, str):
                out.append(it)
    return out


def entry_names(e):
    out = layer_names(e.get("fg")) + layer_names(e.get("bg"))
    for a in e.get("additional_tiles", []) or []:
        out += entry_names(a)
    return out


def fix_layer(layer, fn):
    """fn(name) -> new name or None (remove). Returns the new layer or None."""
    if layer is None:
        return None
    if isinstance(layer, str):
        return fn(layer)
    if not isinstance(layer, list):
        return layer                      # a number or something else: leave alone
    res = []
    for it in layer:
        if isinstance(it, dict):
            s = it.get("sprite")
            if isinstance(s, list):
                ns = [x for x in ((fn(n) if isinstance(n, str) else n) for n in s) if x not in (None, "")]
                if ns:
                    it["sprite"] = ns
                    res.append(it)
            elif isinstance(s, str):
                n = fn(s)
                if n:
                    it["sprite"] = n
                    res.append(it)
            else:
                res.append(it)
        elif isinstance(it, str):
            n = fn(it)
            if n:
                res.append(n)
        else:
            res.append(it)
    return res


def fix_entry(e, fn):
    changed = False
    for k in ("fg", "bg"):
        if k in e:
            new = fix_layer(e[k], fn)
            if new != e[k]:
                e[k] = new if new is not None else []
                changed = True
    for a in e.get("additional_tiles", []) or []:
        changed |= fix_entry(a, fn)
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--show", type=int, default=15, help="how many examples to show")
    a = ap.parse_args()
    src = a.src

    sheets = [s for s in load_sheets(src) if not s["fallback"]]
    for s in sheets:
        if not s["dir"].is_dir():
            print(f"WARNING: folder not found: {s['dir']}", file=sys.stderr)
    sheets = [s for s in sheets if s["dir"].is_dir()]

    # ---------- 1. PNGs with a dot in the name ----------
    all_pngs = {}
    for s in sheets:
        for p in walk(s["dir"]):
            if p.suffix == ".png":
                all_pngs[p] = p.stem
    taken = {p.stem for p in all_pngs if p.suffixes == [".png"]}
    rename, ren_map = [], {}
    for p, stem in all_pngs.items():
        if p.suffixes == [".png"]:
            continue
        new = stem.replace(".", "_")
        while new in taken:
            new += "_"
        taken.add(new)
        rename.append((p, p.with_name(new + ".png")))
        ren_map[stem] = new
    print(f"[1] PNGs with a dot in the name: {len(rename)}")
    for o, n in rename[:a.show]:
        print(f"    {o.name} -> {n.name}")
    existing = set(taken)

    # ---------- 1b. JSONs with a dot in the name (compose.py ignores them) ----------
    json_ren = []
    for s_ in sheets:
        for p in walk(s_["dir"]):
            if p.suffix == ".json" and p.suffixes != [".json"]:
                nw = p.with_name(p.name[:-5].replace(".", "_") + ".json")
                while nw.exists() or any(nw == n for _, n in json_ren):
                    nw = nw.with_name(nw.name[:-5] + "_.json")
                json_ren.append((p, nw))
    print(f"[1b] JSONs with a dot in the name (compose.py skips them): {len(json_ren)}")
    for o, n in json_ren[:a.show]:
        print(f"    {o.name} -> {n.name}")
    if a.apply:
        for o, n in json_ren:
            o.rename(n)
        if json_ren:
            print("    (renamed; run the script again for a full check)")

    # ---------- loading all JSONs ----------
    files = {}   # path -> (list_of_entries, was_list, sheet_index)
    order = []
    for si, s in enumerate(sheets):
        for p in walk(s["dir"]):
            if p.suffixes == [".json"]:
                data = json.load(open(p, encoding="utf-8"))
                was_list = isinstance(data, list)
                files[p] = ([x for x in (data if was_list else [data])], was_list, si)
                order.append(p)
    dirty = set()

    # ---------- 2. references to missing / renamed sprites ----------
    missing = {}

    def fn(name):
        if name in ren_map:
            name = ren_map[name]
        if name in existing:
            return name
        missing[name] = missing.get(name, 0) + 1
        return None

    for p in order:
        for e in files[p][0]:
            if isinstance(e, dict) and fix_entry(e, fn):
                dirty.add(p)
    print(f"[2] references to missing sprites (will be removed): {sum(missing.values())}, "
          f"unique names: {len(missing)}")
    for n in list(missing)[:a.show]:
        print(f"    {n}  (x{missing[n]})")

    # ---------- 2b. ID repeated within a single id list ----------
    in_list = 0
    for p in order:
        for e in files[p][0]:
            if isinstance(e, dict) and isinstance(e.get("id"), list):
                u = list(dict.fromkeys(e["id"]))
                if len(u) != len(e["id"]):
                    in_list += len(e["id"]) - len(u)
                    e["id"] = u if len(u) > 1 else u[0]
                    dirty.add(p)
    print(f"[2b] IDs repeated within a single id list (will be removed): {in_list}")

    # ---------- 3. duplicate IDs in regular sheets ----------
    main_idx = {i for i, s in enumerate(sheets) if not s["filler"]}
    occ = {}      # id -> position of the last definition
    pos = {}      # (path, i) -> sequence number
    n = 0
    for p in order:
        if files[p][2] not in main_idx:
            continue
        for i, e in enumerate(files[p][0]):
            if not isinstance(e, dict) or not (e.get("fg") or e.get("bg")):
                continue
            ids = e.get("id")
            ids = [ids] if isinstance(ids, str) else (ids or [])
            pos[(p, i)] = n
            for x in ids:
                occ[x] = n
            n += 1
    deleted, manual, trimmed = [], [], 0
    removed_names = set()
    for p in order:
        if files[p][2] not in main_idx:
            continue
        ents = files[p][0]
        for i, e in enumerate(ents):
            if (p, i) not in pos:
                continue
            ids = e.get("id")
            lst = [ids] if isinstance(ids, str) else list(ids or [])
            dups = [x for x in lst if occ[x] != pos[(p, i)]]
            if not dups:
                continue
            rest = [x for x in lst if x not in dups]
            if rest and lst[0] in dups and e.get("additional_tiles"):
                manual.append((p, lst, dups))
                continue
            dirty.add(p)
            if not rest:
                removed_names.update(entry_names(e))
                deleted.append((p, lst))
                ents[i] = None
            else:
                e["id"] = rest if len(rest) > 1 else rest[0]
                trimmed += 1
    print(f"[3] redefined IDs: entries removed entirely {len(deleted)}, "
          f"multi-ID entries with some IDs removed {trimmed}, need manual review {len(manual)}")
    for p, lst in deleted[:a.show]:
        print(f"    delete {p.relative_to(src)}: {lst}")
    for p, lst, dups in manual:
        print(f"    MANUAL: {p.relative_to(src)}: id={lst}, redefined={dups}")

    # sprites that nothing references anymore
    still = set()
    for p in order:
        for e in files[p][0]:
            if isinstance(e, dict):
                still.update(entry_names(e))
    orphans = []
    for p, stem in all_pngs.items():
        cur = ren_map.get(stem, stem)
        if cur in removed_names and cur not in still:
            orphans.append(p)
    print(f"    orphaned PNGs (will be deleted): {len(orphans)}")

    if not a.apply:
        print("\nThis is a report only. Add --apply to write changes.")
        return

    # ---------- writing ----------
    for o, nw in rename:
        o.rename(nw)
    for p in dirty:
        ents, was_list, _ = files[p]
        ents = [e for e in ents if e is not None]
        if not ents:
            p.unlink()
            continue
        with open(p, "w", encoding="utf-8") as f:
            json.dump(ents if was_list else ents[0], f, ensure_ascii=False)
    for p in orphans:
        q = p
        for o, nw in rename:
            if o == p:
                q = nw
        if q.exists():
            q.unlink()
    print(f"\nDone: JSONs modified {len(dirty)}, PNGs renamed {len(rename)}, "
          f"orphaned PNGs deleted {len(orphans)}.")


if __name__ == "__main__":
    main()