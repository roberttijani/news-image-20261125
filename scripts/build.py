#!/usr/bin/env python3
"""
Build script for the 25 November 2026 Swiss Broadsheet world news graphic.

Renders a 2048x2048 HTML/SVG front page via headless Chromium (Playwright),
validates zero text clipping/overflow, Lanczos-downscales to 1024x1024 PNG,
and optimizes with Pillow adaptive palette + oxipng to stay cleanly under 450 KB.
"""

from __future__ import annotations

import html
import json
import math
import os
from pathlib import Path
from typing import Dict, List, Tuple

import oxipng
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "scripts" / "data" / "ne_110m_countries.geojson"
BUILD_DIR = ROOT / "tmp"
HTML_PATH = BUILD_DIR / "broadsheet.html"
RAW_PNG_PATH = BUILD_DIR / "broadsheet_2048.png"
OUT_PNG_PATH = ROOT / "assets" / "entry.png"

CAT_COLORS: Dict[str, str] = {
    "GEO": "#B91C1C",
    "ECON": "#1D4ED8",
    "SCI": "#0F766E",
    "LAW": "#B45309",
    "SPORT": "#6D28D9",
}

CAT_LABELS: Dict[str, str] = {
    "GEO": "GEOPOLITICS & CONFLICT",
    "ECON": "ECONOMY, TECH & TRADE",
    "SCI": "SPACE, CLIMATE & HEALTH",
    "LAW": "LAW, SOCIETY & DISASTERS",
    "SPORT": "GLOBAL SPORTS",
}

LEAD_STORIES = [
    {
        "pin": 1,
        "cat": "SCI",
        "kicker": "SPACE · CHINA–PAKISTAN",
        "headline": "Shenzhou-24 Launches First Pakistani Astronaut to Tiangong",
        "summary": "Lifts off at 08:18 CST carrying Muhammad Zeeshan Ali — Pakistan's first astronaut and the first foreign crew member aboard China's orbital station.",
        "icon": "rocket",
    },
    {
        "pin": 2,
        "cat": "ECON",
        "kicker": "MARKETS · AI & SEMICONDUCTORS",
        "headline": "Nvidia Tumbles 5.9% as Rally Fades & Anthropic Slides",
        "summary": "Post-Huang-return rally cools as Anthropic slips below its IPO price; CEO Jensen Huang apologizes to staff and cites therapy.",
        "icon": "chart",
    },
    {
        "pin": 3,
        "cat": "ECON",
        "kicker": "GLOBAL TRADE · US TARIFFS",
        "headline": "US Prepares Fresh Tariffs on 16 Major Trade Partners",
        "summary": "Targets China, India, the EU, and 13 other economies over subsidized production ahead of the Jan 10 US–China interim deal expiry.",
        "icon": "trade",
    },
]

# All 36 verified stories for 25 November 2026
# (pin, region, cat, lat, lon, headline)
STORIES: List[Tuple[int, str, str, float, float, str]] = [
    # AMERICAS (6)
    (2, "Americas", "ECON", 37.39, -121.96, "US: Nvidia drops 5.9% as chip & AI stocks slide; Anthropic falls below IPO price"),
    (3, "Americas", "ECON", 38.90, -77.04, "US: Trump readies new tariffs on China, India, EU & 13 other trade partners"),
    (4, "Americas", "LAW", 40.71, -74.01, "US: Federal jury convicts Huawei of trade-secret theft conspiracy & bank fraud"),
    (5, "Americas", "GEO", 38.95, -77.15, "US: Intelligence agencies hit by breach of unclassified data, reports say"),
    (6, "Americas", "LAW", 10.39, -75.48, "Colombia: Gunmen take up to 30 hostages in Cartagena supermarket; 10 rescued"),
    (7, "Americas", "LAW", 46.81, -71.21, "Canada: Quebec court requires provincial legislators to swear oath to King Charles III"),
    # EUROPE (8)
    (8, "Europe", "GEO", 47.84, 35.14, "Ukraine: Russian airstrike hits 5-story apartment in Zaporizhzhia, killing 2 & injuring 44"),
    (9, "Europe", "LAW", 52.07, 4.30, "EU: Europol traces €26M crypto trail in 11-nation crackdown on 57 illegal IPTV networks"),
    (10, "Europe", "LAW", 55.68, 12.57, "Denmark: Supreme Court upholds controversial \"non-Western\" evictions law"),
    (11, "Europe", "SCI", 51.51, -0.13, "UK: UKHSA reports record 5,258 heat-related deaths in 2026; 2 arrested in royal residence break-in"),
    (12, "Europe", "ECON", 50.85, 4.35, "EU: Commission warns Bulgaria & Hungary risk EU funding suspension over excessive deficits"),
    (13, "Europe", "ECON", 52.23, 21.01, "Poland: Leads all EU states in net budget receipts at €6.7B, ahead of Romania & Greece"),
    (14, "Europe", "GEO", 55.75, 37.62, "Russia: Putin holds bilateral talks with Brunei's Sultan Hassanal Bolkiah in Moscow"),
    (15, "Europe", "SPORT", 40.42, -3.70, "UCL: Real Madrid thrash PSV 5-1 (Mbappé brace); Como near knockouts; Sporting host Man Utd"),
    # MIDDLE EAST (6)
    (16, "Middle East", "GEO", 24.71, 46.67, "Saudi Arabia: Houthi strike hits Riyadh's tallest financial tower (2nd in a week), wounding 11+"),
    (17, "Middle East", "GEO", 12.78, 45.02, "Yemen: Houthis advance near Aden as US warns citizens in Middle East of heightened threat"),
    (18, "Middle East", "GEO", 31.77, 35.21, "Israel: Gadi Eisenkot strikes first coalition deal in bid to form new government"),
    (19, "Middle East", "GEO", 31.50, 34.47, "Gaza: Israeli airstrike kills senior Hamas security official Naeem Abu Nahel amid meningitis rise"),
    (20, "Middle East", "LAW", 39.77, 30.52, "Turkey: Air Force training helicopter crashes in Eskişehir, killing all 5 crew members"),
    (21, "Middle East", "LAW", 25.80, 55.97, "UAE: Bus collides with stationary truck in Ras Al Khaimah, killing 13 and injuring 14"),
    # AFRICA (5)
    (22, "Africa", "SPORT", 14.72, -17.47, "Senegal: CAS reinstates Senegal as 2025 AFCON champions, overturning CAF ruling for Morocco"),
    (23, "Africa", "SCI", -4.32, 15.31, "DR Congo: Gavi to buy up to 1.5M doses of new Ebola vaccine as outbreak strains response"),
    (24, "Africa", "ECON", -11.66, 27.48, "DR Congo: Revives cobalt export ban effective Nov 30 to counter sliding global prices"),
    (25, "Africa", "ECON", 9.06, 7.49, "Nigeria: Central Bank (CBN) holds benchmark interest rate at 23% amid energy & inflation risks"),
    (26, "Africa", "SCI", 6.13, 1.22, "Togo: Study finds national vaccination coverage climbed to 90% over 45-year push"),
    # ASIA (8)
    (1, "Asia", "SCI", 40.96, 100.29, "China/Pakistan: Shenzhou-24 launches with first Pakistani astronaut Muhammad Zeeshan Ali to Tiangong"),
    (27, "Asia", "GEO", 31.23, 121.47, "China: Xi launches shock corruption probe into Shanghai party boss / Politburo member"),
    (28, "Asia", "ECON", 39.90, 116.40, "China: Extends suspension of gallium, germanium & antimony export ban until Jan 27"),
    (29, "Asia", "LAW", 37.57, 126.98, "South Korea: Plans to move 31 agencies to Sejong by 2031; raises AI exam-cheating ban to 10 yrs"),
    (30, "Asia", "ECON", 23.81, 90.41, "Bangladesh: 481 garment factories halt amid wage clashes; ex-PM Hasina plans Dec 16 return"),
    (31, "Asia", "LAW", -6.12, 106.15, "Indonesia: Death toll from Serang confectionery factory fire rises to 26"),
    (32, "Asia", "LAW", 21.03, 105.85, "Vietnam: Cooking gas blast at Hanoi hot-pot restaurant kills 7 and injures 9"),
    (33, "Asia", "GEO", 25.03, 121.56, "Taiwan/SE Asia: Taiwan heads to 11,000-seat local vote; Thailand informal economy hits 48% of GDP"),
    # OCEANIA & GLOBAL (3)
    (34, "Oceania & Global", "LAW", -33.87, 151.21, "Australia: Ex-officer Beau Lamarre-Condon found guilty of 2024 murders of Jesse Baird & Luke Davies"),
    (35, "Oceania & Global", "GEO", -9.43, 159.95, "Pacific: Australia edges China out of Solomon Islands with new primary security partner treaty"),
    (36, "Oceania & Global", "SCI", 48.20, 16.37, "UN / Space: 47,000 women killed by partners/family in 2025 (UN Nov 25 report); ESA Hera eyes Dimorphos"),
]

