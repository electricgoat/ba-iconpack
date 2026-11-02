"""Fit the vector frame geometry in frames.json to the source icons.

Only needed when frame artwork changes or a new icon type appears; generate_atlas.py
just reads frames.json.

How it works: icons of one type share an identical frame, so the per-pixel mode across
all (aligned) icons of a type is a clean picture of the frame. A parametric model is
fitted to that picture by least squares:

  upright convex polygon with rounded corners -> skewX -> fill
  same polygon grown by rim_width             -> skewX -> translucent rim underneath
  blurred, offset silhouette                  -> drop shadow (fit only)

The blurred shadow cannot be reproduced reliably in CSS, so a second step fits the
filter-free shadow that the CSS actually draws (shared by all types).

    python fit_frames.py                      # refit every type in frames.json
    python fit_frames.py --types Buff CC      # refit some types
    python fit_frames.py --add Foo --shape rect   # add a new frame type
"""
import argparse
import math
import os
import sys

import numpy as np
from scipy import ndimage, optimize

from iconpack.frames import Frame, FrameSet, Shadow
from iconpack.geometry import coverage, offset_polygon, rounded_polygon
from iconpack.icons import load_icons, shift_image

HERE = os.path.dirname(os.path.abspath(__file__))
SS = 4  # supersampling used for the blurred shadow during fitting

# Free parameters of each shape and how they map onto upright vertices and corner radii.
SHAPES = {
    'rect': (
        ['x0', 'y0', 'x1', 'y1', 'r'],
        lambda p: ([(p['x0'], p['y0']), (p['x1'], p['y0']), (p['x1'], p['y1']), (p['x0'], p['y1'])],
                   [p['r']] * 4)),
    'house': (  # pointed top (Buff)
        ['xa', 'ya', 'x1', 'ysh_r', 'y1', 'x0', 'ysh_l', 'r_apex', 'r_sh_r', 'r_br', 'r_bl', 'r_sh_l'],
        lambda p: ([(p['xa'], p['ya']), (p['x1'], p['ysh_r']), (p['x1'], p['y1']), (p['x0'], p['y1']),
                    (p['x0'], p['ysh_l'])],
                   [p['r_apex'], p['r_sh_r'], p['r_br'], p['r_bl'], p['r_sh_l']])),
    'shield': (  # pointed bottom (Debuff)
        ['x0', 'y0', 'x1', 'ysh_r', 'xp', 'yp', 'ysh_l', 'r_tl', 'r_tr', 'r_sh_r', 'r_point', 'r_sh_l'],
        lambda p: ([(p['x0'], p['y0']), (p['x1'], p['y0']), (p['x1'], p['ysh_r']), (p['xp'], p['yp']),
                    (p['x0'], p['ysh_l'])],
                   [p['r_tl'], p['r_tr'], p['r_sh_r'], p['r_point'], p['r_sh_l']])),
}
COMMON = ['skew', 'rim_width', 'rim_alpha', 'rim_r', 'rim_g', 'rim_b', 'sh_dx', 'sh_dy', 'sh_sigma', 'sh_alpha']
BOUNDS = {'skew': (0.0, 0.5), 'rim_width': (0.05, 3.0), 'rim_alpha': (0.05, 1.0), 'rim_r': (0, 1),
          'rim_g': (0, 1), 'rim_b': (0, 1), 'sh_dx': (-2, 2), 'sh_dy': (-1, 4), 'sh_sigma': (0.05, 4),
          'sh_alpha': (0, 1)}


