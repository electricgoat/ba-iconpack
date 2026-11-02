# ba-iconpack

Builds the Blue Archive combat status icons (`Combat_Icon_*.png`: buffs, debuffs, CC, special and
guide icons) into one glyph atlas plus a stylesheet for [bluearchive.wiki](https://bluearchive.wiki).

The coloured frame around each icon is drawn by CSS as vector `clip-path` polygons, so it stays sharp
at any size and pixel density. Only the glyph inside the frame comes from the raster atlas.

## Usage

```
pip install -r requirements.txt
python generate_atlas.py
```

This reads `icons/` and `frames.json` and writes `output/`:

| File | Purpose |
|---|---|
| `Combat_Icon_Atlas.webp` | Glyph atlas, lossless WebP (123 KiB; the same atlas as PNG is 266 KiB). Pass `--wiki-file Combat_Icon_Atlas.png` for PNG. |
| `combat-icons.css` | The stylesheet. The atlas URL points at the wiki upload. |
| `icons.json` | Icon ids, types, atlas cells and any warnings, for templates or modules. |
| `preview.html` | Local page showing every CSS icon next to its source PNG, at several sizes and on light or dark backgrounds. |

The output is deterministic, so re-running without changes produces identical files.

## Markup

```html
<span class="combat-icon mw-no-invert" data-icon="Buff_ATK" role="img" aria-label="ATK Up" title="ATK Up"></span>
```

- `data-icon` is the file name without `Combat_Icon_` and `.png`. Its prefix (`Buff_`, `Debuff_`,
  `CC_`, `Special_`, `Guide_`) selects the frame, so templates don't need to pass the type.
  An unknown name shows an empty frame of its type, and an unknown type shows a grey (Guide) frame.
- Size: set `--combat-icon-size` (the icon's height, default `1.5em`) inline or on any ancestor,
  e.g. `style="--combat-icon-size:24px"`. The width follows the source 47:54 aspect ratio, and the
  box is the same as the source PNG's, so a CSS icon can replace `[[File:Combat_Icon_…png|x24px]]` 1:1.
- Inline, each icon is centred on the text by its frame rather than its box. CC and Special frames
  sit low and short in the shared canvas, so they are raised to line up with Buff and Debuff.
- `mw-no-invert` is only needed for the DarkMode extension, which dark-modes the default skin
  (Vector legacy) by inverting the whole page. That class makes it re-invert the icon, as it does
  for images. Citizen, Vector 2022 and Minerva have native dark themes and ignore it.

All of the above was checked against the live wiki: this markup survives the wikitext sanitizer, and
`combat-icons.css` passes TemplateStyles (plus TemplateStylesExtender) with no errors or dropped
declarations.

## Deploying to the wiki

1. Upload `output/Combat_Icon_Atlas.webp` as **File:Combat_Icon_Atlas.webp**. The stylesheet computes
   the file's URL from that exact name (MediaWiki's hashed upload path on `static.wikitide.net`).
2. Paste `output/combat-icons.css` into a TemplateStyles page, e.g. `Template:CombatIcon/styles.css`,
   and load it from the template with `<templatestyles src="CombatIcon/styles.css" />`.
3. When icons change, re-upload the atlas and re-paste the CSS together. The `?v=<hash>` on the atlas
   URL changes with the atlas contents, so browsers never pair new CSS with a cached old atlas.

Use `--wiki-file` or `--upload-base` if the file name or wiki differ, or `--atlas-url` to point
at any other URL.

## How it works

**Frames.** Every icon of a type has an identical frame, so `fit_frames.py` takes the per-pixel
consensus of all icons of each type and fits a vector model to it by least squares. The model is an
upright rounded polygon, skewed about 10°, over a translucent dark rim and a drop shadow. The fitted
geometry lives in `frames.json`. Rendered by Chrome at native size, the CSS icons differ from the
source PNGs by 2.4/255 on average on a white background and 1.0/255 on a dark one.

The shadow is not a CSS `filter: drop-shadow()`. Chrome snaps drop-shadow offsets to whole device
pixels and drops sub-pixel blur, so at typical wiki sizes the shadow would jump or vanish. Instead,
the icon element is clipped to the rim shape extruded downwards, and its own background paints the
shadow. Three layers result: element (shadow), `::before` (rim) and `::after` (fill plus glyph).

**Glyphs.** Each icon is aligned to its frame first: 21 Buff icons sit 1px lower in their PNGs than
the rest, and this is corrected. Then every pixel fully inside the fill shape is converted from the fill
colour to alpha. That gives the minimal-alpha colour which, composited over the fill, reproduces the
source pixel exactly. The glyph is padded outward across the edge so the vector clip cuts through flat
colour. As a consequence, the atlas glyphs only look right over their frame's fill colour, which is how
the stylesheet draws them.

## Maintenance

- **New icons**: add the PNGs to `icons/` and re-run `generate_atlas.py`. It reports icons that don't
  line up with their frame, have transparent holes, or draw outside the frame. At the moment only
  `Special_Omamori` does, where the top 2px of its string loop gets clipped.
- **New icon type**: `generate_atlas.py` skips types that have no frame in `frames.json`. Fit one with
  `python fit_frames.py --add NewType --shape rect` (`rect`, `house` for a Buff-style pointed top,
  `shield` for a Debuff-style pointed bottom), then re-run `generate_atlas.py`.
- **Changed frame artwork**: `python fit_frames.py` refits every type in `frames.json`.

## Limitations

- Glyphs are 1× raster art, so they soften once an icon is shown larger than about 54 device pixels
  tall. The frames stay sharp.
- CSS backgrounds are skipped when printing unless the reader enables "background graphics", and
  TemplateStyles rejects `print-color-adjust`, so the icons can't opt out of this.