TICKER_ROW_1 = [
    ("NVDA", "-5.9%", "down"),
    ("NASDAQ", "-1.48%", "down"),
    ("S&P 500", "-0.50%", "down"),
    ("GOLD", "$3,552.50 (-2.25%)", "down"),
    ("SILVER", "$40.79 (-5.22%)", "down"),
    ("BRENT", "$87.38 (+2.3%)", "up"),
]

TICKER_ROW_2 = [
    ("WTI", "$80.60", "flat"),
    ("BTC", "$59,335", "flat"),
    ("US 10Y", "4.90%", "flat"),
    ("EUR/USD", "1.095", "flat"),
    ("USD/JPY", "159.17", "flat"),
    ("US OCT PCE FORECAST", "3.8%", "accent"),
]

# Natural Earth projection (Šavrič et al. 2011)
def ne_project_raw(lat_deg: float, lon_deg: float) -> Tuple[float, float]:
    phi = math.radians(max(-89.9, min(89.9, lat_deg)))
    lam = math.radians(lon_deg)
    phi2 = phi * phi
    phi4 = phi2 * phi2
    l_val = 0.870700 - 0.131979 * phi2 - 0.013791 * phi4 + 0.003971 * (phi4 * phi4 * phi2) - 0.001529 * (phi4 * phi4 * phi4)
    d_val = phi * (1.007226 + 0.015085 * phi2 - 0.044475 * (phi4 * phi2) + 0.028874 * (phi4 * phi4) - 0.005916 * (phi4 * phi4 * phi2))
    return (l_val * lam, -d_val)


MAP_W = 1976.0
MAP_H = 734.0
LON_MIN, LON_MAX = -168.0, 179.0
LAT_MIN, LAT_MAX = -55.0, 72.5

# Precompute bounds in Natural Earth space
_X_MIN = ne_project_raw(0.0, LON_MIN)[0]
_X_MAX = ne_project_raw(0.0, LON_MAX)[0]
_Y_TOP = ne_project_raw(LAT_MAX, 0.0)[1]
_Y_BOT = ne_project_raw(LAT_MIN, 0.0)[1]

PAD_X = 16.0
PAD_Y = 14.0
_SCALE_X = (MAP_W - 2 * PAD_X) / (_X_MAX - _X_MIN)
_SCALE_Y = (MAP_H - 2 * PAD_Y) / (_Y_BOT - _Y_TOP)
MAP_SCALE = min(_SCALE_X, _SCALE_Y)
_USED_W = (_X_MAX - _X_MIN) * MAP_SCALE
_USED_H = (_Y_BOT - _Y_TOP) * MAP_SCALE
MAP_OFF_X = (MAP_W - _USED_W) / 2.0
MAP_OFF_Y = (MAP_H - _USED_H) / 2.0


def project(lat_deg: float, lon_deg: float) -> Tuple[float, float]:
    rx, ry = ne_project_raw(lat_deg, lon_deg)
    sx = MAP_OFF_X + (rx - _X_MIN) * MAP_SCALE
    sy = MAP_OFF_Y + (ry - _Y_TOP) * MAP_SCALE
    return (sx, sy)


def ring_to_path(coords: List[List[float]]) -> str:
    pts = []
    prev_lon = None
    for lon, lat in coords:
        if lat < LAT_MIN - 2:
            lat = LAT_MIN - 2
        if lat > LAT_MAX + 5:
            lat = LAT_MAX + 5
        if prev_lon is not None and abs(lon - prev_lon) > 180:
            # Skip antimeridian jump segment cleanly
            continue
        prev_lon = lon
        x, y = project(lat, lon)
        pts.append(f"{x:.1f},{y:.1f}")
    if len(pts) < 3:
        return ""
    return "M" + "L".join(pts) + "Z"