def shape_params(frame):
    """Inverse of SHAPES: read the free parameters back out of a Frame."""
    v, r = frame.vertices, frame.radii
    if frame.shape == 'rect':
        return dict(x0=v[0][0], y0=v[0][1], x1=v[1][0], y1=v[2][1], r=float(np.mean(r)))
    if frame.shape == 'house':
        return dict(xa=v[0][0], ya=v[0][1], x1=v[1][0], ysh_r=v[1][1], y1=v[2][1], x0=v[3][0], ysh_l=v[4][1],
                    r_apex=r[0], r_sh_r=r[1], r_br=r[2], r_bl=r[3], r_sh_l=r[4])
    if frame.shape == 'shield':
        return dict(x0=v[0][0], y0=v[0][1], x1=v[1][0], ysh_r=v[2][1], xp=v[3][0], yp=v[3][1], ysh_l=v[4][1],
                    r_tl=r[0], r_tr=r[1], r_sh_r=r[2], r_point=r[3], r_sh_l=r[4])
    raise ValueError(f'unknown shape {frame.shape!r}')


# --- consensus templates ---------------------------------------------------------------

def _mode(stack):
    """Per-pixel most common RGBA value across a stack, and how common it is."""
    n, h, w, _ = stack.shape
    packed = stack.astype(np.int64)
    packed = (packed[..., 0] << 24) | (packed[..., 1] << 16) | (packed[..., 2] << 8) | packed[..., 3]
    mode = np.zeros((h, w), dtype=np.int64)
    freq = np.zeros((h, w))
    for y in range(h):
        for x in range(w):
            vals, counts = np.unique(packed[:, y, x], return_counts=True)
            mode[y, x] = vals[counts.argmax()]
            freq[y, x] = counts.max() / n
    rgba = np.stack([(mode >> s) & 255 for s in (24, 16, 8, 0)], -1).astype(np.uint8)
    return rgba, freq


def build_template(images):
    """Align images to their majority silhouette and return (premultiplied template, freq)."""
    stack = np.stack(images)
    ref = _mode(stack)[0][..., 3].astype(float)
    aligned = []
    for img in images:
        best = None
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                s = shift_image(img, dx, dy)
                score = (np.abs(s[..., 3].astype(float) - ref) > 8).sum()
                if best is None or score < best[0]:
                    best = (score, s)
        aligned.append(best[1])
    rgba, freq = _mode(np.stack(aligned))
    t = rgba.astype(float) / 255.0
    prem = np.concatenate([t[..., :3] * t[..., 3:4], t[..., 3:4]], -1)
    return prem, freq


# --- fitting model with a blurred drop shadow ------------------------------------------

def _outline(shape, p, grow):
    verts, radii = SHAPES[shape][1](p)
    if grow:
        verts = offset_polygon(verts, grow)
        radii = [r + grow for r in radii]
    pts = rounded_polygon(verts, radii, max_step_deg=7.5)
    return [(x + p['skew'] * (47.0 - y), y) for x, y in pts]


def render_fit_model(shape, p, fill, canvas):
    w, h = canvas
    sc = lambda pts: coverage([(x * SS, y * SS) for x, y in pts], w * SS, h * SS)
    c_fill, c_rim = sc(_outline(shape, p, 0.0)), sc(_outline(shape, p, p['rim_width']))
    content = c_fill + (1 - c_fill) * p['rim_alpha'] * c_rim
    shadow = ndimage.gaussian_filter(content, p['sh_sigma'] * SS, mode='constant')
    shadow = ndimage.shift(shadow, (p['sh_dy'] * SS, p['sh_dx'] * SS), order=1, mode='constant') * p['sh_alpha']
    down = lambda a: a.reshape(h, SS, w, SS).mean(axis=(1, 3))
    c_fill, c_rim, shadow = down(c_fill), down(c_rim), down(shadow)
    content = c_fill + (1 - c_fill) * p['rim_alpha'] * c_rim
    f = np.asarray(fill) / 255.0
    rim = np.array([p['rim_r'], p['rim_g'], p['rim_b']])
    prem = f * c_fill[..., None] + (1 - c_fill)[..., None] * rim * (p['rim_alpha'] * c_rim)[..., None]
    alpha = content + (1 - content) * shadow
    return np.concatenate([prem, alpha[..., None]], -1)


