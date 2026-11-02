"""Polygon helpers: exact-area rasterization, rounded corners, offsets and hulls.

Coordinates are in source pixels with pixel (x, y) covering [x, x+1) x [y, y+1).
"""
import math

import numpy as np


def coverage(points, width, height):
    """Exact fraction of each pixel covered by a simple closed polygon.

    Port of the signed-area accumulation rasterizer from font-rs: every edge deposits
    its exact trapezoid area into an accumulation buffer, which a running sum turns
    into per-pixel coverage. Coverage is continuous in the vertex coordinates, which
    keeps least-squares fitting well behaved.
    """
    acc = np.zeros(width * height + 2)
    n = len(points)
    for i in range(n):
        _accumulate_edge(acc, width, height, points[i], points[(i + 1) % n])
    cov = np.abs(np.cumsum(acc[:width * height])).reshape(height, width)
    return np.minimum(cov, 1.0)


def _accumulate_edge(acc, width, height, p0, p1):
    x0, y0 = p0
    x1, y1 = p1
    if abs(y0 - y1) < 1e-12:
        return
    direction = 1.0
    if y0 > y1:
        direction = -1.0
        x0, y0, x1, y1 = x1, y1, x0, y0
    dxdy = (x1 - x0) / (y1 - y0)
    x = x0
    if y0 < 0:
        x -= y0 * dxdy
    for y in range(max(int(math.floor(y0)), 0), min(height, int(math.ceil(y1)))):
        row = y * width
        dy = min(y + 1.0, y1) - max(float(y), y0)
        x_next = x + dxdy * dy
        d = dy * direction
        xa, xb = (x, x_next) if x < x_next else (x_next, x)
        xa_floor = math.floor(xa)
        xai = int(xa_floor)
        xbi = int(math.ceil(xb))
        idx = row + xai
        if idx >= 0:
            if xbi <= xai + 1:
                xmf = 0.5 * (x + x_next) - xa_floor
                acc[idx] += d - d * xmf
                acc[idx + 1] += d * xmf
            else:
                s = 1.0 / (xb - xa)
                xaf = xa - xa_floor
                a0 = 0.5 * s * (1.0 - xaf) ** 2
                xbf = xb - xbi + 1.0
                am = 0.5 * s * xbf * xbf
                acc[idx] += d * a0
                if xbi == xai + 2:
                    acc[idx + 1] += d * (1.0 - a0 - am)
                else:
                    a1 = s * (1.5 - xaf)
                    acc[idx + 1] += d * (a1 - a0)
                    for xi in range(xai + 2, xbi - 1):
                        acc[row + xi] += d * s
                    a2 = a1 + (xbi - xai - 3) * s
                    acc[row + xbi - 1] += d * (1.0 - a2 - am)
                acc[row + xbi] += d * am
        x = x_next


def rounded_polygon(verts, radii, max_step_deg=8.0):
    """Outline of a convex polygon whose corners are circular arcs.

    Each corner gets enough segments that no segment spans more than max_step_deg of arc.
    """
    n = len(verts)
    if np.isscalar(radii):
        radii = [radii] * n
    v = np.asarray(verts, dtype=float)
    out = []
    for i in range(n):
        prev, cur, nxt = v[i - 1], v[i], v[(i + 1) % n]
        r = radii[i]
        u1, u2 = prev - cur, nxt - cur
        l1, l2 = np.linalg.norm(u1), np.linalg.norm(u2)
        u1, u2 = u1 / l1, u2 / l2
        theta = math.acos(float(np.clip(np.dot(u1, u2), -1.0, 1.0)))  # interior angle
        if r <= 1e-9 or theta >= math.pi - 1e-9:
            out.append((float(cur[0]), float(cur[1])))
            continue
        t = min(r / math.tan(theta / 2), 0.49 * l1, 0.49 * l2)  # tangent length
        r_eff = t * math.tan(theta / 2)
        a = cur + u1 * t
        b = cur + u2 * t
        bis = (u1 + u2) / np.linalg.norm(u1 + u2)
        c = cur + bis * (r_eff / math.sin(theta / 2))
        ang_a = math.atan2(a[1] - c[1], a[0] - c[0])
        ang_b = math.atan2(b[1] - c[1], b[0] - c[0])
        sweep = (ang_b - ang_a + math.pi) % (2 * math.pi) - math.pi
        seg = max(2, math.ceil(abs(math.degrees(sweep)) / max_step_deg))
        for k in range(seg + 1):
            ang = ang_a + sweep * k / seg
            out.append((c[0] + r_eff * math.cos(ang), c[1] + r_eff * math.sin(ang)))
    return out


def offset_polygon(verts, dist):
    """Move every edge of a convex polygon outward by dist, keeping corners sharp."""
    v = np.asarray(verts, dtype=float)
    n = len(v)
    area = 0.5 * np.sum(v[:, 0] * np.roll(v[:, 1], -1) - np.roll(v[:, 0], -1) * v[:, 1])
    sign = 1.0 if area > 0 else -1.0
    lines = []
    for i in range(n):
        p, q = v[i], v[(i + 1) % n]
        d = (q - p) / np.linalg.norm(q - p)
        lines.append((p + np.array([d[1], -d[0]]) * sign * dist, d))
    out = []
    for i in range(n):
        (p1, d1), (p2, d2) = lines[i - 1], lines[i]
        s, _ = np.linalg.solve(np.array([d1, -d2]).T, p2 - p1)
        out.append(tuple(p1 + s * d1))
    return out


def convex_hull(points):
    """Andrew's monotone chain; returns hull vertices in counter-clockwise order."""
    pts = sorted(set((round(x, 9), round(y, 9)) for x, y in points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def simplify_collinear(points, tol=1e-4):
    """Drop vertices that lie on the straight line between their neighbours."""
    out = list(points)
    changed = True
    while changed and len(out) > 3:
        changed = False
        for i in range(len(out)):
            a, b, c = np.array(out[i - 1]), np.array(out[i]), np.array(out[(i + 1) % len(out)])
            ab, ac = b - a, c - a
            if abs(ab[0] * ac[1] - ab[1] * ac[0]) <= tol * np.linalg.norm(ac):
                del out[i]
                changed = True
                break
    return out