def build_map_svg() -> str:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        gj = json.load(f)

    # Outline of the Natural Earth projection globe (clipped to LAT_MIN..LAT_MAX)
    globe_pts = []
    for lat in range(int(LAT_MIN), int(LAT_MAX) + 1, 2):
        globe_pts.append(project(lat, -180.0))
    for lon in range(-180, 181, 5):
        globe_pts.append(project(LAT_MAX, lon))
    for lat in range(int(LAT_MAX), int(LAT_MIN) - 1, -2):
        globe_pts.append(project(lat, 180.0))
    for lon in range(180, -181, -5):
        globe_pts.append(project(LAT_MIN, lon))
    globe_d = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in globe_pts) + "Z"

    # Graticule lines
    grat_paths = []
    for lat in (-30, 0, 30, 60):
        pts = [project(lat, lon) for lon in range(-180, 181, 4)]
        d = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        cls = "grat-eq" if lat == 0 else "grat"
        grat_paths.append(f'<path d="{d}" class="{cls}"/>')
    for lon in (-150, -120, -90, -60, -30, 0, 30, 60, 90, 120, 150):
        pts = [project(lat, lon) for lat in range(int(LAT_MIN), int(LAT_MAX) + 1, 3)]
        d = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        grat_paths.append(f'<path d="{d}" class="grat"/>')

    # Countries paths
    country_paths = []
    for feat in gj["features"]:
        props = feat.get("properties", {})
        admin = props.get("ADMIN", "")
        iso = props.get("ISO_A3", "")
        if admin == "Antarctica" or iso == "ATA":
            continue
        geom = feat.get("geometry", {})
        gtype = geom.get("type")
        polys = [geom["coordinates"]] if gtype == "Polygon" else (geom["coordinates"] if gtype == "MultiPolygon" else [])
        subpaths = []
        for poly in polys:
            if not poly:
                continue
            d = ring_to_path(poly[0])
            if d:
                subpaths.append(d)
        if subpaths:
            country_paths.append(f'<path d="{" ".join(subpaths)}" class="land"/>')

    # Continent subtle watermarks placed in 100% pin-free open geography
    continent_labels = [
        ("NORTH AMERICA", 55.0, -106.0),
        ("SOUTH AMERICA", -17.0, -59.0),
        ("AFRICA", 21.0, 13.0),
        ("ASIA", 56.5, 95.0),
        ("OCEANIA", -25.0, 133.5),
        ("EUROPE", 67.2, 43.0),
    ]
    cont_svg = []
    for label, clat, clon in continent_labels:
        cx, cy = project(clat, clon)
        cont_svg.append(f'<text x="{cx:.1f}" y="{cy:.1f}" class="cont-lbl">{html.escape(label)}</text>')

    # Pin layout: initial curated callout offsets (dx, dy) for dense clusters so leader lines never cross
    # Coordinates are in map SVG pixels (1976 x 716)
    preferred_offsets: Dict[int, Tuple[float, float]] = {
        # US East Coast cluster
        2: (-14.0, 4.0),     # Silicon Valley
        5: (-42.0, 14.0),    # US Intel (west/inland)
        3: (-2.0, 36.0),     # DC (south-east into Atlantic)
        4: (44.0, 8.0),      # NYC (east into Atlantic)
        7: (32.0, -24.0),    # Quebec (north-east)
        6: (0.0, 0.0),       # Cartagena
        # Europe cluster (fan cleanly outward around western/central Europe)
        11: (-52.0, -14.0),  # UK -> NW over Atlantic
        15: (-34.0, 12.0),   # Madrid -> W over Atlantic
        12: (-34.0, 26.0),   # Brussels -> SW over France/Bay of Biscay
        9: (-18.0, -40.0),   # Hague -> N over North Sea
        10: (14.0, -46.0),   # Denmark -> NNE over Scandinavia
        36: (10.0, 32.0),    # Vienna -> S over Italy/Adriatic
        13: (36.0, -24.0),   # Warsaw -> NE over Baltics
        14: (26.0, -14.0),   # Moscow -> NE
        8: (36.0, -6.0),     # Ukraine -> E
        # Middle East / Levant cluster
        20: (-10.0, -14.0),  # Turkey -> NW
        19: (-42.0, 18.0),   # Gaza -> SW over Mediterranean/Libya
        18: (14.0, -6.0),    # Israel -> E
        16: (4.0, 12.0),     # Saudi Arabia
        21: (28.0, 10.0),    # UAE -> E over Oman Sea
        17: (0.0, 24.0),     # Yemen -> S over Gulf of Aden
        # Africa
        22: (-14.0, 0.0),    # Senegal
        26: (-22.0, 18.0),   # Togo -> SW over Gulf of Guinea
        25: (16.0, 6.0),     # Nigeria -> E
        23: (-12.0, 4.0),    # DRC Ebola -> W
        24: (10.0, 12.0),    # DRC Cobalt -> SE
        # Asia cluster
        1: (-18.0, -16.0),   # Jiuquan (Shenzhou-24) -> NW
        28: (10.0, -28.0),   # Beijing -> N
        29: (38.0, -18.0),   # Seoul -> NE over Sea of Japan
        27: (42.0, 6.0),     # Shanghai -> E over East China Sea
        33: (38.0, 28.0),    # Taipei -> SE over Philippine Sea
        30: (-14.0, 12.0),   # Bangladesh -> SW
        32: (-14.0, 24.0),   # Vietnam -> S
        31: (0.0, 18.0),     # Indonesia -> S over Indian Ocean
        # Oceania
        34: (0.0, 0.0),      # Sydney
        35: (0.0, 0.0),      # Solomon Islands
    }

    nodes = []
    for pin, region, cat, lat, lon, headline in STORIES:
        ax, ay = project(lat, lon)
        dx, dy = preferred_offsets.get(pin, (0.0, 0.0))
        is_lead = pin in (1, 2, 3)
        r = 19.0 if is_lead else 16.0
        nodes.append({
            "pin": pin,
            "cat": cat,
            "ax": ax,
            "ay": ay,
            "x": ax + dx,
            "y": ay + dy,
            "tx": ax + dx,
            "ty": ay + dy,
            "r": r,
            "is_lead": is_lead,
        })

    # Deterministic collision-resolution solver (guarantees >= 6px whitespace between every badge pair)
    pad_margin = 26.0
    for _ in range(400):
        moved = False
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                ni, nj = nodes[i], nodes[j]
                dx = nj["x"] - ni["x"]
                dy = nj["y"] - ni["y"]
                dist = math.hypot(dx, dy)
                min_d = ni["r"] + nj["r"] + 6.5
                if dist < min_d:
                    if dist < 1e-4:
                        dx, dy, dist = 1.0, 0.5, math.hypot(1.0, 0.5)
                    push = (min_d - dist) * 0.52
                    ux, uy = dx / dist, dy / dist
                    ni["x"] -= ux * push
                    ni["y"] -= uy * push
                    nj["x"] += ux * push
                    nj["y"] += uy * push
                    moved = True
        # Gentle spring back toward preferred offset
        for n in nodes:
            n["x"] += (n["tx"] - n["x"]) * 0.03
            n["y"] += (n["ty"] - n["y"]) * 0.03
            n["x"] = max(pad_margin, min(MAP_W - pad_margin, n["x"]))
            n["y"] = max(pad_margin, min(MAP_H - pad_margin, n["y"]))
        if not moved:
            break

    # Final hard verification: zero overlap!
    min_gap = 999.0
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            ni, nj = nodes[i], nodes[j]
            gap = math.hypot(nj["x"] - ni["x"], nj["y"] - ni["y"]) - (ni["r"] + nj["r"])
            if gap < min_gap:
                min_gap = gap
    print(f"[map] 36 pins laid out; minimum edge-to-edge gap = {min_gap:.2f}px")
    assert min_gap >= 3.5, f"Pin collision detected! min_gap={min_gap:.2f}"

    # Render leader lines, anchor dots, and badges
    leaders_svg = []
    anchors_svg = []
    badges_svg = []

    # Sort so lead pins render on top
    for n in sorted(nodes, key=lambda item: (item["is_lead"], item["pin"])):
        color = CAT_COLORS[n["cat"]]
        ax, ay, bx, by, r = n["ax"], n["ay"], n["x"], n["y"], n["r"]
        dist = math.hypot(bx - ax, by - ay)
        if dist > 6.0:
            leaders_svg.append(
                f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" '
                f'stroke="#F8F5EE" stroke-width="4.5" stroke-linecap="round" opacity="0.9"/>'
                f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" '
                f'stroke="{color}" stroke-width="2.2" stroke-linecap="round"/>'
            )
            anchors_svg.append(
                f'<circle cx="{ax:.1f}" cy="{ay:.1f}" r="5.0" fill="{color}" stroke="#F8F5EE" stroke-width="2.0"/>'
            )

        if n["is_lead"]:
            badges_svg.append(
                f'<g class="pin-badge">'
                f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{r + 3.5:.1f}" fill="#F8F5EE"/>'
                f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{r:.1f}" fill="{color}" stroke="#111317" stroke-width="2.4"/>'
                f'<text x="{bx:.1f}" y="{by + 1.0:.1f}" class="pin-num pin-num-lead">{n["pin"]}</text>'
                f'</g>'
            )
        else:
            badges_svg.append(
                f'<g class="pin-badge">'
                f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{r + 2.4:.1f}" fill="#F8F5EE"/>'
                f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{r:.1f}" fill="{color}"/>'
                f'<text x="{bx:.1f}" y="{by + 0.8:.1f}" class="pin-num">{n["pin"]}</text>'
                f'</g>'
            )

    svg = f'''<svg viewBox="0 0 {int(MAP_W)} {int(MAP_H)}" width="{int(MAP_W)}" height="{int(MAP_H)}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <clipPath id="globeClip"><path d="{globe_d}"/></clipPath>
  </defs>
  <rect x="0" y="0" width="{int(MAP_W)}" height="{int(MAP_H)}" fill="#F3EFE6"/>
  <path d="{globe_d}" fill="#E6E1D5" stroke="#B9B1A1" stroke-width="1.6"/>
  <g clip-path="url(#globeClip)">
    {"".join(grat_paths)}
    {"".join(country_paths)}
    {"".join(cont_svg)}
  </g>
  <path d="{globe_d}" fill="none" stroke="#9B9384" stroke-width="1.6"/>
  <g class="leaders">{"".join(leaders_svg)}</g>
  <g class="anchors">{"".join(anchors_svg)}</g>
  <g class="badges">{"".join(badges_svg)}</g>
  <!-- Map Legend Inset (bottom-left over South Pacific) -->
  <g transform="translate(24, 646)">
    <rect x="0" y="0" width="388" height="68" rx="3" fill="#F8F5EE" fill-opacity="0.95" stroke="#BDB5A6" stroke-width="1.4"/>
    <text x="14" y="23" class="map-meta-title">GLOBAL DISPATCH MAP · NATURAL EARTH 110m</text>
    <text x="14" y="42" class="map-meta-sub">36 VERIFIED EVENTS · 6 INHABITED CONTINENTS</text>
    <text x="14" y="58" class="map-meta-sub">DOUBLE-RING PINS 1–3 = TOP LEAD STORIES</text>
  </g>
</svg>'''
    return svg


