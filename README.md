# THE WORLD ON WEDNESDAY, 25 NOVEMBER 2026

[![make.fun · news-image-20261125](https://make.fun/badge/news-image-20261125.svg)](https://make.fun/bounty/news-image-20261125?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261125)
[![rank](https://make.fun/badge/news-image-20261125/roberttijani/news-image-20261125/rank.svg)](https://make.fun/bounty/news-image-20261125/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261125)
[![reward](https://make.fun/badge/news-image-20261125/roberttijani/news-image-20261125/reward.svg)](https://make.fun/bounty/news-image-20261125?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261125)

Deterministic submission for the [make.fun `news-image-20261125` bounty](https://make.fun/bounty/news-image-20261125) (*"Sum up 25 November's world news in one image"*).

![The World on Wednesday, 25 November 2026](assets/entry.png)

## Overview

- **Format**: 1024×1024 PNG (`assets/entry.png`, 185.2 KB), rendered at 2048×2048 from a custom Swiss broadsheet HTML/SVG composition via headless Chromium, Lanczos-downscaled to 1024×1024, and optimized with 256-color no-dither quantization + `oxipng`.
- **Content**: 36 verified 25 November 2026 stories across all 6 inhabited continents plus Space, Markets, and Global Sports:
  - Top masthead with exact date, story count, and category legend.
  - 3-column Lead Stories hero strip (Shenzhou-24 Pakistani astronaut, Nvidia -5.9% post-rally slide, US fresh tariffs on 16 partners) with custom vector editorial illustrations.
  - Central Natural Earth 110m world map (Natural Earth projection) with color-coded, collision-free numbered pins (`1`–`36`) and leader lines.
  - 6 regional news blocks (Europe, Asia, Americas, Middle East, Africa, Oceania & Global) with crisp 1-line dated headlines matching each map pin.
  - Bottom global market data ticker for 25 November 2026.

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
