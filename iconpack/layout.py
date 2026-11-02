"""Atlas cells that stay put from one run to the next.

The wiki delivers the stylesheet (TemplateStyles, part of each rendered page) and the atlas (an
uploaded file behind its own caches) separately, so for a while a reader can get a new stylesheet
with an old atlas, or the other way round. That is harmless as long as no cell ever changes hands:
an icon keeps the cell it was first given, new icons are appended after the last cell in use, and
an icon that leaves the source keeps its cell, drawn from the previous atlas or, if that atlas is
gone, left empty. (The stylesheet doesn't depend on the atlas height, so an older one still works
after the atlas grows.)

The previous layout is read from the last run's icons.json. Delete it to pack the atlas afresh.
"""
import hashlib
import io
import json
import os
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

LAYOUT_FILE = 'icons.json'


class LayoutError(Exception):
    pass


def atlas_version(data):
    """Short content hash of the encoded atlas, used as its cache-busting version."""
    return hashlib.sha1(data).hexdigest()[:10]


@dataclass
class PreviousLayout:
    path: str                                   # the icons.json it was read from
    columns: int
    cell: tuple                                 # (width, height)
    gutter: int
    icons: dict = field(default_factory=dict)   # id -> record, for icons that were drawn
    reserved: dict = field(default_factory=dict)  # id -> record, for cells that were left empty
    file: str = None                            # the atlas's file name, also its name on the wiki
    atlas: np.ndarray = None                    # the atlas icons.json describes; None if gone or changed

    def cells(self):
        """Icon id -> cell index, for every cell in use."""
        return {i: r['row'] * self.columns + r['col'] for i, r in {**self.icons, **self.reserved}.items()}

    def glyph(self, icon_id):
        """The icon's glyph in the previous atlas, or None if it has none there."""
        r = self.icons.get(icon_id)
        if r is None or self.atlas is None:
            return None
        (cw, ch), g = self.cell, self.gutter
        x, y = g + r['col'] * (cw + g), g + r['row'] * (ch + g)
        return self.atlas[y:y + ch, x:x + cw].copy()


def load_previous(out_dir, cell, gutter):
    """The layout of the last run's output in out_dir, or None if there is none."""
    path = os.path.join(out_dir, LAYOUT_FILE)
    if not os.path.isfile(path):
        return None
    fresh = 'delete it to lay the atlas out afresh'
    try:
        with open(path, encoding='utf-8') as fh:
            meta = json.load(fh)
        a = meta['atlas']
        prev = PreviousLayout(path=path, columns=a['columns'], cell=tuple(a['cell']), gutter=a['gutter'],
                              icons={r['id']: r for r in meta['icons']},
                              reserved={r['id']: r for r in meta.get('reserved', [])}, file=a.get('file'))
    except (ValueError, KeyError, TypeError) as e:
        raise LayoutError(f'{path} is not a layout this script can read ({e!r}); restore it or {fresh}')
    if prev.cell != tuple(cell) or prev.gutter != gutter:
        raise LayoutError(f'{path} has {prev.cell[0]}x{prev.cell[1]} cells with a {prev.gutter}px gutter, '
                          f'not {cell[0]}x{cell[1]} with {gutter}px; {fresh}')
    # only trust the atlas file if it is the one icons.json was written with
    atlas_path = os.path.join(out_dir, a.get('file', ''))
    if os.path.isfile(atlas_path):
        with open(atlas_path, 'rb') as fh:
            data = fh.read()
        if atlas_version(data) == a.get('version'):
            with Image.open(io.BytesIO(data)) as im:
                prev.atlas = np.array(im.convert('RGBA'))
    return prev