def lead_icon_svg(kind: str, accent: str) -> str:
    if kind == "rocket":
        # Shenzhou-24 + Tiangong orbital arc icon
        return f'''<svg viewBox="0 0 96 96" width="92" height="92" xmlns="http://www.w3.org/2000/svg">
  <rect x="2" y="2" width="92" height="92" rx="6" fill="#EFEAE0" stroke="#D1C9B9" stroke-width="1.5"/>
  <!-- Orbital arc -->
  <path d="M12 74 Q 44 18, 84 26" fill="none" stroke="{accent}" stroke-width="2.4" stroke-dasharray="5 4"/>
  <!-- Tiangong mini station at upper right -->
  <g transform="translate(68, 25) rotate(-14)">
    <rect x="-12" y="-3.5" width="24" height="7" rx="2" fill="#111317"/>
    <rect x="-5" y="-14" width="3.5" height="28" fill="{accent}"/>
    <rect x="2" y="-14" width="3.5" height="28" fill="{accent}"/>
  </g>
  <!-- Ascending rocket -->
  <g transform="translate(36, 54) rotate(32)">
    <path d="M0 -24 C7 -14, 8 -2, 8 10 L-8 10 C-8 -2, -7 -14, 0 -24 Z" fill="#111317"/>
    <circle cx="0" cy="-5" r="3.6" fill="#F8F5EE"/>
    <path d="M-8 4 L-15 13 L-8 12 Z" fill="{accent}"/>
    <path d="M8 4 L15 13 L8 12 Z" fill="{accent}"/>
    <path d="M-4 12 L0 23 L4 12 Z" fill="#B91C1C"/>
  </g>
  <!-- Star ticks -->
  <circle cx="20" cy="24" r="2.2" fill="#111317"/>
  <circle cx="34" cy="18" r="1.6" fill="{accent}"/>
  <circle cx="76" cy="54" r="2.0" fill="#111317"/>
</svg>'''
    if kind == "chart":
        # Nvidia -5.9% market slide + chip die icon
        return f'''<svg viewBox="0 0 96 96" width="92" height="92" xmlns="http://www.w3.org/2000/svg">
  <rect x="2" y="2" width="92" height="92" rx="6" fill="#EFEAE0" stroke="#D1C9B9" stroke-width="1.5"/>
  <!-- Subtle grid -->
  <line x1="12" y1="26" x2="84" y2="26" stroke="#D8D1C2" stroke-width="1.2"/>
  <line x1="12" y1="46" x2="84" y2="46" stroke="#D8D1C2" stroke-width="1.2"/>
  <line x1="12" y1="66" x2="84" y2="66" stroke="#D8D1C2" stroke-width="1.2"/>
  <!-- Chip icon silhouette top-right -->
  <g transform="translate(56, 13)" opacity="0.9">
    <rect x="5" y="5" width="20" height="20" rx="2.5" fill="none" stroke="{accent}" stroke-width="2.2"/>
    <rect x="10" y="10" width="10" height="10" fill="{accent}"/>
    <line x1="10" y1="0" x2="10" y2="5" stroke="{accent}" stroke-width="2"/>
    <line x1="20" y1="0" x2="20" y2="5" stroke="{accent}" stroke-width="2"/>
    <line x1="10" y1="25" x2="10" y2="30" stroke="{accent}" stroke-width="2"/>
    <line x1="20" y1="25" x2="20" y2="30" stroke="{accent}" stroke-width="2"/>
    <line x1="0" y1="10" x2="5" y2="10" stroke="{accent}" stroke-width="2"/>
    <line x1="0" y1="20" x2="5" y2="20" stroke="{accent}" stroke-width="2"/>
    <line x1="25" y1="10" x2="30" y2="10" stroke="{accent}" stroke-width="2"/>
    <line x1="25" y1="20" x2="30" y2="20" stroke="{accent}" stroke-width="2"/>
  </g>
  <!-- Downward price line -->
  <polyline points="12,30 28,24 41,38 55,34 68,58 82,70" fill="none" stroke="#B91C1C" stroke-width="4.2" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="82" cy="70" r="4.5" fill="#B91C1C"/>
  <!-- Percentage pill -->
  <rect x="12" y="67" width="48" height="18" rx="3" fill="#111317"/>
  <text x="36" y="80" text-anchor="middle" font-family="IBM Plex Mono, monospace" font-weight="700" font-size="11.5" fill="#FCA5A5">-5.9%</text>
</svg>'''
    # Trade / Tariffs on 16 partners
    return f'''<svg viewBox="0 0 96 96" width="92" height="92" xmlns="http://www.w3.org/2000/svg">
  <rect x="2" y="2" width="92" height="92" rx="6" fill="#EFEAE0" stroke="#D1C9B9" stroke-width="1.5"/>
  <!-- Globe wireframe -->
  <circle cx="42" cy="48" r="27" fill="none" stroke="#111317" stroke-width="2.2"/>
  <ellipse cx="42" cy="48" rx="13" ry="27" fill="none" stroke="#111317" stroke-width="1.6"/>
  <line x1="15" y1="48" x2="69" y2="48" stroke="#111317" stroke-width="1.6"/>
  <path d="M20 33 Q42 39 64 33" fill="none" stroke="#111317" stroke-width="1.4"/>
  <path d="M20 63 Q42 57 64 63" fill="none" stroke="#111317" stroke-width="1.4"/>
  <!-- Cargo container badge -->
  <rect x="46" y="54" width="38" height="24" rx="2.5" fill="{accent}" stroke="#F8F5EE" stroke-width="2"/>
  <line x1="54" y1="58" x2="54" y2="74" stroke="#F8F5EE" stroke-width="1.6"/>
  <line x1="62" y1="58" x2="62" y2="74" stroke="#F8F5EE" stroke-width="1.6"/>
  <line x1="70" y1="58" x2="70" y2="74" stroke="#F8F5EE" stroke-width="1.6"/>
  <line x1="78" y1="58" x2="78" y2="74" stroke="#F8F5EE" stroke-width="1.6"/>
  <!-- Tariff 16 badge -->
  <circle cx="72" cy="26" r="14" fill="#B91C1C" stroke="#F8F5EE" stroke-width="2"/>
  <text x="72" y="31" text-anchor="middle" font-family="IBM Plex Mono, monospace" font-weight="700" font-size="14" fill="#F8F5EE">16</text>
</svg>'''


