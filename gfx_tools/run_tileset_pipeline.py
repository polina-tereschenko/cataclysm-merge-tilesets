#!/usr/bin/env python3
"""Sequentially runs the Cataclysm: DDA tileset preparation tools.

Expects four separate scripts next to it (or in --scripts-dir):
  cleanup_for_compose.py
  compose.py
  fix_rotation_order.py
  fix_tile_config.py

By default it only shows the plan. Use --apply to execute it.
With --apply, backups of source_dir and, if it is a separate existing
folder, output_dir are created automatically. Backups can be disabled
with --no-backup.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


SCRIPT_NAMES = (
    "cleanup_for_compose.py",
    "compose.py",
    "fix_rotation_order.py",
    "fix_tile_config.py",
)


def parse_tileset_json_name(source_dir: Path, output_dir: Path) -> str:
    """Reads the JSON key from tileset.txt the same way compose.py does."""
    for folder in (source_dir, output_dir):
        properties = folder / "tileset.txt"
        if not properties.is_file():
            continue
        try:
            lines = properties.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise RuntimeError(f"Failed to read {properties}: {exc}") from exc

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, _, value = line.partition(":")
            if key.strip() == "JSON" and value.strip():
                return value.strip()

    raise RuntimeError(
        "No non-empty 'JSON:' key found in tileset.txt "
        f"of the source or output folder ({source_dir}, {output_dir})."
    )


def resolve_config_path(json_name: str, output_dir: Path) -> Path:
    config = Path(json_name).expanduser()
    if not config.is_absolute():
        config = output_dir / config
    return config.resolve()


def make_backup(folder: Path, stamp: str) -> Optional[Path]:
    """Creates a full copy of the folder next to it; returns the path to the copy."""
    if not folder.exists():
        return None
    if not folder.is_dir():
        raise RuntimeError(f"Backup path is not a folder: {folder}")

    backup = folder.with_name(f"{folder.name}_backup_{stamp}")
    if backup.exists():
        raise RuntimeError(f"Backup folder already exists: {backup}")

    print(f"Creating backup: {backup}")
    shutil.copytree(folder, backup, symlinks=True)
    return backup


def is_inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def command_text(command: list[str]) -> str:
    # repr gives readable escaping of spaces and special characters on Windows/Linux.
    return " ".join(repr(part) for part in command)


def run_stage(title: str, command: list[str], apply: bool, cwd: Path) -> None:
    print(f"\n{'=' * 12} {title} {'=' * 12}")
    print(command_text(command))
    if not apply:
        return

    result = subprocess.run(command, cwd=str(cwd), check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"Stage '{title}' exited with code {result.returncode}. "
            "Subsequent stages were not run."
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Runs the four tileset preparation scripts sequentially."
    )
    parser.add_argument("source_dir", type=Path, help="Compositing tileset folder")
    parser.add_argument(
        "output_dir",
        nargs="?",
        type=Path,
        help="Output folder (defaults to source_dir)",
    )
    parser.add_argument(
        "--scripts-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Folder containing the four separate scripts (defaults to the runner's folder)",
    )
    parser.add_argument(
        "--stop-sheet",
        default="tiles.png",
        help="Sheet before which fix_rotation_order.py stops processing (default: tiles.png)",
    )
    parser.add_argument(
        "--rotates",
        action="store_true",
        help="Additionally set rotates=true for the relevant multitile entries",
    )
    parser.add_argument(
        "--compose-arg",
        action="append",
        default=[],
        metavar="ARG",
        help="Extra argument for compose.py; may be given multiple times",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute all stages. Without this flag only the plan is shown.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create full backups before making changes (not recommended)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    source_dir = args.source_dir.expanduser().resolve()
    output_dir = (args.output_dir or args.source_dir).expanduser().resolve()
    scripts_dir = args.scripts_dir.expanduser().resolve()

    if not source_dir.is_dir():
        print(f"ERROR: source folder does not exist: {source_dir}", file=sys.stderr)
        return 2
    if not output_dir.exists() and args.apply:
        # compose.py will create it itself, so this is not an error.
        pass
    elif output_dir.exists() and not output_dir.is_dir():
        print(f"ERROR: output path is not a folder: {output_dir}", file=sys.stderr)
        return 2

    scripts = {name: scripts_dir / name for name in SCRIPT_NAMES}
    missing = [str(path) for path in scripts.values() if not path.is_file()]
    if missing:
        print("ERROR: required separate scripts not found:", file=sys.stderr)
        for path in missing:
            print(f"  - {path}", file=sys.stderr)
        print(
            "Put the four scripts in one folder or pass it via --scripts-dir.\n"
            "The previously uploaded combined compose.py does not replace these four separate files.",
            file=sys.stderr,
        )
        return 2

    try:
        json_name = parse_tileset_json_name(source_dir, output_dir)
        config_path = resolve_config_path(json_name, output_dir)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.apply and not args.no_backup:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            source_backup = make_backup(source_dir, stamp)
            output_backup = None
            # If output_dir is already inside source_dir, its copy is already in the source backup.
            if output_dir.exists() and output_dir != source_dir and not is_inside(output_dir, source_dir):
                output_backup = make_backup(output_dir, stamp)
            print("Backups created:")
            if source_backup:
                print(f"  source: {source_backup}")
            if output_backup:
                print(f"  output: {output_backup}")
        except (OSError, RuntimeError) as exc:
            print(f"BACKUP ERROR: {exc}", file=sys.stderr)
            return 2

    py = sys.executable
    commands = [
        (
            "1/4 — cleaning up the input folder",
            [py, str(scripts["cleanup_for_compose.py"]), str(source_dir), "--apply"],
        ),
        (
            "2/4 — composing the tileset",
            [py, str(scripts["compose.py"]), str(source_dir)]
            + ([str(output_dir)] if output_dir != source_dir else [])
            + args.compose_arg,
        ),
        (
            "3/4 — fixing rotation order",
            [
                py,
                str(scripts["fix_rotation_order.py"]),
                str(config_path),
                "--stop-sheet",
                args.stop_sheet,
            ]
            + (["--rotates"] if args.rotates else []),
        ),
        (
            "4/4 — final tile_config.json fix",
            [py, str(scripts["fix_tile_config.py"]), str(config_path)],
        ),
    ]

    print("Source:  ", source_dir)
    print("Output:  ", output_dir)
    print("JSON:    ", config_path)

    try:
        for title, command in commands:
            run_stage(title, command, args.apply, Path.cwd())
    except (OSError, RuntimeError) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1

    if args.apply:
        print("\nDone: all four stages completed successfully.")
    else:
        print("\nThis is a preview. Add --apply for a real run.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())