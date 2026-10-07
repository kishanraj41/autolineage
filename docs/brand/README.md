# AutoLineage brand assets

The mark is a pipeline drawn as a tree: each bar is a step, and the short
accent bar with the dotted trail is the step that silently lost rows — the
thing AutoLineage localizes.

| Use | File |
|---|---|
| README / docs header, light background | `autolineage-lockup.svg` |
| README / docs header, dark background | `autolineage-lockup-dark.svg` |
| Mark only | `autolineage-mark.svg`, `autolineage-mark-dark.svg` |
| Avatar, app icon, slides | `autolineage-icon.svg`, `autolineage-icon-{512,256,128}.png` |
| Favicon / small UI (16–64 px, simplified geometry) | `autolineage-icon-small.svg`, `autolineage-icon-{64,48,32,16}.png`, `favicon.ico` |
| GitHub social preview (Settings → Social preview) | `autolineage-social-preview.png` (1280×640) |

## Palette

| | Hex | Use |
|---|---|---|
| Aubergine | `#2A1236` | ink on light, ground on dark |
| Lime | `#C8F03C` | accent on dark |
| Olive | `#6E9A00` | accent on light (lime is too faint on white) |
| Mist | `#F3EAF7` | bars and text on dark |

Wordmark: IBM Plex Mono (400 "auto", 600 "lineage"), outlined to paths so the
SVGs need no fonts installed. IBM Plex is licensed under the SIL Open Font
License 1.1.

Regenerate everything with `python make_brand.py <out_dir>` (needs
`fonttools`, `cairosvg`, `Pillow`, and the `@fontsource/ibm-plex-mono` /
`@fontsource/ibm-plex-sans` font files in `$PLEX_FONTS`, default `../fonts`).