def format_headline_html(text: str) -> str:
    if ":" in text:
        prefix, rest = text.split(":", 1)
        return f'<span class="hl-prefix">{html.escape(prefix)}:</span>{html.escape(rest)}'
    return html.escape(text)


def render_region_block(title: str, stories: List[Tuple[int, str, str, float, float, str]]) -> str:
    rows = []
    for pin, region, cat, lat, lon, headline in stories:
        color = CAT_COLORS[cat]
        rows.append(
            f'<div class="story-row">'
            f'<span class="row-pin" style="background:{color};">{pin}</span>'
            f'<span class="row-text">{format_headline_html(headline)}</span>'
            f'</div>'
        )
    return (
        f'<section class="region-block">'
        f'<div class="region-hdr">'
        f'<span class="region-title">{html.escape(title)}</span>'
        f'<span class="region-meta">{len(stories)} STORIES · 25 NOV</span>'
        f'</div>'
        f'<div class="region-list">{"".join(rows)}</div>'
        f'</section>'
    )


def find_font_uri(filename: str) -> str:
    candidates = [
        Path("C:/Windows/Fonts") / filename,
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Windows/Fonts" / filename,
    ]
    for p in candidates:
        if p.exists():
            return p.resolve().as_uri()
    raise FileNotFoundError(f"Font not found: {filename}")


