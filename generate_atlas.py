"""Build the combat icon glyph atlas, its stylesheet, metadata and a preview page.

    python generate_atlas.py

Reads the game's Combat_Icon_<Type>_<Name>.png files (by default straight from the data
extract, see --icons) and frames.json, writes to output/:
  Combat_Icon_Atlas.webp glyph atlas, lossless (upload to the wiki under this name)
  combat-icons.css       stylesheet (TemplateStyles-compatible)
  icon-list.wikitext     list of icons for the wiki template's page (Template:CombatIcon/list)
  icons.json             icon ids, types and atlas cells; the next run keeps these cells
  preview.html           local preview comparing CSS icons with the source PNGs

Icons never change cells from one run to the next (see iconpack/layout.py): new icons are
appended, and icons that leave the source keep theirs. The atlas keeps its file name too, unless
--wiki-file gives another. Delete output/icons.json to pack the atlas afresh.

deploy.py runs this script and brings the wiki up to date with its output.
"""
import argparse
import io
import json
import math
import os
import pathlib
import sys

import numpy as np
from PIL import Image

from iconpack.css import CLASS, build_css, wiki_file_url
from iconpack.frames import FrameSet
from iconpack.icons import DEFAULT_SOURCE, Icon, align, extract_glyph, load_icons, shift_image
from iconpack.layout import LAYOUT_FILE, LayoutError, atlas_version, load_previous
from iconpack.preview import build_preview
from iconpack.wikitext import build_icon_list

HERE = os.path.dirname(os.path.abspath(__file__))
GUTTER = 2    # transparent pixels between atlas cells, so filtering never samples a neighbour
COLUMNS = 16  # atlas columns of a fresh layout; a kept layout keeps its own
WIKI_FILE = 'Combat_Icon_Atlas.webp'  # atlas file name of a fresh layout; a kept layout keeps its own

# Icons whose alpha disagrees with their frame in more than this fraction of pixels (after
# alignment) have a different frame altogether and are skipped. The worst match among real
# icons is 0.2%; the green, square Buff_Heal scores 8% against the Buff frame, so it has its own.
MAX_MISMATCH = 0.03
MAX_ERROR = 2         # glyph-over-fill round trip error (0-255) above which a warning is given


