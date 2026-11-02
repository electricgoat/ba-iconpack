"""Vector frame model shared by the fitter, the atlas builder and the CSS writer.

Each frame type is an upright convex polygon with rounded corners, skewed horizontally:
    x' = x + skew * (skew_origin_y - y)
The fill is that shape; the rim is the same shape grown by rim_width (before skewing)
and painted underneath in a translucent dark tint. The drop shadow is approximated
without CSS filters (Chrome snaps drop-shadow() offsets to whole device pixels and
drops sub-pixel blur): the rim shape extruded downwards by shadow.extent, painted in
translucent black from shadow.top_offset below the frame's top edge.
"""
import json
import re
from dataclasses import dataclass, field

import numpy as np

from .geometry import convex_hull, coverage, offset_polygon, rounded_polygon, simplify_collinear

ARC_STEP_DEG = 10.0  # rounded corners are emitted as polygon segments spanning at most this much arc


def _hex(rgb):
    return '#%02x%02x%02x' % tuple(rgb)


def _rgb(hex_color):
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


@dataclass
class Frame:
    name: str
    shape: str
    fill: tuple
    rim: tuple
    rim_alpha: float
    rim_width: float
    skew: float
    vertices: list
    radii: list
    skew_origin_y: float = 47.0

    def outline(self, grow=0.0):
        verts = [tuple(v) for v in self.vertices]
        radii = list(self.radii)
        if grow:
            verts = offset_polygon(verts, grow)
            radii = [r + grow for r in radii]
        pts = rounded_polygon(verts, radii, ARC_STEP_DEG)
        return [(x + self.skew * (self.skew_origin_y - y), y) for x, y in pts]

    @property
    def fill_outline(self):
        return self.outline(0.0)

    @property
    def rim_outline(self):
        return self.outline(self.rim_width)

    @property
    def center_y(self):
        """Vertical area centroid of the frame, i.e. where it looks centred."""
        p = np.asarray(self.rim_outline)
        x, y = p[:, 0], p[:, 1]
        x1, y1 = np.roll(x, -1), np.roll(y, -1)
        cross = x * y1 - x1 * y
        return float(((y + y1) * cross).sum() / (3 * cross.sum()))


@dataclass
class Shadow:
    alpha: float
    top_offset: float
    extent: float


@dataclass
class FrameSet:
    canvas: tuple
    shadow: Shadow
    frames: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path):
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
        origin = data.get('skew_origin_y', 47.0)
        frames = {}
        for name, t in data['types'].items():
            frames[name] = Frame(name=name, shape=t['shape'], fill=_rgb(t['fill']), rim=_rgb(t['rim']),
                                 rim_alpha=t['rim_alpha'], rim_width=t['rim_width'], skew=t['skew'],
                                 vertices=[tuple(v) for v in t['vertices']], radii=list(t['radii']),
                                 skew_origin_y=origin)
        return cls(canvas=tuple(data['canvas']), shadow=Shadow(**data['shadow']), frames=frames)

    def save(self, path, extra=None):
        origin = next(iter(self.frames.values())).skew_origin_y if self.frames else 47.0
        data = {
            'canvas': list(self.canvas),
            'skew_origin_y': origin,
            'shadow': {k: round(v, 4) for k, v in vars(self.shadow).items()},
            'types': {
                name: {
                    'shape': f.shape,
                    'fill': _hex(f.fill),
                    'rim': _hex(f.rim),
                    'rim_alpha': round(f.rim_alpha, 4),
                    'rim_width': round(f.rim_width, 4),
                    'skew': round(f.skew, 5),
                    'vertices': [[round(x, 4), round(y, 4)] for x, y in f.vertices],
                    'radii': [round(r, 4) for r in f.radii],
                } for name, f in self.frames.items()
            },
        }
        if extra:
            data.update(extra)
        text = json.dumps(data, indent=2)
        # keep numeric arrays such as [x, y] pairs on one line
        text = re.sub(r'\[\s+([-\d.,\s]+?)\s+\]', lambda m: '[' + re.sub(r'\s+', ' ', m.group(1)) + ']', text)
        text = re.sub(r'\[\s+(\[[-\d., ]+\](?:,\s+\[[-\d., ]+\])*)\s+\]',
                      lambda m: '[' + re.sub(r',\s+\[', ', [', m.group(1)) + ']', text)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text + '\n')

    # --- derived geometry -------------------------------------------------------------

    def hull_outline(self, frame):
        rim = frame.rim_outline
        ext = self.shadow.extent
        return simplify_collinear(convex_hull(rim + [(x, y + ext) for x, y in rim]))

    def shadow_top(self, frame):
        return min(y for _, y in frame.rim_outline) + self.shadow.top_offset

    # --- raster model of the CSS rendering ----------------------------------------------

    def render(self, frame):
        """Premultiplied RGBA float image of the frame as the CSS draws it (no glyph)."""
        w, h = self.canvas
        c_fill = coverage(frame.fill_outline, w, h)
        c_rim = coverage(frame.rim_outline, w, h)
        c_hull = coverage(self.hull_outline(frame), w, h)
        return self.composite(frame, c_fill, c_rim, c_hull)

    def composite(self, frame, c_fill, c_rim, c_hull):
        """Paint shadow, rim and fill (in that order) from precomputed pixel coverages."""
        h = c_fill.shape[0]
        shadow = c_hull * shadow_rows(h, self.shadow.alpha, self.shadow_top(frame))[:, None]
        rim_a = frame.rim_alpha * c_rim
        fill = np.array(frame.fill) / 255.0
        rim = np.array(frame.rim) / 255.0
        prem = rim * rim_a[..., None]  # the black shadow adds no premultiplied colour
        alpha = rim_a + (1 - rim_a) * shadow
        prem = fill * c_fill[..., None] + (1 - c_fill[..., None]) * prem
        alpha = c_fill + (1 - c_fill) * alpha
        return np.concatenate([prem, alpha[..., None]], -1)


def shadow_rows(height, alpha, top):
    """Exact per-row average of the shadow gradient: transparent above `top`, `alpha` below."""
    rows = np.arange(height, dtype=float)
    return np.clip(rows + 1.0 - np.maximum(rows, top), 0.0, 1.0) * alpha