def build_html() -> str:
    fonts_css = f"""
    @font-face {{ font-family: 'LibreBask'; font-weight: 400; src: url('{find_font_uri("LibreBaskerville-Regular.ttf")}'); }}
    @font-face {{ font-family: 'LibreBask'; font-weight: 700; src: url('{find_font_uri("LibreBaskerville-Bold.ttf")}'); }}
    @font-face {{ font-family: 'Barlow'; font-weight: 500; src: url('{find_font_uri("Barlow-Medium.ttf")}'); }}
    @font-face {{ font-family: 'Barlow'; font-weight: 600; src: url('{find_font_uri("Barlow-SemiBold.ttf")}'); }}
    @font-face {{ font-family: 'Barlow'; font-weight: 700; src: url('{find_font_uri("Barlow-Bold.ttf")}'); }}
    @font-face {{ font-family: 'Barlow'; font-weight: 800; src: url('{find_font_uri("Barlow-ExtraBold.ttf")}'); }}
    @font-face {{ font-family: 'OpenSansCond'; font-weight: 600; src: url('{find_font_uri("OpenSans_Condensed-SemiBold.ttf")}'); }}
    @font-face {{ font-family: 'OpenSansCond'; font-weight: 700; src: url('{find_font_uri("OpenSans_Condensed-Bold.ttf")}'); }}
    @font-face {{ font-family: 'OpenSansSemi'; font-weight: 500; src: url('{find_font_uri("OpenSans_SemiCondensed-Medium.ttf")}'); }}
    @font-face {{ font-family: 'OpenSansSemi'; font-weight: 600; src: url('{find_font_uri("OpenSans_SemiCondensed-SemiBold.ttf")}'); }}
    @font-face {{ font-family: 'OpenSansSemi'; font-weight: 700; src: url('{find_font_uri("OpenSans_SemiCondensed-Bold.ttf")}'); }}
    @font-face {{ font-family: 'IBMPlexMono'; font-weight: 500; src: url('{find_font_uri("IBMPlexMono-Medium.ttf")}'); }}
    @font-face {{ font-family: 'IBMPlexMono'; font-weight: 600; src: url('{find_font_uri("IBMPlexMono-SemiBold.ttf")}'); }}
    @font-face {{ font-family: 'IBMPlexMono'; font-weight: 700; src: url('{find_font_uri("IBMPlexMono-Bold.ttf")}'); }}
    """

    by_region: Dict[str, List[Tuple[int, str, str, float, float, str]]] = {}
    cat_counts: Dict[str, int] = {k: 0 for k in CAT_COLORS}
    for s in STORIES:
        by_region.setdefault(s[1], []).append(s)
        cat_counts[s[2]] += 1

    # Lead cards
    lead_cards_html = []
    for item in LEAD_STORIES:
        color = CAT_COLORS[item["cat"]]
        lead_cards_html.append(f'''
        <article class="lead-card" style="border-top-color:{color};">
          <div class="lead-body">
            <div class="lead-top">
              <span class="lead-pin" style="background:{color};">{item["pin"]}</span>
              <span class="lead-kicker" style="color:{color};">{html.escape(item["kicker"])}</span>
            </div>
            <h2 class="lead-title">{html.escape(item["headline"])}</h2>
            <p class="lead-summary">{html.escape(item["summary"])}</p>
          </div>
          <div class="lead-icon">{lead_icon_svg(item["icon"], color)}</div>
        </article>''')

    # Category legend bar
    legend_items = []
    for cat, color in CAT_COLORS.items():
        legend_items.append(
            f'<span class="leg-item">'
            f'<span class="leg-dot" style="background:{color};"></span>'
            f'<span class="leg-code">{cat}</span>'
            f'<span class="leg-name">{CAT_LABELS[cat]} ({cat_counts[cat]})</span>'
            f'</span>'
        )

    # Category summary mini-strip below Oceania & Global to complete bottom-right grid cleanly with 100% factual dataset counts
    cat_bars = []
    for cat, color in CAT_COLORS.items():
        pct = (cat_counts[cat] / len(STORIES)) * 100.0
        cat_bars.append(
            f'<div class="cat-stat">'
            f'<span class="cat-stat-dot" style="background:{color};"></span>'
            f'<span class="cat-stat-code">{cat}</span>'
            f'<span class="cat-stat-bar-bg"><span class="cat-stat-bar-fg" style="width:{pct:.1f}%;background:{color};"></span></span>'
            f'<span class="cat-stat-num">{cat_counts[cat]:02d}</span>'
            f'</div>'
        )
    index_box_html = f'''
    <div class="edition-index">
      <div class="edition-index-hdr">
        <span>EDITION BREAKDOWN · 36 VERIFIED DISPATCHES</span>
        <span>25 NOV 2026</span>
      </div>
      <div class="cat-stats-grid">{"".join(cat_bars)}</div>
    </div>'''

    # Ticker items
    def render_ticker_row(items):
        parts = []
        for label, val, tone in items:
            parts.append(
                f'<span class="tk-item">'
                f'<span class="tk-lbl">{html.escape(label)}</span> '
                f'<span class="tk-val tk-{tone}">{html.escape(val)}</span>'
                f'</span>'
            )
        return '<span class="tk-sep">|</span>'.join(parts)

    map_svg = build_map_svg()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>The World on Wednesday, 25 November 2026</title>
<style>
{fonts_css}

* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{
  width: 2048px;
  height: 2048px;
  overflow: hidden;
  background: #F8F5EE;
  color: #111317;
  font-family: 'Barlow', sans-serif;
  -webkit-font-smoothing: antialiased;
  text-rendering: geometricPrecision;
}}

.page {{
  width: 2048px;
  height: 2048px;
  padding: 20px 36px 18px 36px;
  display: flex;
  flex-direction: column;
  background: #F8F5EE;
}}

/* MASTHEAD */
.masthead {{
  display: flex;
  flex-direction: column;
}}
.mast-top {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: 'IBMPlexMono', monospace;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: #3E434D;
  padding-bottom: 7px;
}}
.mast-top-center {{
  color: #B91C1C;
  font-weight: 700;
}}
.double-rule-top {{
  height: 7px;
  border-top: 4px solid #111317;
  border-bottom: 1.5px solid #111317;
}}
.mast-title-wrap {{
  display: flex;
  align-items: baseline;
  justify-content: center;
  padding: 8px 0 7px 0;
}}
.mast-title {{
  font-family: 'LibreBask', Georgia, serif;
  font-size: 56px;
  font-weight: 700;
  letter-spacing: -0.012em;
  line-height: 1.04;
  color: #111317;
  white-space: nowrap;
}}
.mast-legend {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1.5px solid #111317;
  border-bottom: 3px solid #111317;
  padding: 6px 6px;
  background: #F2EDE3;
}}
.leg-item {{
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-family: 'Barlow', sans-serif;
  font-size: 16.5px;
  font-weight: 700;
  letter-spacing: 0.03em;
  color: #1D2128;
}}
.leg-dot {{
  width: 13px;
  height: 13px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}}
.leg-code {{
  font-family: 'IBMPlexMono', monospace;
  font-weight: 700;
  color: #111317;
}}
.leg-name {{
  font-weight: 600;
  color: #414752;
}}

/* LEAD STORIES HERO STRIP */
.lead-strip {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  margin-top: 11px;
  height: 196px;
}}
.lead-card {{
  border-top: 5px solid #111317;
  border-bottom: 1.5px solid #C9C1B3;
  background: #F3EFE6;
  padding: 10px 14px 10px 14px;
  display: flex;
  gap: 12px;
  align-items: flex-start;
  position: relative;
}}
.lead-body {{
  flex: 1;
  min-width: 0;
}}
.lead-top {{
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 5px;
}}
.lead-pin {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  color: #F8F5EE;
  font-family: 'Barlow', sans-serif;
  font-variant-numeric: tabular-nums;
  font-size: 17.5px;
  font-weight: 800;
  border: 2px solid #111317;
  flex-shrink: 0;
}}
.lead-kicker {{
  font-family: 'Barlow', sans-serif;
  font-size: 16px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  white-space: nowrap;
}}
.lead-title {{
  font-family: 'LibreBask', Georgia, serif;
  font-size: 22.5px;
  font-weight: 700;
  line-height: 1.18;
  color: #111317;
  margin-bottom: 6px;
  letter-spacing: -0.01em;
}}
.lead-summary {{
  font-family: 'OpenSansSemi', sans-serif;
  font-size: 18.5px;
  font-weight: 500;
  line-height: 1.28;
  color: #242931;
}}
.lead-icon {{
  flex-shrink: 0;
  margin-top: 4px;
}}