def names(ids, limit=12):
    ids = list(ids)
    return ', '.join(ids[:limit]) + (f' and {len(ids) - limit} more' if len(ids) > limit else '')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--icons', default=DEFAULT_SOURCE, help='source icon directory (default: the game data extract)')
    ap.add_argument('--frames', default=os.path.join(HERE, 'frames.json'), help='frame geometry')
    ap.add_argument('--out', default=os.path.join(HERE, 'output'), help='output directory')
    ap.add_argument('--columns', type=int, help=f'atlas columns when laying it out afresh (default {COLUMNS})')
    ap.add_argument('--wiki-file', help='file name of the atlas on the wiki, .webp (lossless) or .png '
                    f"(default: the previous output's, or {WIKI_FILE} for a fresh layout)")
    ap.add_argument('--upload-base', default='https://static.wikitide.net/bluearchivewiki/',
                    help="base URL of the wiki's uploaded files")
    ap.add_argument('--atlas-url', help='use this atlas URL in the stylesheet instead of the wiki upload URL')
    args = ap.parse_args(argv)
    if not os.path.isdir(args.icons):
        sys.exit(f'icon directory {args.icons} not found; pass --icons')

    frameset = FrameSet.load(args.frames)
    cw, ch = frameset.canvas
    try:
        prev = load_previous(args.out, (cw, ch), GUTTER)
    except LayoutError as e:
        sys.exit(str(e))
    if prev and args.columns and args.columns != prev.columns:
        sys.exit(f'{prev.path} lays the atlas out in {prev.columns} columns; delete it to re-pack in {args.columns}')
    columns = prev.columns if prev else args.columns or COLUMNS
    # the name sticks like the cells do, so an atlas re-packed under a new name keeps it
    wiki_file = args.wiki_file or (prev and prev.file) or WIKI_FILE

    models = {name: frameset.render(frame) for name, frame in frameset.frames.items()}
    placed, skipped = [], []
    for icon in load_icons(args.icons):
        icon.frame = frameset.frame_for(icon.id)
        if icon.frame is None:
            skipped.append(f'{icon.file}: no frame for type {icon.type!r} (add one with fit_frames.py --add)')
            continue
        if icon.image.shape[:2] != (ch, cw):
            skipped.append(f'{icon.file}: {icon.image.shape[1]}x{icon.image.shape[0]}, not {cw}x{ch}')
            continue
        dx, dy, mismatch = align(icon.image, models[icon.frame][..., 3])
        if mismatch > MAX_MISMATCH:
            skipped.append(f"{icon.file}: doesn't match the {icon.frame} frame ({mismatch:.1%} of pixels differ); "
                           f'give it its own with fit_frames.py --add NAME --shape SHAPE --for {icon.id}')
            continue
        glyph, s = extract_glyph(shift_image(icon.image, dx, dy), frameset.frames[icon.frame], models[icon.frame])
        icon.shift, icon.glyph = (dx, dy), glyph
        if s['overflow']:
            icon.warnings.append(f"{s['overflow']}px drawn outside frame (clipped)")
        if s['holes']:
            icon.warnings.append(f"{s['holes']}px transparent inside frame")
        if s['max_error'] > MAX_ERROR:
            icon.warnings.append(f"round-trip error {s['max_error']:.0f}")
        placed.append(icon)

    # group by frame (frames.json order), keeping file-name order within a frame
    order = {name: i for i, name in enumerate(frameset.frames)}
    placed.sort(key=lambda i: order[i.frame])

    # Icons keep the cell they had in the previous output and new ones are appended, so a cell
    # never shows a different icon than it did (see iconpack/layout.py).
    cells = prev.cells() if prev else {}
    new = [i for i in placed if i.id not in cells]
    for n, icon in enumerate(new, start=max(cells.values(), default=-1) + 1):
        cells[icon.id] = n
    changed, retained, reserved = [], [], []
    if prev:
        # glyphs that differ from the previous atlas, including ones back in a cell left empty
        for icon in placed:
            old = prev.glyph(icon.id)
            if icon.id in prev.reserved or (old is not None and not np.array_equal(old, icon.glyph)):
                changed.append(icon.id)
        # icons that left the source, or no longer match their frame, keep their cell and glyph
        present = {i.id for i in placed}
        for icon_id, rec in {**prev.icons, **prev.reserved}.items():
            if icon_id in present:
                continue
            glyph = prev.glyph(icon_id)
            if glyph is None:  # nothing to keep, so the cell stays empty
                reserved.append(rec)
            else:
                retained.append(Icon(file=rec['file'], id=icon_id, type=rec['type'], effect=rec['effect'],
                                     image=None, frame=rec.get('frame', rec['type']), shift=tuple(rec['shift']),
                                     glyph=glyph, warnings=rec['warnings'], missing=True))
    drawn = sorted(placed + retained, key=lambda i: cells[i.id])
    reserved.sort(key=lambda r: cells[r['id']])

    rows = max(1, math.ceil((max(cells.values(), default=-1) + 1) / columns))
    aw, ah = columns * (cw + GUTTER) + GUTTER, rows * (ch + GUTTER) + GUTTER
    atlas = np.zeros((ah, aw, 4), dtype=np.uint8)
    for icon in drawn:
        icon.row, icon.col = divmod(cells[icon.id], columns)
        x, y = GUTTER + icon.col * (cw + GUTTER), GUTTER + icon.row * (ch + GUTTER)
        atlas[y:y + ch, x:x + cw] = icon.glyph

    os.makedirs(args.out, exist_ok=True)
    ext = os.path.splitext(wiki_file)[1].lower()
    buf = io.BytesIO()
    if ext == '.webp':  # lossless WebP is bit-exact and about half the size of the PNG
        Image.fromarray(atlas, 'RGBA').save(buf, format='WEBP', lossless=True, quality=100, method=6)
    elif ext == '.png':
        Image.fromarray(atlas, 'RGBA').save(buf, format='PNG', optimize=True)
    else:
        sys.exit(f'--wiki-file must end in .webp or .png, not {ext!r}')
    data = buf.getvalue()
    atlas_path = os.path.join(args.out, wiki_file)
    with open(atlas_path, 'wb') as fh:
        fh.write(data)
    version = atlas_version(data)
    atlas_url = args.atlas_url or f'{wiki_file_url(wiki_file, args.upload_base)}?v={version}'

    layout = dict(columns=columns, rows=rows, gutter=GUTTER, width=aw, height=ah)
    css = build_css(frameset, [(i.id, i.col, i.row) for i in drawn], layout, atlas_url)
    with open(os.path.join(args.out, 'combat-icons.css'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(css)

    records = []
    for icon in drawn:
        record = {
            'id': icon.id, 'file': icon.file, 'type': icon.type, 'effect': icon.effect,
            'col': icon.col, 'row': icon.row,
            'x': GUTTER + icon.col * (cw + GUTTER), 'y': GUTTER + icon.row * (ch + GUTTER),
            'shift': list(icon.shift), 'warnings': icon.warnings,
        }
        if icon.frame != icon.type:
            record['frame'] = icon.frame  # its own frame rather than its type's (see frames.json)
        if icon.missing:
            record['missing'] = True  # gone from the source; glyph kept from the previous atlas
        records.append(record)
    meta = {
        'class': CLASS,
        'atlas': {'file': wiki_file, 'url': atlas_url, 'version': version, 'width': aw, 'height': ah,
                  'cell': [cw, ch], 'gutter': GUTTER, 'columns': columns, 'rows': rows},
        'types': {name: {'fill': '#%02x%02x%02x' % f.fill, 'count': sum(1 for i in drawn if i.frame == name)}
                  for name, f in frameset.frames.items()},
        'icons': records,
        # cells held empty for icons that left the source when their glyph couldn't be kept
        'reserved': [{'id': r['id'], 'type': r['type'], 'col': cells[r['id']] % columns,
                      'row': cells[r['id']] // columns} for r in reserved],
    }
    with open(os.path.join(args.out, LAYOUT_FILE), 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(meta, fh, indent=1)
        fh.write('\n')

    types = [name for name, f in frameset.frames.items() if not f.icons]  # not the frames of single icons
    with open(os.path.join(args.out, 'icon-list.wikitext'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(build_icon_list(records, types))

    page = build_preview(records, list(frameset.frames), 'combat-icons.css', wiki_file,
                         pathlib.Path(os.path.abspath(args.icons)).as_uri(), (aw, ah), version)
    with open(os.path.join(args.out, 'preview.html'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(page)

    # report ----------------------------------------------------------------------------
    counts = ', '.join(f'{name} {meta["types"][name]["count"]}' for name in frameset.frames)
    print(f'{len(drawn)} icons ({counts}) -> {os.path.relpath(atlas_path)} {aw}x{ah}, {len(data) / 1024:.0f} KiB')
    print(f'stylesheet {len(css.encode()) / 1024:.1f} KiB, atlas url {atlas_url}')
    if prev is None:
        print(f'fresh layout (there was no {os.path.relpath(os.path.join(args.out, LAYOUT_FILE))} to keep)')
    else:
        print(f'cells kept from the previous {os.path.relpath(prev.path)}'
              + ('' if prev.atlas is not None else ", but not its atlas (missing, or it doesn't match)"))
        for label, ids in (('new, appended', [i.id for i in new]),
                           ('changed', changed),
                           ('gone from the source, kept from the previous atlas', [i.id for i in retained]),
                           ('gone from the source, cell left empty', [r['id'] for r in reserved])):
            if ids:
                print(f'  {label}: {names(ids)}')
    shifted = [i for i in placed if i.shift != (0, 0)]
    if shifted:
        print(f'{len(shifted)} icons re-aligned to their frame (e.g. {shifted[0].id} by {shifted[0].shift})')
    for r in records:
        if r['warnings']:
            print(f"  warning: {r['id']}: {'; '.join(r['warnings'])}")
    for line in skipped:
        print(f'  skipped {line}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
