# Cataclysm: DDA tileset mixer
A set of Python scripts for combining several Cataclysm: DDA tilesets into one.

## Get started

```shell
python -m venv .venv
source .venv/bin/activate
pip install pyvips
```

pyvips needs the libvips library on your system. If you do not want to install it separately, install the bundled binaries instead:

```shell
pip install "pyvips[binary]"
```

## Workflow
1. Decompose every source tileset

Each source tileset is a folder that contains tile_config.json, tileset.txt and the sheet PNGs. Put the tilesets you want to use in this repository (or any working folder) and run decompose.py once per tileset:

```shell
python decompose.py path/to/Tileset
```

2. Build the merged folder

Create a new empty folder (for example mixed/) and put the following into it:

The pngs_* folders you want from each decomposed tileset. Sprite file names must be unique across the whole merged folder, otherwise compose.py reports duplicate root name. Also make sure two tilesets do not provide a sheet folder with the same name that you do not intend to merge.
tileset.txt with a non-empty JSON: key, which is the name of the generated config file. 

For example:
```shell
NAME: UNDEAD_PEOPLE_PLUS_MS_TEST
VIEW: UNDEAD_PEOPLE_PLUS_MS_TEST
JSON: tile_config.json
TILESET: tiles.png
```

tile_info.json that lists the sheets in the order they should be composed (see the example below).
fallback.png (the fallback sheet; it is not composed, only referenced, so it has to be copied by hand for now).

Example tile_info.json. The first entry holds the global sprite size; each following entry names a sheet and its options:

```json
[
  { "width": 32, "height": 32, "pixelscale": 1 },
  { "tiles.png": {} },
  { "large_tiles.png": { "sprite_width": 64, "sprite_height": 64 } },
  { "filler.png": { "filler": true } },
  { "fallback.png": { "fallback": true } }
]
```

3. Run the pipeline

<b>Without --apply nothing is executed or changed</b>:

```shell
python run_tileset_pipeline.py mixed/
```

Then run it for real:

```shell
python run_tileset_pipeline.py mixed/ --apply
```

Before changing anything, --apply makes full backups named <folder>_backup_<timestamp> next to the source folder (and next to the output folder if it already exists and is separate). Stage 1 modifies the source folder in place (renames files, edits JSON, deletes orphaned PNGs), which is why the backup matters.

To see only the cleanup report without changing anything, run the cleanup script alone (it is read-only without --apply):

```shell
python cleanup_for_compose.py mixed
```

4. Use the result

The output folder (the source folder if you did not pass an output folder) now contains the generated tile_config.json, the composed sheet PNGs, tileset.txt and fallback.png. Copy that folder into the game's gfx/ directory and select the tileset in the game options.

## Known issues and TODO

Known issue:
decompose.py produces an empty pngs_big_80x64 folder for the MShockXotto+ tileset.

TODO:
- Script that renames sprite files with duplicate names
- Script that generates tile_info.json with correct sheet names
- Fix pngs_big_80x64 for MShockXotto+ (the folder is empty after decompose.py)
- Copy fallback.png into the merged folder automatically