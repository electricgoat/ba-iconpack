"""Loading source icons, aligning them to their frame and extracting the glyph layer."""
import os
from dataclasses import dataclass, field

import numpy as np
from PIL import Image
from scipy import ndimage

from .geometry import coverage

PREFIX = 'Combat_Icon_'

# Glyph values of pixels fully inside the fill shape are extended this far (grid distance)
# over the anti-aliased edge, so the CSS clip-path cuts through flat colour instead of
# hitting the transparent border of the layer.
PAD = 2.5


@dataclass
class Icon:
    file: str
    id: str
    type: str
    effect: str
    image: np.ndarray                      # (H, W, 4) uint8, as loaded
    shift: tuple = (0, 0)                  # (dx, dy) applied to line the icon up with its frame
    glyph: np.ndarray = None               # extracted glyph layer, same size as image
    stats: dict = field(default_factory=dict)
    col: int = 0                           # atlas cell
    row: int = 0


def parse_name(filename):
    """'Combat_Icon_Buff_ATK.png' -> ('Buff_ATK', 'Buff', 'ATK'); None if not an icon."""
    stem, ext = os.path.splitext(filename)
    if ext.lower() != '.png' or not stem.startswith(PREFIX):
        return None
    icon_id = stem[len(PREFIX):]
    icon_type, _, effect = icon_id.partition('_')
    if not effect:
        return None
    return icon_id, icon_type, effect


def load_icons(directory):
    icons, skipped = [], []
    for name in sorted(os.listdir(directory), key=str.lower):
        parsed = parse_name(name)
        if parsed is None:
            skipped.append(name)
            continue
        with Image.open(os.path.join(directory, name)) as im:
            image = np.array(im.convert('RGBA'))
        icons.append(Icon(file=name, id=parsed[0], type=parsed[1], effect=parsed[2], image=image))
    return icons, skipped


def shift_image(image, dx, dy):
    """Move image content by (dx, dy) whole pixels, filling with transparency."""
    out = np.zeros_like(image)
    h, w = image.shape[:2]
    src_y = slice(max(0, -dy), h - max(0, dy))
    dst_y = slice(max(0, dy), h - max(0, -dy))
    src_x = slice(max(0, -dx), w - max(0, dx))
    dst_x = slice(max(0, dx), w - max(0, -dx))
    out[dst_y, dst_x] = image[src_y, src_x]
    return out


def align(image, ref_alpha, search=3):
    """Whole-pixel shift that best lines the icon's silhouette up with the frame model.

    Returns (dx, dy, mismatch) where mismatch is the fraction of pixels whose alpha still
    differs from the model by more than 0.25 after shifting.
    """
    alpha = image[..., 3].astype(float) / 255.0
    best = None
    for dy in range(-search, search + 1):
        for dx in range(-search, search + 1):
            shifted = shift_image(alpha[..., None], dx, dy)[..., 0]
            score = np.abs(shifted - ref_alpha).sum()
            if best is None or score < best[0]:
                best = (score, dx, dy, float((np.abs(shifted - ref_alpha) > 0.25).mean()))
    return best[1], best[2], best[3]


def fill_to_alpha(rgb, fill):
    """Minimal-alpha colour such that compositing it over `fill` reproduces `rgb`."""
    f = np.asarray(fill, dtype=float)
    rgb = rgb.astype(float)
    above = np.where(rgb > f, (rgb - f) / np.maximum(255.0 - f, 1e-9), 0.0)
    below = np.where(rgb < f, (f - rgb) / np.maximum(f, 1e-9), 0.0)
    alpha = np.clip(np.maximum(above, below).max(-1), 0.0, 1.0)
    # quantise alpha upwards, then derive the colour from it: the colour then stays within
    # 0..255 without clipping and the 8-bit pair composites back to within half a level
    a8 = np.ceil(alpha * 255.0 - 1e-6)
    color = np.where(a8[..., None] > 0, f + (rgb - f) * 255.0 / np.maximum(a8, 1)[..., None], 0.0)
    return np.concatenate([np.clip(np.round(color), 0, 255), a8[..., None]], -1).astype(np.uint8)


def extract_glyph(image, frame, frame_model):
    """Split an aligned icon into its glyph layer (RGBA uint8) plus diagnostics.

    frame_model is the premultiplied RGBA raster of the CSS frame (FrameSet.render).
    """
    h, w = image.shape[:2]
    c_fill = coverage(frame.fill_outline, w, h)
    # Edge pixels mix fill and rim, so only fully covered pixels are read. The fitted outline is
    # accurate enough that almost all fully covered pixels next to the edge are pure fill colour.
    interior = c_fill >= 1.0 - 1e-9

    glyph = np.zeros((h, w, 4), dtype=np.uint8)
    glyph[interior] = fill_to_alpha(image[interior][:, :3], frame.fill)

    # extend interior values outward across the anti-aliased edge
    dist, (iy, ix) = ndimage.distance_transform_edt(~interior, return_indices=True)
    band = ~interior & (dist <= PAD)
    glyph[band] = glyph[iy[band], ix[band]]

    # diagnostics ---------------------------------------------------------------------
    stats = {}
    fill = np.asarray(frame.fill, dtype=float)
    ga = glyph[..., 3:4].astype(float) / 255.0
    recon = glyph[..., :3] * ga + fill * (1 - ga)
    diff = np.abs(recon - image[..., :3].astype(float)).max(-1)
    stats['max_error'] = float(diff[interior].max()) if interior.any() else 0.0
    stats['holes'] = int((image[..., 3][interior] < 250).sum())
    # glyph content drawn over the rim or outside the frame, which the CSS clips away; pixels
    # under 25% fill coverage cannot differ this much from the frame through clipped glyph edges
    orig = image.astype(float) / 255.0
    orig_prem = np.concatenate([orig[..., :3] * orig[..., 3:4], orig[..., 3:4]], -1)
    outside = c_fill < 0.25
    stats['overflow'] = int(((np.abs(orig_prem - frame_model).max(-1) > 0.35) & outside).sum())
    return glyph, stats