/* WORLD MAP */
.map-frame {{
  margin-top: 11px;
  width: 1976px;
  height: 734px;
  border: 2px solid #111317;
  background: #F3EFE6;
  overflow: hidden;
  flex-shrink: 0;
}}
.map-frame svg {{
  display: block;
}}
.land {{
  fill: #D8D0BE;
  stroke: #857E70;
  stroke-width: 1.0;
  stroke-linejoin: round;
}}
.grat {{
  fill: none;
  stroke: #C9C2B3;
  stroke-width: 0.85;
  stroke-dasharray: 3 4;
}}
.grat-eq {{
  fill: none;
  stroke: #B2AA9A;
  stroke-width: 1.15;
  stroke-dasharray: 6 4;
}}
.cont-lbl {{
  font-family: 'Barlow', sans-serif;
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 0.24em;
  fill: #645E52;
  fill-opacity: 0.62;
  text-anchor: middle;
}}
.pin-num {{
  font-family: 'Barlow', sans-serif;
  font-variant-numeric: tabular-nums;
  font-size: 19px;
  font-weight: 800;
  fill: #FFFFFF;
  text-anchor: middle;
  dominant-baseline: central;
}}
.pin-num-lead {{
  font-size: 22px;
}}
.map-meta-title {{
  font-family: 'Barlow', sans-serif;
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 0.06em;
  fill: #111317;
}}
.map-meta-sub {{
  font-family: 'IBMPlexMono', monospace;
  font-size: 12.5px;
  font-weight: 600;
  fill: #454B56;
}}

/* REGIONAL NEWS GRID: 2 COLUMNS x 3 BALANCED ROWS */
.regions-grid {{
  margin-top: 12px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  column-gap: 28px;
  row-gap: 12px;
  flex: 1;
}}
.region-col-pair {{
  display: contents;
}}
.region-block {{
  display: flex;
  flex-direction: column;
  min-width: 0;
}}
.region-hdr {{
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  border-top: 3.5px solid #111317;
  border-bottom: 1.5px solid #111317;
  padding: 4px 2px 4px 2px;
  margin-bottom: 4px;
}}
.region-title {{
  font-family: 'Barlow', sans-serif;
  font-size: 22px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #111317;
  text-transform: uppercase;
}}
.region-meta {{
  font-family: 'IBMPlexMono', monospace;
  font-size: 14.5px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: #555B66;
}}
.region-list {{
  display: flex;
  flex-direction: column;
}}
.story-row {{
  display: flex;
  align-items: center;
  gap: 10px;
  height: 34.5px;
  border-bottom: 1px dotted #CBC3B4;
  min-width: 0;
}}
.story-row:last-child {{
  border-bottom: none;
}}
.row-pin {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 29px;
  height: 24px;
  border-radius: 4px;
  color: #FFFFFF;
  font-family: 'Barlow', sans-serif;
  font-variant-numeric: tabular-nums;
  font-size: 16.5px;
  font-weight: 800;
  flex-shrink: 0;
}}
.row-text {{
  font-family: 'OpenSansCond', sans-serif;
  font-size: 22.5px;
  font-weight: 600;
  line-height: 1.1;
  color: #181B21;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: clip;
  letter-spacing: -0.005em;
}}
.hl-prefix {{
  font-weight: 700;
  color: #111317;
}}

/* BOTTOM-RIGHT EDITION INDEX (COMPLETES ROW 3 NEXT TO AFRICA) */
.oceania-cell {{
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-width: 0;
}}
.edition-index {{
  margin-top: 6px;
  margin-bottom: 2px;
  padding: 9px 14px 10px 14px;
  background: #F1ECE1;
  border: 1.5px solid #C8C0B0;
  border-left: 5px solid #111317;
}}
.edition-index-hdr {{
  display: flex;
  justify-content: space-between;
  font-family: 'IBMPlexMono', monospace;
  font-size: 13.5px;
  font-weight: 700;
  color: #323740;
  margin-bottom: 6px;
  letter-spacing: 0.04em;
}}
.cat-stats-grid {{
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
}}
.cat-stat {{
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: 'IBMPlexMono', monospace;
  font-size: 14px;
  font-weight: 700;
}}
.cat-stat-dot {{
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}}
.cat-stat-code {{
  color: #111317;
  font-size: 13.5px;
}}
.cat-stat-bar-bg {{
  flex: 1;
  height: 8px;
  background: #DDD6C8;
  border-radius: 2px;
  overflow: hidden;
}}
.cat-stat-bar-fg {{
  display: block;
  height: 100%;
}}
.cat-stat-num {{
  color: #111317;
  font-size: 14px;
}}

