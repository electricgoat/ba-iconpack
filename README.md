# ba-iconpack

Builds the Blue Archive combat status icons (`Combat_Icon_*.png`: buffs, debuffs, CC, special and
guide icons) into one glyph atlas plus a stylesheet for [bluearchive.wiki](https://bluearchive.wiki),
where `{{CombatIcon}}` (`wiki/CombatIcon.wikitext`) shows them.

The coloured frame around each icon is drawn by CSS as vector `clip-path` polygons, so it stays sharp
at any size and pixel density. Only the glyph inside the frame comes from the raster atlas.

## Usage

```
pip install -r requirements.txt
python generate_atlas.py
```

This reads the icons straight from the game data extract and writes `output/`. The extract is
`C:\blue_archive_data\datamine\blue_archive\ui_textures_pc\Assets\_MX\AddressableAsset\UIs\02_Tactics\04_BuffIcon`;
use `--icons` to read them from somewhere else. Only `Combat_Icon_<Type>_<Name>.png` files are read. The
`Suffix_*` badges (EX, stack, timer) that sit in the same folder are ignored.

| File | Purpose |
|---|---|
| `Combat_Icon_Atlas.webp` | Glyph atlas, lossless WebP (124 KiB; the same atlas as PNG is 269 KiB). Pass `--wiki-file Combat_Icon_Atlas.png` for PNG. |
| `combat-icons.css` | The stylesheet. The atlas URL points at the wiki upload. |
| `icon-list.wikitext` | Every icon with its name, for the template's page (Template:CombatIcon/list). |
| `icons.json` | Icon ids, types, atlas cells and any warnings, for templates or modules. Icons with their own frame also have a `frame` field. The next run also reads this file to keep every icon in its cell (see below). |
| `preview.html` | Local page showing every CSS icon next to its source PNG, at several sizes and on light or dark backgrounds. |

The output is deterministic, so re-running without changes produces identical files. `output/` is
committed, so `git status` shows which files changed and need deploying, which `deploy.py` does (see
[Deploying to the wiki](#deploying-to-the-wiki)).

The report lists icons that were added, changed or removed since the previous run (with the source
folder outside the repo, nothing else records this), plus any icon that was skipped.

## The wiki template

`wiki/CombatIcon.wikitext` is Template:CombatIcon. Its page documents the options, with examples and
the list of icons from `icon-list.wikitext`.

```
{{CombatIcon|Buff_ATK}}
{{CombatIcon|Buff_ATK|text=Attack Increase}}
{{CombatIcon|CC_Stunned|text=Stun|link=Category:Characters with stun skills|size=24}}
```

- The name may have spaces for underscores, as file names may. Without a name, only the text is shown.
- `text` follows the icon after a no-break space, and the icon is never left alone at the end of a
  line. The no-break space alone doesn't ensure that: browsers may break a line next to an
  inline-block even beside one, and in Chrome `icon&nbsp;text` put the icon on a line of its own at
  about one in ten of the widths tried. So, as in ItemCard, the icon and the text are in a label
  that doesn't wrap, and only the text inside it does. That kept the icon with the text's first word
  at every width tried, in every skin, including columns too narrow for the first word.
- `title` is the icon's tooltip and what screen readers read. Without it, the icon is labelled with
  its name (`Buff ATK`), unless it has text. Then it is `aria-hidden`, and screen readers read the text.
- `link` links the icon and its text together. It is written as `[[:Page|…]]`, so a category or file
  is linked rather than added to the page.
- `size` is the icon's height, in pixels (a bare number) or any CSS length. It sets
  `--combat-icon-size` on the icon.
- The stylesheet is loaded once per page, through Template:DeduplicateCSS.

## Markup

The template writes this markup, which other templates or modules can also write themselves:

```html
<span class="combat-icon mw-no-invert" data-icon="Buff_ATK" role="img" aria-label="Buff ATK" title="Buff ATK"></span>
<span class="combat-icon-label"><span class="combat-icon mw-no-invert" data-icon="Buff_ATK" aria-hidden="true"></span>&nbsp;<span class="combat-icon-text">Attack Increase</span></span>
```

- `data-icon` is the file name without `Combat_Icon_` and `.png`. Its prefix (`Buff_`, `Debuff_`,
  `CC_`, `Special_`, `Guide_`) selects the frame, so templates don't need to pass the type. The
  stylesheet overrides this for the few icons that have their own frame (at the moment only
  `Buff_Heal`, which is green). An unknown name shows an empty frame of its type, and an unknown
  type shows a grey (Guide) frame.
- `data-icon` is case-sensitive, and the game data doesn't always match the files' case. Its
  `IconSpriteName` fields spell six icons `Combat_Icon_DeBuff_Enhance…Rate`, but the files are
  `Combat_Icon_Debuff_…`. Names taken from the data need `DeBuff_` turned into `Debuff_`. There were
  no other mismatches as of 2026-11-02.
- Size: set `--combat-icon-size` (the icon's height, default `1.5em`) inline or on any ancestor,
  e.g. `style="--combat-icon-size:24px"`. The width follows the source 47:54 aspect ratio, and the
  box is the same as the source PNG's, so a CSS icon can replace `[[File:Combat_Icon_…png|x24px]]` 1:1.
- Inline, each icon is centred on the text by its frame rather than its box. CC and Special frames
  sit low and short in the shared canvas, so they are raised to line up with Buff and Debuff. The
  frames are centred on capitals and digits, half their height above the baseline (0.69ex, which is
  within 0.2px of that in common sans-serif fonts). Centred on the x-height, as `vertical-align: middle`
  does, they looked 1.4px low in Vector's 14px text and 1.6px low in Citizen's and Minerva's 16px.
- Negative top and bottom margins make the line leave room only for the frame and its shadow, not
  the empty canvas around them. At the default size, a line with icons is exactly as tall as one
  without in all four skins (before, up to 1.1px taller). The margins apply outside text as well:
  directly in a flex or grid container, an icon is placed by its frame, not by its 47×54 canvas.
  Add `margin: 0` where an icon has to line up box for box with a PNG, as `preview.html` does.
- `mw-no-invert` is only needed for the DarkMode extension, which dark-modes the default skin
  (Vector legacy) by inverting the whole page. That class makes it re-invert the icon, as it does
  for images. Citizen, Vector 2022 and Minerva have native dark themes and ignore it.

All of the above was checked against the live wiki: this markup survives the wikitext sanitizer, and
`combat-icons.css` passes TemplateStyles (plus TemplateStylesExtender) with no errors or dropped
declarations. The template was parsed by the wiki through TemplateSandbox, without saving, and its
page, list included, was rendered in Vector, Vector 2022, Citizen (day and night), Minerva and
Vector's Dark mode, with the stylesheet and atlas put in by the browser.

## Deploying to the wiki

```
python deploy.py                         # regenerate, then list what differs from the wiki
python deploy.py -wiki LOGIN PASSWORD    # ...and upload and publish it
```

`deploy.py` runs `generate_atlas.py`, then updates whatever differs from the wiki's copy. LOGIN and
PASSWORD are a bot password's, as for the scripts in wiki-scripts and bluearchivewiki. The bot
password needs grants to edit and create pages, and to upload and replace files. Without `-wiki`, the
script reads the wiki without logging in and changes nothing. The updates go in this order:

1. **File:Combat_Icon_Atlas.webp**, if its SHA-1 differs from `output/`'s. The stylesheet computes the
   file's URL from that exact name (MediaWiki's hashed upload path on `static.wikitide.net`), and the
   script stops if the wiki serves the file from anywhere else.
2. **Template:CombatIcon/styles.css**, from `output/combat-icons.css`. The `?v=<hash>` on its atlas
   URL changes with the atlas contents, so browsers fetch the new atlas along with the new CSS. The
   atlas goes first so that nothing fetches the new URL before the new file is there. The
   stylesheet also has to exist before the template is used, or pages show a TemplateStyles error.
3. **Template:CombatIcon**, from `wiki/CombatIcon.wikitext`.
4. **Template:CombatIcon/list**, from `output/icon-list.wikitext`. The template's page shows the list,
   which is a page of its own so that updating it doesn't re-render every page that uses the template.

Pages are compared as the wiki keeps them, with LF line ends and no trailing whitespace. Edits made
on the wiki to these pages are overwritten. `--diff` shows what would change. `--no-generate`
publishes `output/` as it is, and `--icons` and `--wiki-file` are passed on to `generate_atlas.py`.

Before changing anything, the script checks the new stylesheet against the wiki's (see below). If a
cell of the atlas file the wiki's stylesheet uses would hold another icon, it stops, because pages
still cached with the old stylesheet would show those icons with the wrong glyphs. That happens after
a re-pack, or when `output/icons.json` isn't the layout last deployed. `--allow-moves` publishes
anyway.

`generate_atlas.py` alone takes `--upload-base` if the wiki differs, and `--atlas-url` to point at
any other URL.

### Stable atlas layout

The CSS and the atlas reach readers through different caches. TemplateStyles CSS is part of each
rendered page, and the atlas is an uploaded file behind its own caches. For a while after an
update, some readers will get a newer stylesheet with an older atlas, or the other way round. To
keep that harmless, an icon never changes cells:

- An icon keeps the cell it was first given. New icons are appended after the last cell in use.
- An icon that disappears from the source (or stops matching its frame) keeps its cell and its glyph,
  copied from the previous atlas. If that atlas is gone, the cell is left empty and stays reserved;
  later icons never reuse it.
- The stylesheet doesn't depend on the atlas height. Glyphs are positioned in units of the icon size,
  so an older stylesheet still finds every glyph after the atlas grows.

In practice, a stale stylesheet shows every icon it knows about correctly, and a stale atlas shows
icons added since then as empty frames until it updates.

The layout is read from `output/icons.json`. To pack the atlas afresh (dropping vanished icons and
regrouping by type), delete that file and re-run. Doing so moves icons between cells, which brings
the mix-up risk back for one update, and `deploy.py` refuses it. You can avoid the risk by uploading
the re-packed atlas under a new name, e.g. `python deploy.py --wiki-file Combat_Icon_Atlas_2.webp`, so
that pages still using the old stylesheet keep loading the old atlas. Later runs keep that name, as
they keep the cells.

## How it works

**Frames.** Every icon of a type has an identical frame, so `fit_frames.py` takes the per-pixel
consensus of all icons of each type and fits a vector model to it by least squares. (An icon that
looks different from the rest of its type gets a frame of its own, fitted from that icon alone, and
`frames.json` lists the icons that frame is for.) The model is an
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

- **Game updates**: re-run `generate_atlas.py` once the data extract has been updated. It warns
  about icons that have transparent holes or draw outside their frame. At the moment only
  `Special_Omamori` does, where the top 2px of its string loop gets clipped.
- **Icons with a different frame** are skipped until they get a frame of their own. An icon is
  skipped when more than 3% of its silhouette disagrees with its type's frame; real icons stay under
  0.2%. To fit a frame for it, run e.g. `python fit_frames.py --add Heal --shape rect --for Buff_Heal`
  (which is how `Buff_Heal` got its green frame), then re-run `generate_atlas.py`. Shapes are `rect`,
  `house` (a Buff-style pointed top) and `shield` (a Debuff-style pointed bottom).
- **New icon type**: `generate_atlas.py` skips types that have no frame in `frames.json`. Fit one with
  `python fit_frames.py --add NewType --shape rect`, then re-run `generate_atlas.py`. Adding a frame
  leaves the existing frames and the shared shadow as they are.
- **Changed frame artwork**: `python fit_frames.py` refits every frame in `frames.json` and the shadow
  they share. Glyphs can change slightly when their frame moves, and the report lists those as changed.

## Limitations

- Glyphs are 1× raster art, so they soften once an icon is shown larger than about 54 device pixels
  tall. The frames stay sharp.
- CSS backgrounds are skipped when printing unless the reader enables "background graphics", and
  TemplateStyles rejects `print-color-adjust`, so the icons can't opt out of this.