def edge_band(outline, freq, canvas, radius=3.5):
    """Pixels near the frame edge that most icons agree on (glyphs rarely reach there)."""
    w, h = canvas
    cov = coverage(outline, w, h)
    edge = (cov > 1e-3) & (cov < 1 - 1e-3)
    return (ndimage.distance_transform_edt(~edge) <= radius) & (freq >= 0.5)


def fit_frame(name, shape, fill, template, freq, init, canvas):
    names = SHAPES[shape][0] + COMMON
    p0 = np.array([init[n] for n in names], dtype=float)
    lo = np.array([BOUNDS.get(n, (0.0, 12.0) if n.startswith('r') else (-10.0, 70.0))[0] for n in names])
    hi = np.array([BOUNDS.get(n, (0.0, 12.0) if n.startswith('r') else (-10.0, 70.0))[1] for n in names])
    p0 = np.clip(p0, lo + 1e-9, hi - 1e-9)

    def residuals(p, mask):
        return (render_fit_model(shape, dict(zip(names, p)), fill, canvas) - template)[mask].ravel()

    for _ in range(3):  # refit with a band recomputed from the current geometry
        mask = edge_band(_outline(shape, dict(zip(names, p0)), 0.0), freq, canvas)
        res = optimize.least_squares(residuals, p0, args=(mask,), bounds=(lo, hi), diff_step=1e-5,
                                     x_scale='jac', ftol=1e-12, xtol=1e-12, gtol=1e-12, max_nfev=20000)
        converged = np.allclose(res.x, p0, atol=1e-5)
        p0 = res.x
        if converged:
            break
    p = dict(zip(names, p0))
    err = np.abs(residuals(p0, mask)) * 255
    print(f'  {name:8s} [{shape}] mean|err|={err.mean():.2f} p99={np.percentile(err, 99):.1f} '
          f'skew={math.degrees(math.atan(p["skew"])):.2f}deg rim={p["rim_width"]:.3f}px@{p["rim_alpha"]:.2f} '
          f'shadow=({p["sh_dx"]:.2f},{p["sh_dy"]:.2f}) sigma={p["sh_sigma"]:.2f} a={p["sh_alpha"]:.2f}')
    verts, radii = SHAPES[shape][1](p)
    rim = tuple(int(round(np.clip(p[k], 0, 1) * 255)) for k in ('rim_r', 'rim_g', 'rim_b'))
    frame = Frame(name=name, shape=shape, fill=tuple(fill), rim=rim, rim_alpha=p['rim_alpha'],
                  rim_width=p['rim_width'], skew=p['skew'], vertices=verts, radii=radii)
    return frame, p


def fit_shadow(frameset, templates):
    """Grid search for the shared filter-free shadow (alpha, top offset, extent)."""
    w, h = frameset.canvas
    layers, hulls = {}, {}
    for n, f in frameset.frames.items():
        layers[n] = (coverage(f.fill_outline, w, h), coverage(f.rim_outline, w, h),
                     edge_band(f.fill_outline, templates[n][1], frameset.canvas))

    def cost(alpha, top, ext):
        frameset.shadow = Shadow(alpha, top, round(ext, 6))
        total = 0.0
        for n, f in frameset.frames.items():
            key = (n, round(ext, 6))
            if key not in hulls:
                hulls[key] = coverage(frameset.hull_outline(f), w, h)
            c_fill, c_rim, mask = layers[n]
            model = frameset.composite(f, c_fill, c_rim, hulls[key])
            total += (((model - templates[n][0])[mask]) ** 2).sum()
        return total

    best = min((cost(a, t, e), a, t, e) for a in np.arange(0.40, 0.71, 0.02)
               for t in np.arange(0.5, 8.01, 0.5) for e in np.arange(1.0, 2.8, 0.125))
    for da, dt, de in ((0.01, 0.2, 0.05), (0.005, 0.1, 0.025)):  # local refinement
        _, a0, t0, e0 = best
        best = min([best] + [(cost(a0 + i * da, t0 + j * dt, e0 + k * de), a0 + i * da, t0 + j * dt, e0 + k * de)
                             for i in (-2, -1, 0, 1, 2) for j in (-2, -1, 0, 1, 2) for k in (-2, -1, 0, 1, 2)])
    _, a, t, e = best
    frameset.shadow = Shadow(float(a), float(t), float(e))
    print(f'  shadow: alpha={a:.3f} top_offset={t:.3f} extent={e:.3f}')