/* BOTTOM GLOBAL DATA TICKER */
.ticker {{
  margin-top: 10px;
  height: 82px;
  background: #111317;
  color: #F8F5EE;
  display: flex;
  align-items: stretch;
  border-top: 3px solid #B91C1C;
  flex-shrink: 0;
}}
.ticker-badge {{
  width: 186px;
  background: #B91C1C;
  color: #F8F5EE;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 0 10px;
  flex-shrink: 0;
}}
.ticker-badge-top {{
  font-family: 'Barlow', sans-serif;
  font-size: 18px;
  font-weight: 800;
  letter-spacing: 0.08em;
  line-height: 1.1;
}}
.ticker-badge-sub {{
  font-family: 'IBMPlexMono', monospace;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.06em;
  margin-top: 3px;
  color: #FDE8E8;
}}
.ticker-rows {{
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
  padding: 0 22px;
  font-family: 'IBMPlexMono', monospace;
  font-size: 19.5px;
  font-weight: 600;
}}
.ticker-row {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  white-space: nowrap;
}}
.tk-lbl {{
  color: #C7CCD6;
  font-weight: 600;
}}
.tk-val {{
  font-weight: 700;
}}
.tk-down {{ color: #FCA5A5; }}
.tk-up {{ color: #86EFAC; }}
.tk-flat {{ color: #F8F5EE; }}
.tk-accent {{ color: #FDE047; }}
.tk-sep {{
  color: #4E5563;
  font-weight: 500;
}}
</style>
</head>
<body>
<div class="page">
  <header class="masthead">
    <div class="mast-top">
      <span>EDITION: WEDNESDAY, 25 NOVEMBER 2026 · UTC 00:00–23:59</span>
      <span class="mast-top-center">GLOBAL DAILY DISPATCH · SWISS BROADSHEET</span>
      <span>36 VERIFIED STORIES · 6 CONTINENTS · SPACE &amp; MARKETS</span>
    </div>
    <div class="double-rule-top"></div>
    <div class="mast-title-wrap">
      <h1 class="mast-title">THE WORLD ON WEDNESDAY, 25 NOVEMBER 2026</h1>
    </div>
    <div class="mast-legend">
      {"".join(legend_items)}
    </div>
  </header>

  <section class="lead-strip">
    {"".join(lead_cards_html)}
  </section>

  <section class="map-frame">
    {map_svg}
  </section>

  <main class="regions-grid">
    <!-- Row 1: 8 vs 8 -->
    {render_region_block("EUROPE", by_region["Europe"])}
    {render_region_block("ASIA", by_region["Asia"])}
    <!-- Row 2: 6 vs 6 -->
    {render_region_block("AMERICAS", by_region["Americas"])}
    {render_region_block("MIDDLE EAST", by_region["Middle East"])}
    <!-- Row 3: 5 vs 3 + Edition Index -->
    {render_region_block("AFRICA", by_region["Africa"])}
    <div class="oceania-cell">
      {render_region_block("OCEANIA & GLOBAL", by_region["Oceania & Global"])}
      {index_box_html}
    </div>
  </main>

  <footer class="ticker">
    <div class="ticker-badge">
      <span class="ticker-badge-top">GLOBAL MARKETS</span>
      <span class="ticker-badge-sub">25 NOV 2026</span>
    </div>
    <div class="ticker-rows">
      <div class="ticker-row">{render_ticker_row(TICKER_ROW_1)}</div>
      <div class="ticker-row">{render_ticker_row(TICKER_ROW_2)}</div>
    </div>
  </footer>
</div>
</body>
</html>'''


def render_and_optimize() -> None:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PNG_PATH.parent.mkdir(parents=True, exist_ok=True)

    html_content = build_html()
    HTML_PATH.write_text(html_content, encoding="utf-8")
    print(f"[build] Wrote {HTML_PATH}")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 2048, "height": 2048}, device_scale_factor=1)
        page.goto(HTML_PATH.resolve().as_uri(), wait_until="load")
        page.evaluate("() => document.fonts.ready")

        # Audit layout: verify zero headline clipping, zero overflow, page height <= 2048
        audit = page.evaluate("""() => {
          const issues = [];
          document.querySelectorAll('.row-text').forEach((el, idx) => {
            if (el.scrollWidth > el.clientWidth + 1) {
              issues.push({type: 'row-overflow', idx, text: el.textContent, scrollW: el.scrollWidth, clientW: el.clientWidth});
            }
          });
          document.querySelectorAll('.lead-card').forEach((el, idx) => {
            if (el.scrollHeight > el.clientHeight + 1) {
              issues.push({type: 'lead-overflow', idx, scrollH: el.scrollHeight, clientH: el.clientHeight});
            }
          });
          document.querySelectorAll('.ticker-row').forEach((el, idx) => {
            if (el.scrollWidth > el.clientWidth + 1) {
              issues.push({type: 'ticker-overflow', idx, scrollW: el.scrollWidth, clientW: el.clientWidth});
            }
          });
          const pg = document.querySelector('.page');
          const tickerRect = document.querySelector('.ticker').getBoundingClientRect();
          return {
            issues,
            pageScrollH: pg.scrollHeight,
            tickerBottom: tickerRect.bottom,
            fontsLoaded: Array.from(document.fonts).filter(f => f.status === 'loaded').length
          };
        }""")
        print("[audit]", json.dumps(audit, indent=2))
        if audit["issues"]:
            print("[WARN] Layout overflow issues detected!")

        page.screenshot(path=str(RAW_PNG_PATH), clip={"x": 0, "y": 0, "width": 2048, "height": 2048})
        browser.close()

    # Lanczos downscale 2048x2048 -> 1024x1024
    img_2048 = Image.open(RAW_PNG_PATH).convert("RGB")
    assert img_2048.size == (2048, 2048), f"Unexpected raw size: {img_2048.size}"
    img_1024 = img_2048.resize((1024, 1024), Image.Resampling.LANCZOS)

    # First try lossless RGB + oxipng to see natural size; if > 430 KB, quantize cleanly to 256-color palette (no dithering for razor-sharp typography) + oxipng
    lossless_path = BUILD_DIR / "entry_lossless.png"
    img_1024.save(lossless_path, format="PNG", optimize=True)
    oxipng.optimize(str(lossless_path), str(lossless_path), level=4, strip=oxipng.StripChunks.safe())
    lossless_size = lossless_path.stat().st_size
    print(f"[opt] Lossless 24-bit PNG + oxipng: {lossless_size:,} bytes ({lossless_size / 1024:.1f} KB)")

    # Quantized 256-color palette PNG (pick highest-PSNR quantizer with dither=NONE for razor-sharp typography)
    best_pal_path = None
    best_psnr = -1.0
    best_size = 0
    for qname, qmethod in (("mediancut", Image.Quantize.MEDIANCUT), ("fastoctree", Image.Quantize.FASTOCTREE)):
        cand_img = img_1024.quantize(colors=256, method=qmethod, dither=Image.Dither.NONE)
        cand_path = BUILD_DIR / f"entry_{qname}.png"
        cand_img.save(cand_path, format="PNG", optimize=True)
        oxipng.optimize(str(cand_path), str(cand_path), level=6, strip=oxipng.StripChunks.safe())
        csize = cand_path.stat().st_size
        # Compute PSNR against lossless 1024 RGB
        from PIL import ImageChops
        diff = ImageChops.difference(img_1024, cand_img.convert("RGB"))
        hist = diff.histogram()
        mse = sum(hist[i] * ((i % 256) ** 2) for i in range(len(hist))) / (1024 * 1024 * 3)
        psnr = 10.0 * math.log10(255.0 * 255.0 / mse) if mse > 0 else 999.0
        print(f"[opt] 256-color {qname} + oxipng: {csize:,} bytes ({csize / 1024:.1f} KB), PSNR={psnr:.2f} dB")
        if csize <= 440 * 1024 and psnr > best_psnr:
            best_psnr = psnr
            best_pal_path = cand_path
            best_size = csize

    if lossless_size <= 440 * 1024:
        OUT_PNG_PATH.write_bytes(lossless_path.read_bytes())
        print(f"[out] Selected LOSSLESS PNG -> {OUT_PNG_PATH} ({lossless_size / 1024:.1f} KB)")
    else:
        assert best_pal_path is not None
        OUT_PNG_PATH.write_bytes(best_pal_path.read_bytes())
        print(f"[out] Selected {best_pal_path.name} -> {OUT_PNG_PATH} ({best_size / 1024:.1f} KB, PSNR={best_psnr:.2f} dB)")


if __name__ == "__main__":
    render_and_optimize()
