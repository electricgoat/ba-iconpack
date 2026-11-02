"""Standalone HTML page for eyeballing the generated icons against the source PNGs."""
import html

from .css import CLASS

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Combat icon preview</title>
<link rel="stylesheet" href="{css}">
<style>
/* the stylesheet points at the wiki upload; use the local atlas here */
.{cls}::after {{ background-image: url("{atlas}"); }}
:root {{ color-scheme: light; --bg: #f8f9fa; --fg: #202122; --muted: #54595d; --card: #fff; --line: #c8ccd1; }}
:root.dark {{ color-scheme: dark; --bg: #101418; --fg: #eaecf0; --muted: #a2a9b1; --card: #1b2127; --line: #3c444d; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; padding: 16px; background: var(--bg); color: var(--fg); font: 14px/1.6 system-ui, sans-serif; }}
header {{ display: flex; flex-wrap: wrap; gap: 8px 24px; align-items: baseline; }}
h1 {{ font-size: 20px; margin: 0; }}
h2 {{ font-size: 16px; margin: 28px 0 8px; }}
.muted {{ color: var(--muted); }}
label {{ user-select: none; }}
.panel {{ background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 12px 16px; }}
.scale {{ display: flex; flex-wrap: wrap; align-items: flex-end; gap: 16px; }}
.scale figure {{ margin: 0; text-align: center; }}
.scale figcaption {{ font-size: 12px; color: var(--muted); }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; }}
.cell {{ background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 8px; text-align: center; }}
.pair {{ display: flex; justify-content: center; gap: 6px; }}
.pair img, .pair .gone {{ width: 47px; height: 54px; }}
.pair .gone {{ border: 1px dashed var(--line); border-radius: 4px; }}
.pair .{cls} {{ --combat-icon-size: 54px; }}
.name {{ font: 11px/1.3 ui-monospace, monospace; overflow-wrap: anywhere; margin-top: 4px; }}
.flag {{ display: inline-block; margin-top: 2px; font-size: 11px; color: #b32424; }}
:root.dark .flag {{ color: #fd7865; }}
.atlas {{ max-width: 100%; background: repeating-conic-gradient(#8884 0 25%, transparent 0 50%) 0 0 / 16px 16px; }}
.inline p {{ margin: 4px 0; }}
</style>
</head>
<body>
<header>
<h1>Combat icon preview</h1>
<span class="muted">{count} icons &middot; atlas {aw}&times;{ah}px &middot; version {version}</span>
<label><input type="checkbox" id="dark"> dark background</label>
</header>

<h2>Inline in text</h2>
<div class="panel inline">
<p>Grants {inline1} ATK up and {inline2} crit up, then inflicts {inline3} fear. Dealing damage applies {inline4} and {inline5}. While {inline6} is active, {inline7} is ignored.</p>
<p style="font-size:18px">Grants {inline1} ATK up and {inline2} crit up, then inflicts {inline3} fear. Dealing damage applies {inline4} and {inline5}. While {inline6} is active, {inline7} is ignored.</p>
</div>

<h2>Scaling (vector frame, raster glyph)</h2>
<div class="panel scale">{scale}</div>

<h2>All icons <span class="muted">(CSS icon &nbsp;|&nbsp; source PNG, both at native 47&times;54)</span></h2>
{groups}

<h2>Atlas</h2>
<img class="atlas" src="{atlas}" alt="glyph atlas">
<p class="muted">Glyphs are stored as colour-to-alpha against their frame's fill colour, so they only look right
composited over that fill (which is what the stylesheet does).</p>

<script>
const box = document.getElementById('dark');
box.addEventListener('change', () => document.documentElement.classList.toggle('dark', box.checked));
</script>
</body>
</html>
"""


def icon_markup(icon_id, title=None, style=None):
    attrs = [f'class="{CLASS}"', f'data-icon="{html.escape(icon_id)}"', 'role="img"',
             f'aria-label="{html.escape(title or icon_id)}"', f'title="{html.escape(title or icon_id)}"']
    if style:
        attrs.append(f'style="{style}"')
    return '<span ' + ' '.join(attrs) + '></span>'


def build_preview(icons, types, css_href, atlas_href, icons_href, atlas_size, version):
    """icons: list of dicts with id, file, type and optional warnings (list of str) and missing (bool)."""
    by_type = {t: [i for i in icons if i['type'] == t] for t in types}
    groups = []
    for t, items in by_type.items():
        if not items:
            continue
        cells = []
        for i in items:
            warnings = (['gone from the source'] if i.get('missing') else []) + i.get('warnings', [])
            flags = ''.join(f'<span class="flag">{html.escape(w)}</span><br>' for w in warnings)
            source = ('<span class="gone"></span>' if i.get('missing') else
                      f'<img src="{html.escape(icons_href + "/" + i["file"])}" alt="" loading="lazy">')
            cells.append(f'<div class="cell"><div class="pair">{icon_markup(i["id"])}{source}</div>'
                         f'<div class="name">{html.escape(i["id"])}</div>{flags}</div>')
        groups.append(f'<h3>{html.escape(t)} <span class="muted">({len(items)})</span></h3>\n'
                      f'<div class="grid">\n' + '\n'.join(cells) + '\n</div>')
    ids = {i['id'] for i in icons}
    firsts = [by_type[t][0]['id'] for t in types if by_type.get(t)]
    scale_ids = ([p for p in ('Buff_ATK', 'Debuff_DEF', 'CC_Stunned', 'Special_CH0224_Public', 'Guide_Question')
                  if p in ids] + firsts)[:5]
    inline_ids = ([p for p in ('Buff_ATK', 'Buff_CriticalChance', 'CC_Fear', 'Debuff_Burn', 'Debuff_Bleed',
                               'Special_Immortal', 'CC_Stunned') if p in ids] + firsts * 7)[:7]
    scale = []
    for size in (16, 24, 32, 54, 108, 216):
        sample = ''.join(icon_markup(p, style=f'--combat-icon-size:{size}px') for p in scale_ids)
        scale.append(f'<figure>{sample}<figcaption>{size}px</figcaption></figure>')
    inline = {f'inline{n + 1}': icon_markup(p) for n, p in enumerate(inline_ids)}
    return PAGE.format(cls=CLASS, css=html.escape(css_href), atlas=html.escape(atlas_href), count=len(icons),
                       aw=atlas_size[0], ah=atlas_size[1], version=html.escape(version), scale='\n'.join(scale),
                       groups='\n'.join(groups), **inline)
