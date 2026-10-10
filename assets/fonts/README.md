# Local webfonts

These files are served from this site, without a runtime font CDN or preload.
Both families retain their complete modern Hangul coverage, Latin accents and
punctuation. Original SIL Open Font License 1.1 texts and copyright notices are
included as `gowun-batang/OFL.txt` and `pretendard/OFL.txt` in the public build.

## Installed files

| Family | Used weight | File | Bytes |
| --- | --- | --- | ---: |
| Gowun Batang 2.000 | 400 | gowun-batang/GowunBatang-Regular.woff2 | 535,088 |
| Gowun Batang 2.000 | 700 | gowun-batang/GowunBatang-Bold.woff2 | 491,780 |
| Pretendard 1.3.9, variable | 400, 500, 600 | pretendard/PretendardVariable.woff2 | 2,057,688 |

Total font binaries: **3,084,556 bytes (2.94 MiB)**. License files add 8,815 bytes.
Only weights 400–600 are exposed by the Pretendard `@font-face`; the original
variable binary supports a wider weight axis. No synthetic bold is needed for
the chosen styles. Both families provide the `tnum` OpenType feature.

## Official sources and conversion

- [Gowun Batang official repository](https://github.com/yangheeryu/Gowun-Batang),
  commit `4e73f5a9a004927220354f4b68a4c720da538147`, version 2.000.
  Sources: `fonts/ttf/GowunBatang-Regular.ttf` (8,433,296 bytes),
  `fonts/ttf/GowunBatang-Bold.ttf` (8,178,712 bytes), and `OFL.txt`.
  Converted the complete, unmodified fonts from TTF to genuine WOFF2 using the
  installed FontTools WOFF2 writer and Brotli 1.2.0. No glyph subsetting or
  outlines, metrics, family-name or license changes were made.
- [Pretendard official repository](https://github.com/orioncactus/pretendard/tree/v1.3.9),
  tag `v1.3.9`. The original binary is
  `packages/pretendard/dist/web/variable/woff2/PretendardVariable.woff2`;
  the original license is the repository-root `LICENSE`. No conversion.

## Loading decision

Downloaded and measured the official Pretendard alternatives at the same tag:

| Alternative | Bytes |
| --- | ---: |
| Full variable WOFF2 | 2,057,688 |
| Regular 400 static WOFF2 | 765,892 |
| Medium 500 static WOFF2 | 778,432 |
| SemiBold 600 static WOFF2 | 785,856 |
| Three static files combined | 2,330,180 |

The full variable file saves 272,492 bytes (11.7%) against the three static files.
The official `pretendardvariable-dynamic-subset.css` was also inspected: it uses
unicode-range blocks to load individual WOFF2 segments and can reduce first-page
transfer. This small, shared-font static archive uses the complete variable file
instead: one cached body font across all pages and a three-binary release list
that is easy to audit. This trades a larger initial download for fewer font
requests and simple offline/self-hosted packaging. No page-specific subset is
used, so new Korean nicknames and repertoire remain supported.

`assets/css/fonts.css` uses only relative local URLs and `font-display: swap`.
All public HTML pages load it before `site.css` and allow same-origin fonts with
`font-src 'self'`. Fonts never delay JSON rendering or hide the page. System
fonts immediately provide readable fallback text when downloads fail.
