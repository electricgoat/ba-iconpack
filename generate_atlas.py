"""Build the combat icon glyph atlas, its stylesheet, metadata and a preview page.

    python generate_atlas.py

Reads icons/Combat_Icon_<Type>_<Name>.png and frames.json, writes to output/:
  Combat_Icon_Atlas.webp glyph atlas, lossless (upload to the wiki under this name)
  combat-icons.css       stylesheet (TemplateStyles-compatible)
  icons.json             icon ids, types and atlas positions
  preview.html           local preview comparing CSS icons with the source PNGs
"""
import argparse
import hashlib
import io
import json
import math
import os
import sys

import numpy as np
from PIL import Image

from iconpack.css import CLASS, build_css, wiki_file_url
from iconpack.frames import FrameSet
from iconpack.icons import align, extract_glyph, load_icons, shift_image
from iconpack.preview import build_preview

HERE = os.path.dirname(os.path.abspath(__file__))
GUTTER = 2  # transparent pixels between atlas cells, so filtering never samples a neighbour

# thresholds for warnings
MAX_MISMATCH = 0.03   # fraction of pixels whose alpha disagrees with the frame after alignment
MAX_ERROR = 2         # glyph-over-fill round trip error, 0-255


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--icons', default=os.path.join(HERE, 'icons'), help='source icon directory')
    ap.add_argument('--frames', default=os.path.join(HERE, 'frames.json'), help='frame geometry')
    ap.add_argument('--out', default=os.path.join(HERE, 'output'), help='output directory')
    ap.add_argument('--columns', type=int, default=16, help='atlas columns')
    ap.add_argument('--wiki-file', default='Combat_Icon_Atlas.webp',
                    help='file name of the atlas on the wiki; .webp (lossless) or .png')
    ap.add_argument('--upload-base', default='https://static.wikitide.net/bluearchivewiki/',
                    help="base URL of the wiki's uploaded files")
    ap.add_argument('--atlas-url', help='use this atlas URL in the stylesheet instead of the wiki upload URL')
    args = ap.parse_args()

    frameset = FrameSet.load(args.frames)
    cw, ch = frameset.canvas
    icons, skipped = load_icons(args.icons)
    models = {name: frameset.render(frame) for name, frame in frameset.frames.items()}

    placed, unknown = [], []
    for icon in icons:
        if icon.type not in frameset.frames:
            unknown.append(icon)
            continue
        if icon.image.shape[:2] != (ch, cw):
            unknown.append(icon)
            continue
        dx, dy, mismatch = align(icon.image, models[icon.type][..., 3])
        glyph, stats = extract_glyph(shift_image(icon.image, dx, dy), frameset.frames[icon.type], models[icon.type])
        icon.shift, icon.glyph = (dx, dy), glyph
        icon.stats = dict(stats, mismatch=mismatch)
        placed.append(icon)

    # group by frame type (frames.json order), keeping file-name order within a type
    order = {name: i for i, name in enumerate(frameset.frames)}
    placed.sort(key=lambda i: order[i.type])

    columns = max(1, min(args.columns, len(placed)))
    rows = max(1, math.ceil(len(placed) / columns))
    aw, ah = columns * (cw + GUTTER) + GUTTER, rows * (ch + GUTTER) + GUTTER
    atlas = np.zeros((ah, aw, 4), dtype=np.uint8)
    for n, icon in enumerate(placed):
        icon.col, icon.row = n % columns, n // columns
        x, y = GUTTER + icon.col * (cw + GUTTER), GUTTER + icon.row * (ch + GUTTER)
        atlas[y:y + ch, x:x + cw] = icon.glyph

    os.makedirs(args.out, exist_ok=True)
    ext = os.path.splitext(args.wiki_file)[1].lower()
    buf = io.BytesIO()
    if ext == '.webp':  # lossless WebP is bit-exact and about half the size of the PNG
        Image.fromarray(atlas, 'RGBA').save(buf, format='WEBP', lossless=True, quality=100, method=6)
    elif ext == '.png':
        Image.fromarray(atlas, 'RGBA').save(buf, format='PNG', optimize=True)
    else:
        sys.exit(f'--wiki-file must end in .webp or .png, not {ext!r}')
    data = buf.getvalue()
    atlas_path = os.path.join(args.out, args.wiki_file)
    with open(atlas_path, 'wb') as fh:
        fh.write(data)
    version = hashlib.sha1(data).hexdigest()[:10]
    atlas_url = args.atlas_url or f'{wiki_file_url(args.wiki_file, args.upload_base)}?v={version}'

    layout = dict(columns=columns, rows=rows, gutter=GUTTER, width=aw, height=ah)
    css = build_css(frameset, [(i.id, i.col, i.row) for i in placed], layout, atlas_url)
    with open(os.path.join(args.out, 'combat-icons.css'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(css)

    records = []
    for icon in placed:
        warnings = []
        s = icon.stats
        if s['mismatch'] > MAX_MISMATCH:
            warnings.append(f"frame mismatch {s['mismatch']:.1%}")
        if s['overflow']:
            warnings.append(f"{s['overflow']}px drawn outside frame (clipped)")
        if s['holes']:
            warnings.append(f"{s['holes']}px transparent inside frame")
        if s['max_error'] > MAX_ERROR:
            warnings.append(f"round-trip error {s['max_error']:.0f}")
        records.append({
            'id': icon.id, 'file': icon.file, 'type': icon.type, 'effect': icon.effect,
            'col': icon.col, 'row': icon.row,
            'x': GUTTER + icon.col * (cw + GUTTER), 'y': GUTTER + icon.row * (ch + GUTTER),
            'shift': list(icon.shift), 'warnings': warnings,
        })
    meta = {
        'class': CLASS,
        'atlas': {'file': args.wiki_file, 'url': atlas_url, 'version': version, 'width': aw, 'height': ah,
                  'cell': [cw, ch], 'gutter': GUTTER, 'columns': columns, 'rows': rows},
        'types': {name: {'fill': '#%02x%02x%02x' % f.fill, 'count': sum(1 for i in placed if i.type == name)}
                  for name, f in frameset.frames.items()},
        'icons': records,
    }
    with open(os.path.join(args.out, 'icons.json'), 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(meta, fh, indent=1)
        fh.write('\n')

    page = build_preview(records, list(frameset.frames), 'combat-icons.css', args.wiki_file,
                         os.path.relpath(args.icons, args.out).replace(os.sep, '/'), (aw, ah), version)
    with open(os.path.join(args.out, 'preview.html'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(page)

    # report ----------------------------------------------------------------------------
    counts = ', '.join(f'{name} {meta["types"][name]["count"]}' for name in frameset.frames)
    print(f'{len(placed)} icons ({counts}) -> {os.path.relpath(atlas_path)} {aw}x{ah}, {len(data) / 1024:.0f} KiB')
    print(f'stylesheet {len(css.encode()) / 1024:.1f} KiB, atlas url {atlas_url}')
    shifted = [i for i in placed if i.shift != (0, 0)]
    if shifted:
        print(f'{len(shifted)} icons re-aligned to their frame (e.g. {shifted[0].id} by {shifted[0].shift})')
    for r in records:
        if r['warnings']:
            print(f"  warning: {r['id']}: {'; '.join(r['warnings'])}")
    for icon in unknown:
        print(f'  skipped {icon.file}: no frame for type {icon.type!r} (add it with fit_frames.py --add)'
              if icon.type not in frameset.frames else f'  skipped {icon.file}: unexpected size')
    for name in skipped:
        print(f'  ignored {name}: not a Combat_Icon_<Type>_<Name>.png file')
    return 0


if __name__ == '__main__':
    sys.exit(main())
