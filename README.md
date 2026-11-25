# THE WORLD ON WEDNESDAY, 25 NOVEMBER 2026

[![make.fun · news-image-20261125](https://make.fun/badge/news-image-20261125.svg)](https://make.fun/bounty/news-image-20261125?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261125)
[![rank](https://make.fun/badge/news-image-20261125/roberttijani/news-image-20261125/rank.svg)](https://make.fun/bounty/news-image-20261125/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261125)
[![reward](https://make.fun/badge/news-image-20261125/roberttijani/news-image-20261125/reward.svg)](https://make.fun/bounty/news-image-20261125?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261125)

Deterministic **v2** submission for the [make.fun `news-image-20261125` bounty](https://make.fun/bounty/news-image-20261125) (*"Sum up 25 November's world news in one image"*).

![The World on Wednesday, 25 November 2026](assets/entry.png)

## Overview (v2)

- **Format**: 1024×1024 PNG (`assets/entry.png`, 219.8 KB), rendered at 2048×2048 from a custom Swiss illustrated broadsheet HTML/SVG composition via headless Chromium, Lanczos-downscaled to 1024×1024, and optimized with 256-color perceptual quantization + `oxipng` (37.49 dB PSNR).
- **Content**: 36 verified Wednesday, 25 November 2026 stories across all 6 inhabited continents plus Space, Markets, Cyber, Energy, and Sports:
  - **Zone 1 — Masthead**: Exact date, 07:00 GMT snapshot metadata, story/scene count, category breakdown, and `DATE CHECK ✓ WED 25 NOV 2026 UTC` badge.
  - **Zone 2 — 10 Custom-Drawn Pictorial Editorial Scenes (2×5 Grid, Pins #1–#10)**: Multi-color editorial SVG illustrations for Shenzhou-24 docking at Tiangong, KOSPI -6.2% AI rout, UK Energy Cap +26%, US tariffs on 16 partners, Riyadh tower strike, WHO Ebola teams trapped in Ituri, CIA breach & Microsoft Code Red, Eurostar strike halt, Vaibhav Sooryavanshi's 204 off 53, and the Australia–Solomons security pact.
  - **Zone 3 — Natural Earth 110m World Map**: Collision-free numbered pins (`1–10` double-ring scene heroes, `11–36` regional briefs), clean continent labels, and `DATE CHECK` verification seal.
  - **Zone 4 — 26-Story 6-Continent Brief (Pins #11–#36)**: Crisp 1-line dated briefs across Americas, Europe, Africa, Asia, Middle East, and Oceania & Global.
  - **Zone 5 — Global Markets Ticker (07:00 GMT)**: KOSPI, Nikkei, Shanghai, NVDA, Nasdaq, Dow, Gold, Silver, Brent, WTI, BTC, USD/JPY, and UK Cap +26%.

## Deterministic Execution (`program/v1`)

`main.ts` runs on Node 22+ with zero external dependencies and zero network calls:

```bash
node main.ts
```

It creates `/output` if needed and deterministically copies `assets/entry.png` to `/output/entry.png`.

## Rebuilding `assets/entry.png`

To regenerate the infographic locally from `scripts/build.py` and the Natural Earth 110m dataset (`scripts/data/ne_110m_countries.geojson`):

```bash
python scripts/build.py
```

## License

MIT — see [LICENSE](LICENSE).