def initial_params(frame, fill, template):
    p = dict(shape_params(frame))
    p.update(skew=frame.skew, rim_width=frame.rim_width, rim_alpha=frame.rim_alpha,
             rim_r=frame.rim[0] / 255, rim_g=frame.rim[1] / 255, rim_b=frame.rim[2] / 255,
             sh_dx=0.0, sh_dy=1.5, sh_sigma=0.6, sh_alpha=0.74)
    if template is not None:
        # new type: move the reference shape onto the new silhouette's bounding box
        ys, xs = np.nonzero(template[..., 3] > 0.9)
        ref = coverage(frame.fill_outline, *frame_canvas(template))
        rys, rxs = np.nonzero(ref > 0.5)
        dx = (xs.min() + xs.max() - rxs.min() - rxs.max()) / 2
        dy = (ys.min() + ys.max() - rys.min() - rys.max()) / 2
        for k in list(p):
            if k.startswith('x'):
                p[k] += dx
            elif k.startswith('y'):
                p[k] += dy
        p.update(rim_r=fill[0] / 255 * 0.35, rim_g=fill[1] / 255 * 0.1, rim_b=fill[2] / 255 * 0.35)
    return p


def frame_canvas(template):
    return template.shape[1], template.shape[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--icons', default=os.path.join(HERE, 'icons'))
    ap.add_argument('--frames', default=os.path.join(HERE, 'frames.json'))
    ap.add_argument('--types', nargs='*', help='types to refit (default: all)')
    ap.add_argument('--add', metavar='TYPE', help='add a new frame type')
    ap.add_argument('--shape', choices=sorted(SHAPES), help='shape of the new type (with --add)')
    ap.add_argument('--fill', help='fill colour of the new type as #rrggbb (default: most common colour)')
    args = ap.parse_args()

    frameset = FrameSet.load(args.frames)
    icons, _ = load_icons(args.icons)
    by_type = {}
    for icon in icons:
        by_type.setdefault(icon.type, []).append(icon.image)

    todo = list(args.types or frameset.frames)
    if args.add:
        if not args.shape:
            sys.exit('--add needs --shape')
        todo = [args.add]
    templates = {}
    for name in set(todo) | set(frameset.frames):
        if name not in by_type:
            sys.exit(f'no icons of type {name!r} in {args.icons}')
        templates[name] = build_template(by_type[name])

    print('fitting frames:')
    for name in todo:
        tmpl, freq = templates[name]
        if name in frameset.frames:
            ref, fill, new = frameset.frames[name], frameset.frames[name].fill, None
        else:
            ref = next(f for f in frameset.frames.values() if f.shape == args.shape)
            if args.fill:
                fill = tuple(int(args.fill.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
            else:
                opaque = tmpl[freq >= 0.9]
                opaque = opaque[opaque[:, 3] > 0.999][:, :3]
                vals, counts = np.unique(np.round(opaque * 255).astype(int), axis=0, return_counts=True)
                fill = tuple(int(v) for v in vals[counts.argmax()])
            new = tmpl
        init = initial_params(ref, fill, new)
        frame, _ = fit_frame(name, ref.shape if new is None else args.shape, fill, tmpl, freq, init,
                             frameset.canvas)
        frameset.frames[name] = frame
    fit_shadow(frameset, templates)
    frameset.save(args.frames)
    print(f'wrote {os.path.relpath(args.frames)}')


if __name__ == '__main__':
    main()
