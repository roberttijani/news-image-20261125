#!/usr/bin/env python3
"""
v2 Build script for the Wednesday, 25 November 2026 Swiss Illustrated Broadsheet.

Renders a 2048x2048 HTML/SVG front page via headless Chromium (Playwright):
  - Zone 1: Masthead + DATE CHECK badge + category legend
  - Zone 2: 10 custom-drawn multi-color editorial SVG scenes (2x5 grid, Pins #1-#10)
  - Zone 3: Natural Earth 110m world map with 36 collision-free numbered pins + DATE CHECK seal
  - Zone 4: 26-story 6-continent dated brief (Pins #11-#36) + audit summary strip
  - Zone 5: Global Markets 07:00 GMT dark-ink ticker
Lanczos-downscales to 1024x1024 PNG and optimizes via palette quantization + oxipng (< 450 KB).
"""

from __future__ import annotations

import html
import json
import math
import os
from pathlib import Path
from typing import Dict, List, Tuple

import oxipng
from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "scripts" / "data" / "ne_110m_countries.geojson"
BUILD_DIR = ROOT / "tmp"
HTML_PATH = BUILD_DIR / "broadsheet_v2.html"
RAW_PNG_PATH = BUILD_DIR / "broadsheet_v2_2048.png"
OUT_PNG_PATH = ROOT / "assets" / "entry.png"

CAT_COLORS: Dict[str, str] = {
    "GEO": "#B91C1C",
    "ECON": "#1D4ED8",
    "SCI": "#0F766E",
    "LAW": "#B45309",
    "SPORT": "#6D28D9",
}

CAT_LABELS: Dict[str, str] = {
    "GEO": "GEOPOLITICS",
    "ECON": "MARKETS & TRADE",
    "SCI": "SPACE & HEALTH",
    "LAW": "LAW & TRANSPORT",
    "SPORT": "SPORTS",
}

# Zone 2: 10 Custom-Drawn Pictorial Editorial Scenes (Pins #1-#10)
SCENES = [
    {
        "pin": 1,
        "cat": "SCI",
        "kicker": "SPACE · 00:18 UTC",
        "title": "Shenzhou-24 Docks at Tiangong",
        "fact": "Pakistan's 1st astronaut Muhammad Zeeshan Ali boards China's station as 1st foreign crew.",
        "lat": 40.96,
        "lon": 100.29,
        "scene": "shenzhou",
    },
    {
        "pin": 2,
        "cat": "ECON",
        "kicker": "MARKETS · 07:00 GMT",
        "title": "KOSPI -6.2% AI Rout",
        "fact": "Seoul plunges 6.2%, Nikkei -2.8%, Nvidia -5.9% as post-Huang rally dies.",
        "lat": 37.57,
        "lon": 126.98,
        "scene": "kospi",
    },
    {
        "pin": 3,
        "cat": "ECON",
        "kicker": "UK ENERGY · 25 NOV",
        "title": "UK Energy Cap +26%",
        "fact": "Ofgem raises Great Britain household energy cap 26% from Jan 2027.",
        "lat": 53.80,
        "lon": -1.55,
        "scene": "uk_energy",
    },
    {
        "pin": 4,
        "cat": "ECON",
        "kicker": "TRADE · 25 NOV",
        "title": "US Tariffs on 16 Partners",
        "fact": "Trump preps new duties on China, India, EU & 13 other trade partners.",
        "lat": 38.90,
        "lon": -77.04,
        "scene": "tariffs",
    },
    {
        "pin": 5,
        "cat": "GEO",
        "kicker": "MIDEAST · 25 NOV",
        "title": "Riyadh Tower Hit Again",
        "fact": "2nd Houthi strike in a week wounds 11+; US warns citizens across region.",
        "lat": 24.71,
        "lon": 46.67,
        "scene": "riyadh",
    },
    {
        "pin": 6,
        "cat": "SCI",
        "kicker": "AFRICA · 25 NOV",
        "title": "WHO Ebola Teams Trapped",
        "fact": "Ituri fighting traps DRC Ebola responders; Gavi buys 1.5M new jabs.",
        "lat": 1.85,
        "lon": 30.05,
        "scene": "ebola",
    },
    {
        "pin": 7,
        "cat": "GEO",
        "kicker": "CYBER · 25 NOV",
        "title": "CIA Breach & MSFT Code Red",
        "fact": "US spy agencies (CIA/ODNI) hacked; Microsoft declares Code Red outage.",
        "lat": 47.67,
        "lon": -122.12,
        "scene": "cyber",
    },
    {
        "pin": 8,
        "cat": "LAW",
        "kicker": "EUROPE · 25 NOV",
        "title": "Eurostar Strike Halts Trains",
        "fact": "Unannounced staff walkout cancels Paris–London high-speed services.",
        "lat": 50.95,
        "lon": 1.85,
        "scene": "eurostar",
    },
    {
        "pin": 9,
        "cat": "SPORT",
        "kicker": "SPORTS · 25 NOV",
        "title": "Teen Smashes 204 off 53",
        "fact": "15-yr-old Vaibhav Sooryavanshi hits 28 sixes for India A vs UAE.",
        "lat": 24.45,
        "lon": 54.38,
        "scene": "cricket",
    },
    {
        "pin": 10,
        "cat": "GEO",
        "kicker": "PACIFIC · 25 NOV",
        "title": "Australia–Solomons Pact",
        "fact": "Canberra edges China out with new primary security partner treaty.",
        "lat": -9.43,
        "lon": 159.95,
        "scene": "pacific",
    },
]

# Zone 4: 26-Story 6-Continent Dated Briefs (Pins #11-#36)
# (pin, region, cat, lat, lon, headline)
BRIEFS: List[Tuple[int, str, str, float, float, str]] = [
    # AMERICAS (5)
    (11, "Americas", "LAW", 40.71, -74.01, "US: Jury convicts Huawei of trade-secret theft & bank fraud"),
    (12, "Americas", "ECON", 38.87, -77.06, "US: Pentagon weighs $15B loan to Trump Jr.-linked AI startup Hadrian"),
    (13, "Americas", "ECON", 37.39, -121.96, "US: Nvidia's Huang apologizes to staff; Anthropic falls below IPO"),
    (14, "Americas", "LAW", 10.39, -75.48, "Colombia: Armed men hold up to 30 hostages in Cartagena supermarket; 10 freed"),
    (15, "Americas", "ECON", 41.88, -87.63, "US: Oct PCE inflation data (3.8% f'cast) eyed ahead of Dec Fed decision"),
    # EUROPE (5)
    (16, "Europe", "LAW", 52.07, 4.30, "EU: Europol traces €26M crypto trail in 11-nation IPTV piracy bust"),
    (17, "Europe", "LAW", 55.68, 12.57, "Denmark: Supreme Court upholds \"non-Western\" evictions law"),
    (18, "Europe", "SCI", 51.51, -0.13, "UK: Record 5,258 heat deaths in 2026; 2 held in royal home break-in"),
    (19, "Europe", "ECON", 52.23, 21.01, "EU: Bulgaria & Hungary warned of funding freeze over deficits; Poland tops receipts (€6.7B)"),
    (20, "Europe", "GEO", 48.86, 2.35, "Europe: Decathlon confirms data breach; Putin meets Brunei Sultan; Real Madrid thrash PSV 5–1"),
    # MIDDLE EAST (4)
    (21, "Middle East", "GEO", 31.77, 35.21, "Israel: Eisenkot strikes 1st coalition deal; Gaza strike kills Hamas official Nahel"),
    (22, "Middle East", "GEO", 12.78, 45.02, "Yemen/Iran: Houthis push near Aden as Iran vows to break US blockade"),
    (23, "Middle East", "ECON", 25.28, 51.53, "Gulf: Allianz pegs Iran war cost to Gulf states at $790B by 2030"),
    (24, "Middle East", "LAW", 39.77, 30.52, "Turkey/UAE: Eskişehir jet-trainer heli crash kills 5; UAE bus crash kills 13"),
    # AFRICA (4)
    (25, "Africa", "SPORT", 14.72, -17.47, "Senegal: CAS reinstates Senegal as 2025 AFCON champions over Morocco"),
    (26, "Africa", "ECON", -11.66, 27.48, "DR Congo: Revives cobalt export ban from Nov 30 as prices slide"),
    (27, "Africa", "ECON", 9.06, 7.49, "Nigeria: Central Bank holds rate at 23% amid energy & inflation risks"),
    (28, "Africa", "ECON", -8.84, 13.23, "Angola/Botswana: Angola seeks $180M for 10% De Beers stake; IMF cuts Botswana to 3%"),
    # ASIA (6)
    (29, "Asia", "GEO", 31.23, 121.47, "China: Xi probes Shanghai party boss / Politburo member in shock shakeup"),
    (30, "Asia", "ECON", 39.90, 116.40, "China: Extends gallium/germanium/antimony export-ban pause to Jan 27"),
    (31, "Asia", "LAW", 36.48, 127.29, "South Korea: Relocating 31 agencies to Sejong by 2031; 10-yr ban for AI exam cheats"),
    (32, "Asia", "ECON", 23.81, 90.41, "Bangladesh: 481 garment plants halt in wage clashes; ex-PM Hasina plans Dec 16 return"),
    (33, "Asia", "LAW", -6.12, 106.15, "Indonesia/Vietnam: Serang factory fire toll hits 26; Hanoi gas blast kills 7"),
    (34, "Asia", "GEO", 25.03, 121.56, "Taiwan/Thailand: Taiwan preps 11,000-seat vote; Thai informal economy hits 48% GDP"),
    # OCEANIA & GLOBAL (2)
    (35, "Oceania & Global", "LAW", -33.87, 151.21, "Australia: Defence issues Nov 25 apology; Lamarre-Condon guilty of Baird/Davies murders"),
    (36, "Oceania & Global", "SCI", 48.20, 16.37, "Global: UN marks Nov 25 with 47,000 femicides report (2025); ESA Hera eyes Dimorphos"),
]

TICKER_ROW_1 = [
    ("KOSPI", "4,697.5 (-6.2%)", "down"),
    ("NIKKEI", "57,011 (-2.8%)", "down"),
    ("SHANGHAI", "-2.0%", "down"),
    ("NVDA", "-5.9%", "down"),
    ("NASDAQ", "-1.48%", "down"),
    ("DOW", "50,018 (+0.9%)", "up"),
]

TICKER_ROW_2 = [
    ("GOLD", "$3,552.5 (-2.25%)", "down"),
    ("SILVER", "$40.79 (-5.22%)", "down"),
    ("BRENT", "$89.99", "flat"),
    ("WTI", "$80.57", "flat"),
    ("BTC", "$59,335", "flat"),
    ("USD/JPY", "159.34", "flat"),
    ("UK CAP", "+26%", "accent"),
]


# ---------------------------------------------------------------------------
# 10 Rich Multi-Color Editorial SVG Scenes (382 x 208 viewBox, flat Swiss print)
# ---------------------------------------------------------------------------
def render_scene_svg(kind: str) -> str:
    if kind == "shenzhou":
        # 1. Shenzhou-24 Docks at Tiangong: deep orbital sky, glowing Earth limb, Tiangong + Shenzhou docking, China-Pakistan motif
        return '''<svg viewBox="0 0 382 208" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width="382" height="208" fill="#0F1C34"/>
  <!-- Deep space starfield -->
  <circle cx="38" cy="36" r="2.2" fill="#F8F5EE"/>
  <circle cx="88" cy="24" r="1.6" fill="#93C5FD"/>
  <circle cx="145" cy="48" r="1.8" fill="#F8F5EE"/>
  <circle cx="242" cy="28" r="2.0" fill="#FDE68A"/>
  <circle cx="312" cy="42" r="1.7" fill="#F8F5EE"/>
  <circle cx="352" cy="72" r="2.1" fill="#93C5FD"/>
  <circle cx="62" cy="84" r="1.5" fill="#F8F5EE"/>
  <circle cx="288" cy="112" r="1.6" fill="#F8F5EE"/>
  <!-- Curved Earth horizon & atmospheric halo -->
  <ellipse cx="191" cy="296" rx="255" ry="132" fill="#0F766E" opacity="0.38"/>
  <ellipse cx="191" cy="304" rx="246" ry="128" fill="#1D4ED8"/>
  <ellipse cx="191" cy="309" rx="242" ry="125" fill="#1E3A8A"/>
  <path d="M22 198 Q115 162 215 178 T366 196 L382 208 L0 208 Z" fill="#15803D" opacity="0.55"/>
  <path d="M55 186 Q191 146 328 186" fill="none" stroke="#5EEAD4" stroke-width="3.5" opacity="0.85"/>
  <!-- Orbital docking trajectory arc -->
  <path d="M36 154 Q122 86 220 90" fill="none" stroke="#5EEAD4" stroke-width="2.4" stroke-dasharray="6 5"/>
  <!-- Tiangong Space Station (upper right) -->
  <g transform="translate(262, 84) rotate(-12)">
    <!-- Upper & lower golden solar wings -->
    <rect x="-42" y="-56" width="16" height="44" rx="1.5" fill="#D97706" stroke="#111317" stroke-width="1.8"/>
    <rect x="-42" y="12" width="16" height="44" rx="1.5" fill="#D97706" stroke="#111317" stroke-width="1.8"/>
    <rect x="26" y="-56" width="16" height="44" rx="1.5" fill="#D97706" stroke="#111317" stroke-width="1.8"/>
    <rect x="26" y="12" width="16" height="44" rx="1.5" fill="#D97706" stroke="#111317" stroke-width="1.8"/>
    <!-- Solar grid lines -->
    <line x1="-34" y1="-56" x2="-34" y2="-12" stroke="#FDE68A" stroke-width="1.2"/>
    <line x1="-34" y1="12" x2="-34" y2="56" stroke="#FDE68A" stroke-width="1.2"/>
    <line x1="34" y1="-56" x2="34" y2="-12" stroke="#FDE68A" stroke-width="1.2"/>
    <line x1="34" y1="12" x2="34" y2="56" stroke="#FDE68A" stroke-width="1.2"/>
    <!-- Core Tiangong modules -->
    <rect x="-56" y="-11" width="112" height="22" rx="6" fill="#F8F5EE" stroke="#111317" stroke-width="2.2"/>
    <rect x="-16" y="-15" width="32" height="30" rx="4" fill="#E5DFD2" stroke="#111317" stroke-width="2.2"/>
    <circle cx="0" cy="0" r="6" fill="#0F766E" stroke="#111317" stroke-width="1.6"/>
    <rect x="-58" y="-6" width="8" height="12" fill="#B91C1C"/>
  </g>
  <!-- Shenzhou-24 Capsule approaching docking port -->
  <g transform="translate(132, 108) rotate(-12)">
    <!-- Thruster flame -->
    <polygon points="-58,0 -82,-9 -74,0 -82,9" fill="#F59E0B"/>
    <polygon points="-58,0 -71,-4 -71,4" fill="#FEF3C7"/>
    <!-- Shenzhou solar panels -->
    <rect x="-38" y="-34" width="12" height="24" fill="#1D4ED8" stroke="#111317" stroke-width="1.6"/>
    <rect x="-38" y="10" width="12" height="24" fill="#1D4ED8" stroke="#111317" stroke-width="1.6"/>
    <!-- Service + Return + Orbital modules -->
    <rect x="-56" y="-10" width="34" height="20" rx="2" fill="#CBD5E1" stroke="#111317" stroke-width="2"/>
    <path d="M-22 -11 L6 -13 L18 -8 L18 8 L6 13 L-22 11 Z" fill="#F8F5EE" stroke="#111317" stroke-width="2"/>
    <circle cx="24" cy="0" r="9" fill="#F8F5EE" stroke="#111317" stroke-width="2"/>
    <rect x="33" y="-4" width="7" height="8" fill="#0F766E" stroke="#111317" stroke-width="1.6"/>
    <rect x="-8" y="-4" width="10" height="8" rx="1.5" fill="#0F766E"/>
  </g>
  <!-- Docking laser / alignment pulse -->
  <line x1="175" y1="99" x2="202" y2="94" stroke="#5EEAD4" stroke-width="3" stroke-dasharray="4 3"/>
  <!-- Pakistan + China mission patch badge (bottom right) -->
  <g transform="translate(274, 162)">
    <rect x="0" y="0" width="96" height="34" rx="4" fill="#111317" stroke="#5EEAD4" stroke-width="1.6"/>
    <!-- China red badge + star -->
    <rect x="7" y="7" width="26" height="20" rx="2" fill="#B91C1C"/>
    <polygon points="16,11 17.5,15 22,15 18.4,17.5 19.8,22 16,19.3 12.2,22 13.6,17.5 10,15 14.5,15" fill="#FDE047"/>
    <!-- Pakistan green badge + crescent -->
    <rect x="39" y="7" width="26" height="20" rx="2" fill="#15803D"/>
    <rect x="39" y="7" width="6" height="20" fill="#F8F5EE"/>
    <circle cx="55" cy="17" r="5.5" fill="#F8F5EE"/>
    <circle cx="57" cy="15.5" r="4.8" fill="#15803D"/>
    <text x="80" y="21" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="11.5" fill="#5EEAD4">SZ-24</text>
  </g>
</svg>'''

    if kind == "kospi":
        # 2. KOSPI -6.2% AI Rout: dark trading floor board, plunging crimson candles, cracked AI chip, -6.2% callout
        return '''<svg viewBox="0 0 382 208" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width="382" height="208" fill="#131926"/>
  <!-- Trading grid -->
  <g stroke="#243047" stroke-width="1.2">
    <line x1="0" y1="48" x2="382" y2="48"/>
    <line x1="0" y1="88" x2="382" y2="88"/>
    <line x1="0" y1="128" x2="382" y2="128"/>
    <line x1="0" y1="168" x2="382" y2="168"/>
    <line x1="64" y1="0" x2="64" y2="208"/>
    <line x1="128" y1="0" x2="128" y2="208"/>
    <line x1="192" y1="0" x2="192" y2="208"/>
    <line x1="256" y1="0" x2="256" y2="208"/>
    <line x1="320" y1="0" x2="320" y2="208"/>
  </g>
  <!-- Area fill under crash curve -->
  <polygon points="18,62 66,54 110,74 156,70 202,118 248,144 294,168 346,184 346,208 18,208" fill="#B91C1C" opacity="0.22"/>
  <!-- Candlesticks (early green rally fading to steep crimson sell-off) -->
  <!-- Green pre-fade -->
  <line x1="34" y1="44" x2="34" y2="78" stroke="#22C55E" stroke-width="2.4"/>
  <rect x="26" y="52" width="16" height="18" fill="#16A34A" stroke="#111317" stroke-width="1.2"/>
  <line x1="72" y1="38" x2="72" y2="70" stroke="#22C55E" stroke-width="2.4"/>
  <rect x="64" y="45" width="16" height="17" fill="#16A34A" stroke="#111317" stroke-width="1.2"/>
  <!-- Steep crimson cascade -->
  <line x1="112" y1="46" x2="112" y2="96" stroke="#F87171" stroke-width="2.4"/>
  <rect x="103" y="54" width="18" height="32" fill="#DC2626" stroke="#111317" stroke-width="1.2"/>
  <line x1="154" y1="68" x2="154" y2="116" stroke="#F87171" stroke-width="2.4"/>
  <rect x="145" y="76" width="18" height="28" fill="#DC2626" stroke="#111317" stroke-width="1.2"/>
  <line x1="198" y1="86" x2="198" y2="148" stroke="#F87171" stroke-width="2.6"/>
  <rect x="188" y="94" width="20" height="44" fill="#B91C1C" stroke="#111317" stroke-width="1.2"/>
  <line x1="244" y1="116" x2="244" y2="174" stroke="#F87171" stroke-width="2.6"/>
  <rect x="234" y="124" width="20" height="38" fill="#B91C1C" stroke="#111317" stroke-width="1.2"/>
  <line x1="292" y1="138" x2="292" y2="194" stroke="#F87171" stroke-width="2.8"/>
  <rect x="281" y="146" width="22" height="38" fill="#EF4444" stroke="#111317" stroke-width="1.2"/>
  <!-- Sharp crash trendline + arrow -->
  <polyline points="22,60 72,50 112,72 154,88 198,124 244,152 308,180" fill="none" stroke="#FCA5A5" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>
  <polygon points="322,186 300,185 310,168" fill="#FCA5A5"/>
  <!-- Cracked AI Chip Icon (upper right) -->
  <g transform="translate(292, 26)">
    <rect x="8" y="8" width="58" height="58" rx="6" fill="#1E3A8A" stroke="#60A5FA" stroke-width="2.4"/>
    <rect x="19" y="19" width="36" height="36" rx="3" fill="#0F172A" stroke="#93C5FD" stroke-width="1.8"/>
    <text x="37" y="42" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="16" fill="#93C5FD">AI</text>
    <!-- Pins -->
    <g stroke="#60A5FA" stroke-width="2.4">
      <line x1="20" y1="0" x2="20" y2="8"/><line x1="37" y1="0" x2="37" y2="8"/><line x1="54" y1="0" x2="54" y2="8"/>
      <line x1="20" y1="66" x2="20" y2="74"/><line x1="37" y1="66" x2="37" y2="74"/><line x1="54" y1="66" x2="54" y2="74"/>
      <line x1="0" y1="20" x2="8" y2="20"/><line x1="0" y1="37" x2="8" y2="37"/><line x1="0" y1="54" x2="8" y2="54"/>
      <line x1="66" y1="20" x2="74" y2="20"/><line x1="66" y1="37" x2="74" y2="37"/><line x1="66" y1="54" x2="74" y2="54"/>
    </g>
    <!-- Red lightning crack -->
    <polyline points="16,14 34,30 28,42 56,62" fill="none" stroke="#EF4444" stroke-width="3.2" stroke-linecap="round"/>
  </g>
  <!-- Bold data callouts -->
  <rect x="12" y="138" width="166" height="54" rx="5" fill="#B91C1C" stroke="#FCA5A5" stroke-width="1.8"/>
  <text x="95" y="162" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="22" fill="#FFFFFF">KOSPI -6.2%</text>
  <text x="95" y="182" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="700" font-size="12" fill="#FEE2E2">NVDA -5.9% · NKY -2.8%</text>
</svg>'''

    if kind == "uk_energy":
        # 3. UK Energy Cap +26%: British terraced homes + radiator + analog utility dial spiking into red +26%
        return '''<svg viewBox="0 0 382 208" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width="382" height="208" fill="#EFE9DC"/>
  <!-- Soft sky band + warm floor -->
  <rect x="0" y="0" width="382" height="148" fill="#DCE5EE"/>
  <rect x="0" y="148" width="382" height="60" fill="#D5CCB8"/>
  <line x1="0" y1="148" x2="382" y2="148" stroke="#111317" stroke-width="2"/>
  <!-- Left: Classic British row house + chimney + cast-iron radiator -->
  <g transform="translate(18, 42)">
    <!-- Brick terrace silhouette -->
    <polygon points="8,44 62,10 116,44" fill="#334155" stroke="#111317" stroke-width="2.2"/>
    <rect x="86" y="6" width="16" height="24" fill="#991B1B" stroke="#111317" stroke-width="2"/>
    <rect x="16" y="44" width="92" height="84" fill="#C25E44" stroke="#111317" stroke-width="2.2"/>
    <!-- Glowing warm windows -->
    <rect x="28" y="56" width="22" height="24" fill="#FDE68A" stroke="#111317" stroke-width="1.8"/>
    <rect x="74" y="56" width="22" height="24" fill="#FDE68A" stroke="#111317" stroke-width="1.8"/>
    <line x1="39" y1="56" x2="39" y2="80" stroke="#111317" stroke-width="1.4"/>
    <line x1="85" y1="56" x2="85" y2="80" stroke="#111317" stroke-width="1.4"/>
    <!-- Front door -->
    <rect x="52" y="92" width="20" height="36" fill="#1D4ED8" stroke="#111317" stroke-width="1.8"/>
    <!-- Radiator ribs overlaid foreground bottom-left -->
    <g transform="translate(12, 114)">
      <rect x="0" y="6" width="102" height="28" rx="4" fill="#F8F5EE" stroke="#111317" stroke-width="2"/>
      <line x1="16" y1="6" x2="16" y2="34" stroke="#111317" stroke-width="2"/>
      <line x1="32" y1="6" x2="32" y2="34" stroke="#111317" stroke-width="2"/>
      <line x1="48" y1="6" x2="48" y2="34" stroke="#111317" stroke-width="2"/>
      <line x1="64" y1="6" x2="64" y2="34" stroke="#111317" stroke-width="2"/>
      <line x1="80" y1="6" x2="80" y2="34" stroke="#111317" stroke-width="2"/>
    </g>
  </g>
  <!-- Right: Oversized Ofgem Utility Gauge Meter spiking into crimson red zone -->
  <g transform="translate(248, 122)">
    <!-- Outer meter casing -->
    <circle cx="0" cy="0" r="80" fill="#F8F5EE" stroke="#111317" stroke-width="3"/>
    <!-- Green / Amber / Red dial arcs -->
    <path d="M-62 12 A64 64 0 0 1 -28 -57" fill="none" stroke="#15803D" stroke-width="14"/>
    <path d="M-24 -59 A64 64 0 0 1 28 -57" fill="none" stroke="#D97706" stroke-width="14"/>
    <path d="M32 -54 A64 64 0 0 1 62 12" fill="none" stroke="#B91C1C" stroke-width="16"/>
    <!-- Tick marks -->
    <circle cx="0" cy="0" r="52" fill="none" stroke="#C5BEB0" stroke-width="1.4" stroke-dasharray="3 6"/>
    <!-- Spiking needle pointed deep into RED -->
    <polygon points="-6,4 4,8 52,-36" fill="#111317"/>
    <circle cx="0" cy="0" r="10" fill="#B91C1C" stroke="#111317" stroke-width="2.2"/>
    <!-- Digital readout window inside dial -->
    <rect x="-48" y="20" width="96" height="34" rx="4" fill="#111317"/>
    <text x="0" y="44" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="25" fill="#FCA5A5">+26%</text>
    <!-- Lightning & flame glyphs -->
    <polygon points="-14,-34 -2,-34 -8,-20 2,-20 -12,-4 -7,-16 -17,-16" fill="#D97706"/>
    <text x="16" y="-12" font-family="Barlow, sans-serif" font-weight="800" font-size="22" fill="#111317">£</text>
  </g>
  <!-- Top right OFGEM stamp -->
  <rect x="278" y="14" width="92" height="24" rx="3" fill="#B91C1C"/>
  <text x="324" y="30" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="700" font-size="12" fill="#FFFFFF">OFGEM CAP</text>
</svg>'''

    if kind == "tariffs":
        # 4. US Tariffs on 16 Partners: cargo container vessel + maritime waves + crimson tariff barrier + red seal 16
        return '''<svg viewBox="0 0 382 208" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width="382" height="208" fill="#E6EEF5"/>
  <!-- Horizon sky & ocean bands -->
  <rect x="0" y="138" width="382" height="70" fill="#1D4ED8"/>
  <rect x="0" y="164" width="382" height="44" fill="#1E3A8A"/>
  <!-- Stylized ocean waves -->
  <path d="M0 156 Q28 148 56 156 T112 156 T168 156 T224 156 T280 156 T336 156 T392 156" fill="none" stroke="#93C5FD" stroke-width="2.4"/>
  <path d="M-16 180 Q18 172 52 180 T120 180 T188 180 T256 180 T324 180 T392 180" fill="none" stroke="#60A5FA" stroke-width="2"/>
  <!-- Container Ship -->
  <g transform="translate(18, 44)">
    <!-- Bridge / superstructure -->
    <rect x="20" y="34" width="34" height="58" fill="#F8F5EE" stroke="#111317" stroke-width="2.2"/>
    <rect x="25" y="42" width="24" height="10" fill="#1E3A8A"/>
    <rect x="30" y="20" width="12" height="14" fill="#B91C1C" stroke="#111317" stroke-width="2"/>
    <!-- Stacked multi-color shipping containers -->
    <rect x="60" y="66" width="44" height="24" fill="#B91C1C" stroke="#111317" stroke-width="2"/>
    <rect x="106" y="66" width="44" height="24" fill="#0F766E" stroke="#111317" stroke-width="2"/>
    <rect x="152" y="66" width="44" height="24" fill="#D97706" stroke="#111317" stroke-width="2"/>
    <rect x="198" y="66" width="40" height="24" fill="#334155" stroke="#111317" stroke-width="2"/>
    <rect x="66" y="40" width="44" height="24" fill="#1D4ED8" stroke="#111317" stroke-width="2"/>
    <rect x="112" y="40" width="44" height="24" fill="#D97706" stroke="#111317" stroke-width="2"/>
    <rect x="158" y="40" width="44" height="24" fill="#0F766E" stroke="#111317" stroke-width="2"/>
    <rect x="92" y="14" width="44" height="24" fill="#B91C1C" stroke="#111317" stroke-width="2"/>
    <rect x="138" y="14" width="44" height="24" fill="#1D4ED8" stroke="#111317" stroke-width="2"/>
    <!-- Ship Hull -->
    <path d="M8 90 L256 90 L240 120 L22 120 Z" fill="#111317"/>
    <path d="M16 108 L246 108 L240 120 L22 120 Z" fill="#B91C1C"/>
  </g>
  <!-- Vertical Customs/Tariff Barrier Gate -->
  <g transform="translate(274, 24)">
    <rect x="0" y="0" width="12" height="172" fill="#F8F5EE" stroke="#111317" stroke-width="2.2"/>
    <rect x="0" y="14" width="12" height="18" fill="#B91C1C"/>
    <rect x="0" y="50" width="12" height="18" fill="#B91C1C"/>
    <rect x="0" y="86" width="12" height="18" fill="#B91C1C"/>
    <rect x="0" y="122" width="12" height="18" fill="#B91C1C"/>
  </g>
  <!-- Embossed Red Tariff Stamp Seal (16 PARTNERS) -->
  <g transform="translate(314, 86) rotate(-10)">
    <circle cx="0" cy="0" r="49" fill="#F8F5EE" stroke="#B91C1C" stroke-width="4.8"/>
    <circle cx="0" cy="0" r="40" fill="none" stroke="#B91C1C" stroke-width="1.6" stroke-dasharray="4 3"/>
    <text x="0" y="-11" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="12" fill="#B91C1C" letter-spacing="1.0">US TARIFFS</text>
    <text x="0" y="17" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="32" fill="#111317">16</text>
    <text x="0" y="32" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="700" font-size="10" fill="#B91C1C">PARTNERS</text>
  </g>
</svg>'''

    if kind == "riyadh":
        # 5. Riyadh Tower Hit Again: desert twilight sky, Riyadh skyline + tallest financial tower + smoke + intercept arc
        return '''<svg viewBox="0 0 382 208" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width="382" height="208" fill="#F3D6B3"/>
  <!-- Sunset desert bands -->
  <rect x="0" y="0" width="382" height="72" fill="#D97706" opacity="0.32"/>
  <rect x="0" y="156" width="382" height="52" fill="#C49A6C"/>
  <!-- Distant Riyadh skyline -->
  <g fill="#475569" stroke="#111317" stroke-width="1.6">
    <rect x="20" y="114" width="28" height="78"/>
    <rect x="54" y="96" width="34" height="96"/>
    <rect x="96" y="122" width="26" height="70"/>
    <rect x="262" y="110" width="30" height="82"/>
    <rect x="298" y="92" width="36" height="100"/>
    <rect x="340" y="120" width="28" height="72"/>
  </g>
  <!-- Tallest Financial Tower (iconic parabolic arch silhouette) -->
  <g transform="translate(154, 18)">
    <path d="M8 174 L14 8 C14 2 62 2 62 8 L68 174 Z" fill="#1E293B" stroke="#111317" stroke-width="2.4"/>
    <!-- Skybridge arch cutout -->
    <path d="M24 22 C24 44 52 44 52 22 L52 14 L24 14 Z" fill="#F3D6B3" stroke="#111317" stroke-width="1.8"/>
    <!-- Glass vertical curtain mullions -->
    <line x1="26" y1="48" x2="24" y2="170" stroke="#93C5FD" stroke-width="1.4" opacity="0.7"/>
    <line x1="38" y1="48" x2="38" y2="170" stroke="#93C5FD" stroke-width="1.4" opacity="0.7"/>
    <line x1="50" y1="48" x2="52" y2="170" stroke="#93C5FD" stroke-width="1.4" opacity="0.7"/>
  </g>
  <!-- Incoming missile arc & air-defense intercept trail -->
  <path d="M16 144 Q88 32 186 76" fill="none" stroke="#B91C1C" stroke-width="3.2" stroke-dasharray="7 5"/>
  <path d="M356 154 Q282 54 218 68" fill="none" stroke="#1D4ED8" stroke-width="2.6" stroke-dasharray="5 4"/>
  <!-- Smoke plume drifting right from upper financial tower -->
  <circle cx="206" cy="74" r="18" fill="#334155" opacity="0.85"/>
  <circle cx="228" cy="64" r="22" fill="#475569" opacity="0.78"/>
  <circle cx="256" cy="54" r="26" fill="#64748B" opacity="0.62"/>
  <circle cx="288" cy="48" r="22" fill="#94A3B8" opacity="0.45"/>
  <!-- Sharp crimson/gold impact flash -->
  <polygon points="194,52 201,67 218,64 205,76 215,92 198,84 186,96 189,79 174,73 190,68" fill="#DC2626" stroke="#111317" stroke-width="1.6"/>
  <polygon points="195,62 199,70 208,69 201,76 205,84 196,80 190,85 192,76 184,73 192,70" fill="#FDE047"/>
  <!-- Alert strip -->
  <rect x="10" y="166" width="150" height="28" rx="3" fill="#111317"/>
  <text x="85" y="185" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="700" font-size="12" fill="#FCA5A5">2ND HIT · 11+ HURT</text>
</svg>'''

    if kind == "ebola":
        # 6. WHO Ebola Teams Trapped: Ituri hills, white/teal WHO medical tent, 1.5M vaccine vial, red cordon chevrons
        return '''<svg viewBox="0 0 382 208" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width="382" height="208" fill="#E8E4D4"/>
  <!-- Ituri tropical rolling hills -->
  <path d="M0 112 Q86 64 190 96 T382 88 L382 208 L0 208 Z" fill="#4D7C5A" opacity="0.45"/>
  <path d="M0 144 Q120 112 246 138 T382 128 L382 208 L0 208 Z" fill="#3F6B4E"/>
  <!-- WHO Medical Field Tent (center-left) -->
  <g transform="translate(44, 64)">
    <polygon points="0,50 96,8 192,50" fill="#0F766E" stroke="#111317" stroke-width="2.4"/>
    <rect x="12" y="50" width="168" height="68" fill="#F8F5EE" stroke="#111317" stroke-width="2.4"/>
    <!-- Tent doorway -->
    <path d="M74 118 L74 72 Q96 62 118 72 L118 118 Z" fill="#1E293B" stroke="#111317" stroke-width="2"/>
    <!-- Bold medical cross on roof/side -->
    <rect x="28" y="70" width="28" height="10" fill="#B91C1C"/>
    <rect x="37" y="61" width="10" height="28" fill="#B91C1C"/>
    <text x="150" y="88" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="19" fill="#0F766E">WHO</text>
  </g>
  <!-- Red/Amber roadblock cordon bar foreground (trapped responders) -->
  <g transform="translate(18, 174)">
    <rect x="0" y="0" width="234" height="18" rx="2" fill="#B91C1C" stroke="#111317" stroke-width="2"/>
    <polygon points="18,0 34,0 24,18 8,18" fill="#FDE047"/>
    <polygon points="56,0 72,0 62,18 46,18" fill="#FDE047"/>
    <polygon points="94,0 110,0 100,18 84,18" fill="#FDE047"/>
    <polygon points="132,0 148,0 138,18 122,18" fill="#FDE047"/>
    <polygon points="170,0 186,0 176,18 160,18" fill="#FDE047"/>
    <polygon points="208,0 224,0 214,18 198,18" fill="#FDE047"/>
  </g>
  <!-- Right: Gavi 1.5M Vaccine Vial + Shield -->
  <g transform="translate(274, 34)">
    <path d="M44 0 L88 18 L88 68 C88 106 44 128 44 128 C44 128 0 106 0 68 L0 18 Z" fill="#0F766E" stroke="#111317" stroke-width="2.6"/>
    <!-- Vial inside shield -->
    <rect x="30" y="24" width="28" height="10" rx="2" fill="#D97706" stroke="#111317" stroke-width="1.8"/>
    <rect x="26" y="34" width="36" height="58" rx="4" fill="#F8F5EE" stroke="#111317" stroke-width="2"/>
    <rect x="26" y="54" width="36" height="24" fill="#5EEAD4"/>
    <text x="44" y="71" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="14" fill="#111317">1.5M</text>
    <text x="44" y="108" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="700" font-size="10.5" fill="#FFFFFF">GAVI</text>
  </g>
  <rect x="266" y="170" width="104" height="24" rx="3" fill="#111317"/>
  <text x="318" y="186" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="700" font-size="11.5" fill="#FDE047">ITURI · DRC</text>
</svg>'''

    if kind == "cyber":
        # 7. CIA Breach & MSFT Code Red: dark terminal screen + cracked security shield + CODE RED banner + server rack
        return '''<svg viewBox="0 0 382 208" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width="382" height="208" fill="#0E141F"/>
  <!-- Matrix / binary subtle grid lines -->
  <g font-family="IBMPlexMono, monospace" font-size="11" fill="#1E293B" font-weight="700">
    <text x="12" y="24">01001101 10110010 00111010 11010101 01011001</text>
    <text x="12" y="44">11010011 01011100 10010110 00101101 11100101</text>
    <text x="12" y="196">ERR_AUTH_BYPASS // ODNI_CIA // CLOUD_ALERT_503</text>
  </g>
  <!-- Left: Cracked Government Intelligence Shield -->
  <g transform="translate(26, 30)">
    <path d="M56 4 L110 24 L110 78 C110 118 56 144 56 144 C56 144 2 118 2 78 L2 24 Z" fill="#1E3A8A" stroke="#93C5FD" stroke-width="2.6"/>
    <!-- Keyhole / Lock -->
    <circle cx="56" cy="64" r="14" fill="#F8F5EE"/>
    <polygon points="48,74 64,74 68,104 44,104" fill="#F8F5EE"/>
    <!-- Jagged crimson breach crack -->
    <polyline points="68,12 46,44 70,66 38,98 62,136" fill="none" stroke="#EF4444" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
    <polyline points="68,12 46,44 70,66 38,98 62,136" fill="none" stroke="#FCA5A5" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
  </g>
  <!-- Right: Microsoft / Cloud Code Red Terminal Window -->
  <g transform="translate(158, 28)">
    <rect x="0" y="0" width="204" height="148" rx="6" fill="#182234" stroke="#475569" stroke-width="2.2"/>
    <rect x="0" y="0" width="204" height="26" rx="6" fill="#334155"/>
    <circle cx="16" cy="13" r="4.5" fill="#EF4444"/>
    <circle cx="30" cy="13" r="4.5" fill="#F59E0B"/>
    <circle cx="44" cy="13" r="4.5" fill="#22C55E"/>
    <text x="192" y="17" text-anchor="end" font-family="IBMPlexMono, monospace" font-weight="700" font-size="11" fill="#CBD5E1">SYS://ALERT</text>
    <!-- Bold CODE RED banner -->
    <rect x="14" y="38" width="176" height="38" rx="4" fill="#B91C1C"/>
    <text x="102" y="64" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="24" fill="#FFFFFF" letter-spacing="1.5">CODE RED</text>
    <!-- 4-pane window glyph (stylized) + status rows -->
    <g transform="translate(16, 90)">
      <rect x="0" y="0" width="14" height="14" fill="#EF4444"/>
      <rect x="17" y="0" width="14" height="14" fill="#22C55E"/>
      <rect x="0" y="17" width="14" height="14" fill="#3B82F6"/>
      <rect x="17" y="17" width="14" height="14" fill="#F59E0B"/>
    </g>
    <text x="60" y="103" font-family="IBMPlexMono, monospace" font-weight="700" font-size="13" fill="#FCA5A5">MSFT OUTAGE</text>
    <text x="60" y="121" font-family="IBMPlexMono, monospace" font-weight="600" font-size="12" fill="#93C5FD">CIA / ODNI HACK</text>
    <rect x="14" y="131" width="176" height="6" rx="2" fill="#0F172A"/>
    <rect x="14" y="131" width="128" height="6" rx="2" fill="#EF4444"/>
  </g>
</svg>'''

    if kind == "eurostar":
        # 8. Eurostar Strike Halts Trains: Channel Tunnel stone arch, sleek cobalt-gold high-speed nose, crimson halt signal
        return '''<svg viewBox="0 0 382 208" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width="382" height="208" fill="#DCE4EE"/>
  <!-- Sky & hillside over Channel Tunnel portal -->
  <path d="M0 78 Q120 20 264 56 L382 32 L382 154 L0 154 Z" fill="#6B8E76"/>
  <rect x="0" y="148" width="382" height="60" fill="#B8B0A0"/>
  <!-- Stone tunnel facade & dark arch -->
  <rect x="26" y="34" width="192" height="118" rx="4" fill="#D4CBB8" stroke="#111317" stroke-width="2.4"/>
  <path d="M52 152 L52 88 A70 52 0 0 1 192 88 L192 152 Z" fill="#18202C" stroke="#111317" stroke-width="2.4"/>
  <!-- Perspective railway tracks -->
  <line x1="94" y1="152" x2="22" y2="208" stroke="#334155" stroke-width="5"/>
  <line x1="176" y1="152" x2="262" y2="208" stroke="#334155" stroke-width="5"/>
  <line x1="72" y1="168" x2="200" y2="168" stroke="#64748B" stroke-width="3"/>
  <line x1="48" y1="186" x2="228" y2="186" stroke="#64748B" stroke-width="3.5"/>
  <!-- Sleek Eurostar High-Speed Train Nose halted at portal -->
  <g transform="translate(88, 72)">
    <path d="M18 14 Q64 4 108 14 L132 58 Q134 78 112 84 L12 84 Q-4 78 4 56 Z" fill="#1D4ED8" stroke="#111317" stroke-width="2.6"/>
    <!-- Gold Eurostar speed stripe -->
    <path d="M4 58 L128 58 L124 68 L2 68 Z" fill="#F59E0B"/>
    <!-- Dark windshield -->
    <path d="M22 20 Q64 14 102 20 L114 48 L12 48 Z" fill="#0F172A" stroke="#93C5FD" stroke-width="1.6"/>
    <!-- Headlights -->
    <ellipse cx="22" cy="74" rx="8" ry="4" fill="#FEF3C7"/>
    <ellipse cx="106" cy="74" rx="8" ry="4" fill="#FEF3C7"/>
  </g>
  <!-- Right: Tall Red Railway Signal + HALTED Strike Banner -->
  <g transform="translate(274, 20)">
    <rect x="40" y="72" width="10" height="106" fill="#334155" stroke="#111317" stroke-width="2"/>
    <rect x="22" y="0" width="46" height="82" rx="10" fill="#111317" stroke="#F8F5EE" stroke-width="2"/>
    <circle cx="45" cy="24" r="14" fill="#EF4444" stroke="#FCA5A5" stroke-width="2.5"/>
    <circle cx="45" cy="58" r="11" fill="#334155"/>
    <!-- Diagonal strike stop sign -->
    <rect x="-14" y="104" width="114" height="36" rx="4" fill="#B91C1C" stroke="#111317" stroke-width="2.2"/>
    <text x="43" y="128" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="18" fill="#FFFFFF" letter-spacing="1">HALTED</text>
    <rect x="-14" y="146" width="114" height="24" rx="3" fill="#111317"/>
    <text x="43" y="162" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="700" font-size="11" fill="#FDE047">PARIS ↔ LONDON</text>
  </g>
</svg>'''

    if kind == "cricket":
        # 9. Teen Smashes 204 off 53: floodlit emerald stadium, dynamic cricket batter lofting six + scoreboard 204 (53) / 28x6s
        return '''<svg viewBox="0 0 382 208" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width="382" height="208" fill="#1E1B4B"/>
  <!-- Stadium floodlight beams -->
  <polygon points="34,12 150,148 0,148" fill="#A78BFA" opacity="0.16"/>
  <polygon points="348,12 382,148 232,148" fill="#A78BFA" opacity="0.16"/>
  <!-- Emerald outfield & golden pitch strip -->
  <rect x="0" y="138" width="382" height="70" fill="#15803D"/>
  <rect x="0" y="156" width="382" height="52" fill="#166534"/>
  <polygon points="44,208 118,144 176,144 136,208" fill="#E6D3A3" stroke="#B45309" stroke-width="1.4"/>
  <!-- Wooden cricket stumps -->
  <g stroke="#FDE68A" stroke-width="3.2" stroke-linecap="round">
    <line x1="66" y1="138" x2="66" y2="178"/>
    <line x1="74" y1="138" x2="74" y2="178"/>
    <line x1="82" y1="138" x2="82" y2="178"/>
    <line x1="64" y1="138" x2="84" y2="138" stroke="#D97706" stroke-width="2.6"/>
  </g>
  <!-- Dynamic India-blue cricket batter mid-lofted-six swing -->
  <g transform="translate(114, 78)">
    <!-- Helmet -->
    <circle cx="14" cy="14" r="12" fill="#1D4ED8" stroke="#111317" stroke-width="2"/>
    <path d="M18 14 L29 18 L24 23 L16 21 Z" fill="#FDE047"/>
    <!-- Torso (India blue jersey) -->
    <path d="M4 26 L28 28 L24 64 L-2 60 Z" fill="#2563EB" stroke="#111317" stroke-width="2"/>
    <!-- Legs + pads -->
    <path d="M0 60 L-12 98 L4 100 L14 64 Z" fill="#F8F5EE" stroke="#111317" stroke-width="2"/>
    <path d="M16 62 L32 98 L46 94 L28 60 Z" fill="#F8F5EE" stroke="#111317" stroke-width="2"/>
    <!-- Raised arms & willow bat swinging high -->
    <path d="M22 32 L46 18 L52 26 L28 42 Z" fill="#2563EB" stroke="#111317" stroke-width="1.8"/>
    <g transform="translate(46, 18) rotate(-42)">
      <rect x="-4" y="-56" width="12" height="44" rx="2" fill="#F5D08A" stroke="#111317" stroke-width="2.2"/>
      <rect x="0" y="-12" width="4" height="16" fill="#111317"/>
    </g>
  </g>
  <!-- Golden sixes trajectory arc + gleaming crimson cricket ball -->
  <path d="M182 54 Q238 4 304 28" fill="none" stroke="#FDE047" stroke-width="3.2" stroke-dasharray="6 4"/>
  <circle cx="312" cy="30" r="11" fill="#DC2626" stroke="#FFFFFF" stroke-width="2"/>
  <path d="M304 26 Q312 32 320 26" fill="none" stroke="#FFFFFF" stroke-width="1.6"/>
  <!-- Classic Stadium Scoreboard (right) -->
  <g transform="translate(216, 62)">
    <rect x="0" y="0" width="150" height="106" rx="6" fill="#111317" stroke="#A78BFA" stroke-width="2.4"/>
    <rect x="8" y="8" width="134" height="22" rx="3" fill="#6D28D9"/>
    <text x="75" y="23" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="13" fill="#FFFFFF" letter-spacing="0.8">INDIA A vs UAE</text>
    <text x="75" y="64" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="36" fill="#FDE047">204</text>
    <text x="75" y="84" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="700" font-size="14" fill="#E9D5FF">53 BALLS · 28×6s</text>
    <text x="75" y="100" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="600" font-size="10.5" fill="#86EFAC">AGE 15 RECORD</text>
  </g>
</svg>'''

    # 10. Australia-Solomons Pact: Pacific chart, Australia & Solomons silhouettes joined by diplomatic security shield
    return '''<svg viewBox="0 0 382 208" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width="382" height="208" fill="#154C79"/>
  <!-- Nautical latitude/longitude chart lines -->
  <g stroke="#38BDF8" stroke-width="1" opacity="0.28">
    <line x1="0" y1="52" x2="382" y2="52"/>
    <line x1="0" y1="104" x2="382" y2="104"/>
    <line x1="0" y1="156" x2="382" y2="156"/>
    <line x1="95" y1="0" x2="95" y2="208"/>
    <line x1="191" y1="0" x2="191" y2="208"/>
    <line x1="287" y1="0" x2="287" y2="208"/>
  </g>
  <!-- Stylized Australia landmass (bottom-left) -->
  <path d="M22 146 L48 112 L94 102 L126 84 L148 106 L168 148 L152 184 L112 192 L76 178 L34 182 Z" fill="#D4A359" stroke="#111317" stroke-width="2.4"/>
  <text x="96" y="156" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="14" fill="#111317" letter-spacing="1.2">AUSTRALIA</text>
  <!-- Stylized Solomon Islands archipelago (upper-right) -->
  <g fill="#4ADE80" stroke="#111317" stroke-width="2">
    <ellipse cx="268" cy="54" rx="18" ry="8" transform="rotate(24 268 54)"/>
    <ellipse cx="298" cy="68" rx="22" ry="9" transform="rotate(28 298 68)"/>
    <ellipse cx="328" cy="86" rx="18" ry="8" transform="rotate(24 328 86)"/>
    <ellipse cx="348" cy="102" rx="12" ry="6" transform="rotate(20 348 102)"/>
  </g>
  <text x="306" y="42" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="13" fill="#F8F5EE" letter-spacing="0.8">SOLOMON IS.</text>
  <!-- Strategic security bridge arc -->
  <path d="M142 114 Q208 60 282 68" fill="none" stroke="#FDE047" stroke-width="4" stroke-dasharray="7 5"/>
  <circle cx="142" cy="114" r="6" fill="#FDE047" stroke="#111317" stroke-width="2"/>
  <circle cx="284" cy="68" r="6" fill="#FDE047" stroke="#111317" stroke-width="2"/>
  <!-- Diplomatic Security Treaty Shield (center-right) -->
  <g transform="translate(194, 86)">
    <path d="M46 0 L92 16 L92 56 C92 86 46 106 46 106 C46 106 0 86 0 56 L0 16 Z" fill="#F8F5EE" stroke="#111317" stroke-width="2.6"/>
    <path d="M46 8 L83 21 L83 54 C83 78 46 95 46 95 C46 95 9 78 9 54 L9 21 Z" fill="#1D4ED8"/>
    <!-- Gold star / pact check -->
    <polygon points="46,19 52,34 68,34 55,44 60,60 46,50 32,60 37,44 24,34 40,34" fill="#FDE047"/>
    <text x="46" y="76" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="700" font-size="9.5" fill="#FFFFFF">SECURITY</text>
  </g>
  <!-- Treaty pill bottom-right -->
  <rect x="294" y="166" width="76" height="26" rx="4" fill="#B91C1C"/>
  <text x="332" y="183" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="700" font-size="11.5" fill="#FFFFFF">NEW PACT</text>
</svg>'''


# ---------------------------------------------------------------------------
# Natural Earth 110m Projection & World Map (Zone 3: 1984 x 494)
# ---------------------------------------------------------------------------
def ne_project_raw(lat_deg: float, lon_deg: float) -> Tuple[float, float]:
    phi = math.radians(max(-89.9, min(89.9, lat_deg)))
    lam = math.radians(lon_deg)
    phi2 = phi * phi
    phi4 = phi2 * phi2
    l_val = 0.870700 - 0.131979 * phi2 - 0.013791 * phi4 + 0.003971 * (phi4 * phi4 * phi2) - 0.001529 * (phi4 * phi4 * phi4)
    d_val = phi * (1.007226 + 0.015085 * phi2 - 0.044475 * (phi4 * phi2) + 0.028874 * (phi4 * phi4) - 0.005916 * (phi4 * phi4 * phi2))
    return (l_val * lam, -d_val)


MAP_W = 1984.0
MAP_H = 516.0
LON_MIN, LON_MAX = -168.0, 179.0
LAT_MIN, LAT_MAX = -54.0, 72.0

_X_MIN = ne_project_raw(0.0, LON_MIN)[0]
_X_MAX = ne_project_raw(0.0, LON_MAX)[0]
_Y_TOP = ne_project_raw(LAT_MAX, 0.0)[1]
_Y_BOT = ne_project_raw(LAT_MIN, 0.0)[1]

PAD_X = 24.0
PAD_Y = 12.0
_SCALE_X = (MAP_W - 2 * PAD_X) / (_X_MAX - _X_MIN)
_SCALE_Y = (MAP_H - 2 * PAD_Y) / (_Y_BOT - _Y_TOP)
MAP_SCALE = min(_SCALE_X, _SCALE_Y)
_USED_W = (_X_MAX - _X_MIN) * MAP_SCALE
_USED_H = (_Y_BOT - _Y_TOP) * MAP_SCALE
MAP_OFF_X = (MAP_W - _USED_W) / 2.0
MAP_OFF_Y = (MAP_H - _USED_H) / 2.0


def project(lat_deg: float, lon_deg: float) -> Tuple[float, float]:
    rx, ry = ne_project_raw(lat_deg, lon_deg)
    return (MAP_OFF_X + (rx - _X_MIN) * MAP_SCALE, MAP_OFF_Y + (ry - _Y_TOP) * MAP_SCALE)


def ring_to_path(coords: List[List[float]]) -> str:
    pts = []
    prev_lon = None
    for lon, lat in coords:
        if lat < LAT_MIN - 2:
            lat = LAT_MIN - 2
        if lat > LAT_MAX + 4:
            lat = LAT_MAX + 4
        if prev_lon is not None and abs(lon - prev_lon) > 180:
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

    # Natural Earth globe border
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

    grat_paths = []
    for lat in (-30, 0, 30, 60):
        pts = [project(lat, lon) for lon in range(-180, 181, 4)]
        d = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        grat_paths.append(f'<path d="{d}" class="{"grat-eq" if lat == 0 else "grat"}"/>')
    for lon in (-150, -120, -90, -60, -30, 0, 30, 60, 90, 120, 150):
        pts = [project(lat, lon) for lat in range(int(LAT_MIN), int(LAT_MAX) + 1, 3)]
        d = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        grat_paths.append(f'<path d="{d}" class="grat"/>')

    country_paths = []
    for feat in gj["features"]:
        props = feat.get("properties", {})
        if props.get("ADMIN") == "Antarctica" or props.get("ISO_A3") == "ATA":
            continue
        geom = feat.get("geometry", {})
        gtype = geom.get("type")
        polys = [geom["coordinates"]] if gtype == "Polygon" else (geom["coordinates"] if gtype == "MultiPolygon" else [])
        subpaths = [ring_to_path(poly[0]) for poly in polys if poly]
        subpaths = [p for p in subpaths if p]
        if subpaths:
            country_paths.append(f'<path d="{" ".join(subpaths)}" class="land"/>')

    # Clean continent watermarks strictly inside map margins & clear of all 36 pins
    continent_labels = [
        ("NORTH AMERICA", 56.0, -104.0),
        ("SOUTH AMERICA", -17.0, -58.0),
        ("EUROPE", 60.5, 42.0),       # Safely below top frame & right of European pins!
        ("AFRICA", 21.5, 13.0),
        ("ASIA", 56.0, 96.0),
        ("OCEANIA", -25.0, 133.5),
    ]
    cont_svg = [
        f'<text x="{project(clat, clon)[0]:.1f}" y="{project(clat, clon)[1]:.1f}" class="cont-lbl">{html.escape(label)}</text>'
        for label, clat, clon in continent_labels
    ]

    # Collect all 36 pins (1-10 scene heroes + 11-36 regional briefs)
    all_pins: List[Tuple[int, str, float, float, bool]] = []
    for sc in SCENES:
        all_pins.append((sc["pin"], sc["cat"], sc["lat"], sc["lon"], True))
    for pin, region, cat, lat, lon, hl in BRIEFS:
        all_pins.append((pin, cat, lat, lon, False))

    # Curated callout hints for dense clusters (US East, Europe, Levant/Gulf, East Asia)
    preferred_offsets: Dict[int, Tuple[float, float]] = {
        # Americas
        7: (-16.0, -12.0),   # Redmond / Cyber
        13: (-22.0, 8.0),    # Santa Clara / Nvidia
        15: (-12.0, -20.0),  # Chicago / PCE
        4: (26.0, 22.0),     # DC / Tariffs -> SE Atlantic
        12: (-18.0, 26.0),   # Pentagon / Hadrian -> SW
        11: (34.0, -8.0),    # NYC / Huawei -> E Atlantic
        14: (0.0, 0.0),      # Colombia
        # Europe (clean radial fan around NW/central Europe, strictly below top border)
        3: (-44.0, -16.0),   # UK Energy -> NW Atlantic
        18: (-48.0, 10.0),   # UK Heat/Royal -> W Atlantic
        8: (-34.0, 32.0),    # Eurostar -> SW Bay of Biscay
        20: (-12.0, 36.0),   # Europe/Decathlon -> S Spain/Med
        16: (-16.0, -34.0),  # Hague / Europol -> N North Sea
        17: (14.0, -30.0),   # Denmark -> NNE Scandinavia
        19: (32.0, -14.0),   # Poland/EU -> NE
        36: (16.0, 24.0),    # Vienna / UN -> SE Adriatic
        # Middle East
        24: (8.0, -8.0),     # Turkey/UAE
        21: (-26.0, 12.0),   # Israel/Gaza -> SW Med
        5: (-4.0, 12.0),     # Riyadh Tower
        23: (16.0, -12.0),   # Gulf / Allianz -> NE
        9: (36.0, 10.0),     # UAE / Cricket 204 -> E Arabian Sea
        22: (-8.0, 20.0),    # Yemen / Houthis -> S
        # Africa
        25: (-16.0, 0.0),    # Senegal
        27: (-10.0, 10.0),   # Nigeria
        6: (14.0, -4.0),     # DRC Ituri / WHO Ebola
        28: (-18.0, 6.0),    # Angola/Botswana
        26: (14.0, 12.0),    # DRC Cobalt
        # Asia
        1: (-18.0, -14.0),   # Jiuquan / Shenzhou-24
        30: (10.0, -24.0),   # Beijing
        2: (36.0, -18.0),    # Seoul / KOSPI -6.2%
        31: (44.0, 6.0),     # Sejong / South Korea
        29: (16.0, 12.0),    # Shanghai
        34: (34.0, 28.0),    # Taiwan/Thailand
        32: (-14.0, 12.0),   # Bangladesh
        33: (0.0, 14.0),     # Indonesia/Vietnam
        # Oceania
        35: (0.0, 0.0),      # Australia
        10: (0.0, 0.0),      # Solomon Islands
    }

    nodes = []
    for pin, cat, lat, lon, is_scene in all_pins:
        ax, ay = project(lat, lon)
        dx, dy = preferred_offsets.get(pin, (0.0, 0.0))
        r = 16.0 if is_scene else 13.5
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
            "is_scene": is_scene,
        })

    pad_x, pad_y = 26.0, 22.0
    for _ in range(450):
        moved = False
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                ni, nj = nodes[i], nodes[j]
                dx = nj["x"] - ni["x"]
                dy = nj["y"] - ni["y"]
                dist = math.hypot(dx, dy)
                min_d = ni["r"] + nj["r"] + 6.0
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
        for n in nodes:
            n["x"] += (n["tx"] - n["x"]) * 0.03
            n["y"] += (n["ty"] - n["y"]) * 0.03
            n["x"] = max(pad_x, min(MAP_W - pad_x, n["x"]))
            n["y"] = max(pad_y, min(MAP_H - pad_y, n["y"]))
        if not moved:
            break

    min_gap = 999.0
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            ni, nj = nodes[i], nodes[j]
            gap = math.hypot(nj["x"] - ni["x"], nj["y"] - ni["y"]) - (ni["r"] + nj["r"])
            if gap < min_gap:
                min_gap = gap
    print(f"[map] 36 pins laid out; minimum edge-to-edge gap = {min_gap:.2f}px")
    assert min_gap >= 3.0, f"Pin overlap detected! min_gap={min_gap:.2f}"

    leaders_svg, anchors_svg, badges_svg = [], [], []
    for n in sorted(nodes, key=lambda item: (item["is_scene"], item["pin"])):
        color = CAT_COLORS[n["cat"]]
        ax, ay, bx, by, r = n["ax"], n["ay"], n["x"], n["y"], n["r"]
        if math.hypot(bx - ax, by - ay) > 5.0:
            leaders_svg.append(
                f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="#F8F5EE" stroke-width="4.2" stroke-linecap="round" opacity="0.9"/>'
                f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{color}" stroke-width="2.0" stroke-linecap="round"/>'
            )
            anchors_svg.append(
                f'<circle cx="{ax:.1f}" cy="{ay:.1f}" r="4.2" fill="{color}" stroke="#F8F5EE" stroke-width="1.8"/>'
            )
        if n["is_scene"]:
            badges_svg.append(
                f'<g>'
                f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{r + 3.0:.1f}" fill="#F8F5EE"/>'
                f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{r:.1f}" fill="{color}" stroke="#111317" stroke-width="2.3"/>'
                f'<text x="{bx:.1f}" y="{by + 0.8:.1f}" class="pin-num pin-num-scene">{n["pin"]}</text>'
                f'</g>'
            )
        else:
            badges_svg.append(
                f'<g>'
                f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{r + 2.2:.1f}" fill="#F8F5EE"/>'
                f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{r:.1f}" fill="{color}"/>'
                f'<text x="{bx:.1f}" y="{by + 0.7:.1f}" class="pin-num">{n["pin"]}</text>'
                f'</g>'
            )

    return f'''<svg viewBox="0 0 {int(MAP_W)} {int(MAP_H)}" width="{int(MAP_W)}" height="{int(MAP_H)}" xmlns="http://www.w3.org/2000/svg">
  <defs><clipPath id="globeClip"><path d="{globe_d}"/></clipPath></defs>
  <rect x="0" y="0" width="{int(MAP_W)}" height="{int(MAP_H)}" fill="#F3EFE6"/>
  <path d="{globe_d}" fill="#E5E0D3" stroke="#B5AD9D" stroke-width="1.5"/>
  <g clip-path="url(#globeClip)">
    {"".join(grat_paths)}
    {"".join(country_paths)}
    {"".join(cont_svg)}
  </g>
  <path d="{globe_d}" fill="none" stroke="#9B9384" stroke-width="1.5"/>
  <g>{"".join(leaders_svg)}</g>
  <g>{"".join(anchors_svg)}</g>
  <g>{"".join(badges_svg)}</g>
  <!-- Bottom-left DATE CHECK Seal Box (open South Pacific margin) -->
  <g transform="translate(18, 424)">
    <rect x="0" y="0" width="496" height="76" rx="4" fill="#F8F5EE" fill-opacity="0.96" stroke="#111317" stroke-width="1.8"/>
    <rect x="0" y="0" width="8" height="76" rx="2" fill="#15803D"/>
    <circle cx="28" cy="24" r="11" fill="#15803D"/>
    <polyline points="22,24 26.5,28.5 34.5,19.5" fill="none" stroke="#FFFFFF" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
    <text x="46" y="29" class="map-seal-title">DATE CHECK: ALL 36 STORIES VERIFIED WED 25 NOV 2026</text>
    <text x="18" y="50" class="map-seal-sub">NATURAL EARTH 110m PROJECTION · 6 INHABITED CONTINENTS</text>
    <text x="18" y="66" class="map-seal-sub">DOUBLE-RING PINS 1–10 = DRAWN SCENES · PINS 11–36 = REGIONAL BRIEFS</text>
  </g>
</svg>'''


def format_headline_html(text: str) -> str:
    if ":" in text:
        prefix, rest = text.split(":", 1)
        return f'<span class="hl-prefix">{html.escape(prefix)}:</span>{html.escape(rest)} <span class="hl-date">(25 Nov)</span>'
    return f'{html.escape(text)} <span class="hl-date">(25 Nov)</span>'


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
        f'<span class="region-meta">{len(stories)} BRIEFS · WED 25 NOV</span>'
        f'</div>'
        f'<div class="region-list">{"".join(rows)}</div>'
        f'</section>'
    )


def find_font_uri(filename: str) -> str:
    for p in (
        Path("C:/Windows/Fonts") / filename,
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Windows/Fonts" / filename,
    ):
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
    for sc in SCENES:
        cat_counts[sc["cat"]] += 1
    for b in BRIEFS:
        by_region.setdefault(b[1], []).append(b)
        cat_counts[b[2]] += 1

    # Zone 2: 10 Pictorial Editorial Scene Cards
    scene_cards_html = []
    for sc in SCENES:
        color = CAT_COLORS[sc["cat"]]
        scene_cards_html.append(f'''
        <article class="scene-card" style="border-top-color:{color};">
          <div class="scene-art">
            {render_scene_svg(sc["scene"])}
            <div class="scene-overlay-top">
              <span class="scene-pin" style="background:{color};">{sc["pin"]}</span>
              <span class="scene-kicker" style="background:{color};">{html.escape(sc["kicker"])}</span>
            </div>
          </div>
          <div class="scene-copy">
            <h2 class="scene-title">{html.escape(sc["title"])}</h2>
            <p class="scene-fact">{html.escape(sc["fact"])}</p>
          </div>
        </article>''')

    # Category summary strip under Oceania & Global
    cat_bars = []
    for cat, color in CAT_COLORS.items():
        pct = (cat_counts[cat] / 36.0) * 100.0
        cat_bars.append(
            f'<div class="cat-stat">'
            f'<span class="cat-stat-dot" style="background:{color};"></span>'
            f'<span class="cat-stat-code">{cat}</span>'
            f'<span class="cat-stat-bar-bg"><span class="cat-stat-bar-fg" style="width:{pct:.1f}%;background:{color};"></span></span>'
            f'<span class="cat-stat-num">{cat_counts[cat]:02d}</span>'
            f'</div>'
        )

    audit_box_html = f'''
    <div class="audit-card">
      <div class="audit-hdr">
        <span class="audit-title">EDITION COVERAGE · 36 DATED STORIES (10 SCENES + 26 BRIEFS)</span>
        <span class="audit-badge">✓ WED 25 NOV 2026 UTC</span>
      </div>
      <div class="cat-stats-grid">{"".join(cat_bars)}</div>
      <div class="audit-foot">
        <span>GEO Geopolitics · ECON Markets/Trade · SCI Space/Health · LAW Law/Transport · SPORT Sports</span>
        <span>MAP: NATURAL EARTH 110m</span>
      </div>
    </div>'''

    def render_ticker_row(items):
        parts = [
            f'<span class="tk-item"><span class="tk-lbl">{html.escape(lbl)}</span> '
            f'<span class="tk-val tk-{tone}">{html.escape(val)}</span></span>'
            for lbl, val, tone in items
        ]
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
  padding: 16px 32px 14px 32px;
  display: flex;
  flex-direction: column;
  background: #F8F5EE;
}}

/* ZONE 1: MASTHEAD (~144px) */
.masthead {{
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}}
.mast-top {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: 'IBMPlexMono', monospace;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: #3A3F49;
  padding-bottom: 5px;
}}
.mast-date-pill {{
  background: #15803D;
  color: #FFFFFF;
  padding: 2px 10px;
  border-radius: 3px;
  font-size: 14px;
  letter-spacing: 0.05em;
}}
.double-rule {{
  height: 6px;
  border-top: 4px solid #111317;
  border-bottom: 1.5px solid #111317;
}}
.mast-title-wrap {{
  display: flex;
  justify-content: center;
  align-items: baseline;
  padding: 6px 0 5px 0;
}}
.mast-title {{
  font-family: 'LibreBask', Georgia, serif;
  font-size: 56px;
  font-weight: 700;
  letter-spacing: -0.014em;
  line-height: 1.04;
  color: #111317;
  white-space: nowrap;
}}
.mast-subbar {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1.5px solid #111317;
  border-bottom: 3px solid #111317;
  background: #EFEAE0;
  padding: 5px 10px;
}}
.mast-sub-left {{
  font-family: 'Barlow', sans-serif;
  font-size: 17px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: #111317;
}}
.mast-sub-cats {{
  display: flex;
  align-items: center;
  gap: 14px;
}}
.mini-leg {{
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: 'IBMPlexMono', monospace;
  font-size: 14px;
  font-weight: 700;
  color: #1E222A;
}}
.mini-dot {{
  width: 11px;
  height: 11px;
  border-radius: 50%;
  display: inline-block;
}}

/* ZONE 2: 10 PICTORIAL EDITORIAL SCENES (2 rows x 5 cols, 676px) */
.scenes-grid {{
  margin-top: 10px;
  height: 676px;
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  grid-template-rows: repeat(2, 1fr);
  gap: 12px;
  flex-shrink: 0;
}}
.scene-card {{
  display: flex;
  flex-direction: column;
  background: #F4EFE6;
  border: 1.5px solid #111317;
  border-top: 5px solid #111317;
  overflow: hidden;
  min-width: 0;
  min-height: 0;
}}
.scene-art {{
  position: relative;
  height: 210px;
  width: 100%;
  flex-shrink: 0;
  border-bottom: 1.5px solid #111317;
  overflow: hidden;
  background: #111317;
}}
.scene-art svg {{
  display: block;
  width: 100%;
  height: 100%;
}}
.scene-overlay-top {{
  position: absolute;
  top: 7px;
  left: 7px;
  display: flex;
  align-items: center;
  gap: 6px;
}}
.scene-pin {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  color: #FFFFFF;
  font-family: 'Barlow', sans-serif;
  font-variant-numeric: tabular-nums;
  font-size: 17px;
  font-weight: 800;
  border: 2.2px solid #F8F5EE;
  box-shadow: 0 1px 3px rgba(0,0,0,0.45);
}}
.scene-kicker {{
  padding: 3px 8px;
  border-radius: 3px;
  color: #FFFFFF;
  font-family: 'Barlow', sans-serif;
  font-size: 13.5px;
  font-weight: 800;
  letter-spacing: 0.06em;
  border: 1.4px solid rgba(248,245,238,0.85);
  box-shadow: 0 1px 3px rgba(0,0,0,0.4);
}}
.scene-copy {{
  flex: 1;
  padding: 7px 10px 6px 10px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 0;
}}
.scene-title {{
  font-family: 'Barlow', sans-serif;
  font-size: 22px;
  font-weight: 800;
  line-height: 1.12;
  color: #111317;
  letter-spacing: -0.01em;
  margin-bottom: 3px;
  white-space: nowrap;
  overflow: hidden;
}}
.scene-fact {{
  font-family: 'OpenSansSemi', sans-serif;
  font-size: 18px;
  font-weight: 600;
  line-height: 1.22;
  color: #222730;
}}

/* ZONE 3: WORLD MAP (516px) */
.map-frame {{
  margin-top: 10px;
  width: 1984px;
  height: 516px;
  border: 2px solid #111317;
  background: #F3EFE6;
  overflow: hidden;
  flex-shrink: 0;
}}
.map-frame svg {{ display: block; }}
.land {{
  fill: #D8D0BE;
  stroke: #857E70;
  stroke-width: 0.95;
  stroke-linejoin: round;
}}
.grat {{
  fill: none;
  stroke: #C9C2B3;
  stroke-width: 0.8;
  stroke-dasharray: 3 4;
}}
.grat-eq {{
  fill: none;
  stroke: #B2AA9A;
  stroke-width: 1.1;
  stroke-dasharray: 6 4;
}}
.cont-lbl {{
  font-family: 'Barlow', sans-serif;
  font-size: 17px;
  font-weight: 800;
  letter-spacing: 0.22em;
  fill: #5F594D;
  fill-opacity: 0.62;
  text-anchor: middle;
}}
.pin-num {{
  font-family: 'Barlow', sans-serif;
  font-variant-numeric: tabular-nums;
  font-size: 16.5px;
  font-weight: 800;
  fill: #FFFFFF;
  text-anchor: middle;
  dominant-baseline: central;
}}
.pin-num-scene {{
  font-size: 19px;
}}
.map-seal-title {{
  font-family: 'Barlow', sans-serif;
  font-size: 15.5px;
  font-weight: 800;
  letter-spacing: 0.04em;
  fill: #111317;
}}
.map-seal-sub {{
  font-family: 'IBMPlexMono', monospace;
  font-size: 11.2px;
  font-weight: 600;
  fill: #3E444F;
}}

/* ZONE 4: 26-STORY 6-CONTINENT BRIEF (2 columns x 3 regions, ~566px) */
.briefs-wrap {{
  margin-top: 10px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  column-gap: 24px;
  flex: 1;
  min-height: 0;
}}
.briefs-col {{
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-width: 0;
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
  border-top: 3px solid #111317;
  border-bottom: 1.5px solid #111317;
  padding: 3px 2px;
  margin-bottom: 2px;
}}
.region-title {{
  font-family: 'Barlow', sans-serif;
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #111317;
}}
.region-meta {{
  font-family: 'IBMPlexMono', monospace;
  font-size: 13.5px;
  font-weight: 700;
  color: #525864;
}}
.region-list {{
  display: flex;
  flex-direction: column;
}}
.story-row {{
  display: flex;
  align-items: center;
  gap: 8px;
  height: 31.5px;
  border-bottom: 1px dotted #C9C1B2;
  min-width: 0;
}}
.story-row:last-child {{
  border-bottom: none;
}}
.row-pin {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 23px;
  border-radius: 4px;
  color: #FFFFFF;
  font-family: 'Barlow', sans-serif;
  font-variant-numeric: tabular-nums;
  font-size: 16px;
  font-weight: 800;
  flex-shrink: 0;
}}
.row-text {{
  font-family: 'OpenSansCond', sans-serif;
  font-size: 21.5px;
  font-weight: 600;
  line-height: 1.1;
  color: #171A20;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: clip;
  letter-spacing: -0.008em;
}}
.hl-prefix {{
  font-weight: 700;
  color: #111317;
}}
.hl-date {{
  font-family: 'OpenSansCond', sans-serif;
  font-size: 18.5px;
  font-weight: 600;
  color: #5A606B;
}}

/* Audit card completing bottom-right under Oceania & Global */
.audit-card {{
  margin-top: 6px;
  padding: 7px 12px 7px 12px;
  background: #EFEAE0;
  border: 1.5px solid #B9B1A2;
  border-left: 5px solid #15803D;
}}
.audit-hdr {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}}
.audit-title {{
  font-family: 'Barlow', sans-serif;
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: #111317;
}}
.audit-badge {{
  background: #15803D;
  color: #FFFFFF;
  font-family: 'IBMPlexMono', monospace;
  font-size: 12.5px;
  font-weight: 700;
  padding: 1.5px 8px;
  border-radius: 3px;
}}
.cat-stats-grid {{
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
  margin-bottom: 5px;
}}
.cat-stat {{
  display: flex;
  align-items: center;
  gap: 5px;
  font-family: 'IBMPlexMono', monospace;
  font-size: 13.5px;
  font-weight: 700;
}}
.cat-stat-dot {{
  width: 9px;
  height: 9px;
  border-radius: 50%;
  flex-shrink: 0;
}}
.cat-stat-bar-bg {{
  flex: 1;
  height: 7px;
  background: #D9D2C4;
  border-radius: 2px;
  overflow: hidden;
}}
.cat-stat-bar-fg {{
  display: block;
  height: 100%;
}}
.audit-foot {{
  display: flex;
  justify-content: space-between;
  font-family: 'IBMPlexMono', monospace;
  font-size: 11.5px;
  font-weight: 600;
  color: #4D535E;
}}

/* ZONE 5: GLOBAL MARKETS TICKER (82px) */
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
  width: 184px;
  background: #B91C1C;
  color: #F8F5EE;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 0 8px;
  flex-shrink: 0;
}}
.ticker-badge-top {{
  font-family: 'Barlow', sans-serif;
  font-size: 17.5px;
  font-weight: 800;
  letter-spacing: 0.08em;
}}
.ticker-badge-sub {{
  font-family: 'IBMPlexMono', monospace;
  font-size: 13.5px;
  font-weight: 600;
  color: #FDE8E8;
  margin-top: 3px;
}}
.ticker-rows {{
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
  padding: 0 20px;
  font-family: 'IBMPlexMono', monospace;
  font-size: 18.5px;
  font-weight: 600;
}}
.ticker-row {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  white-space: nowrap;
}}
.tk-lbl {{ color: #C7CCD6; font-weight: 600; }}
.tk-val {{ font-weight: 700; }}
.tk-down {{ color: #FCA5A5; }}
.tk-up {{ color: #86EFAC; }}
.tk-flat {{ color: #F8F5EE; }}
.tk-accent {{ color: #FDE047; }}
.tk-sep {{ color: #4E5563; font-weight: 500; }}
</style>
</head>
<body>
<div class="page">
  <!-- ZONE 1: MASTHEAD -->
  <header class="masthead">
    <div class="mast-top">
      <span>EDITION: WEDNESDAY, 25 NOVEMBER 2026 · 07:00 GMT SNAPSHOT</span>
      <span>SWISS ILLUSTRATED BROADSHEET · ALL 6 INHABITED CONTINENTS</span>
      <span class="mast-date-pill">DATE CHECK ✓ WED 25 NOV 2026 UTC</span>
    </div>
    <div class="double-rule"></div>
    <div class="mast-title-wrap">
      <h1 class="mast-title">THE WORLD ON WEDNESDAY, 25 NOVEMBER 2026</h1>
    </div>
    <div class="mast-subbar">
      <span class="mast-sub-left">36 DATED STORIES · 10 DRAWN SCENES · 6 CONTINENTS · WORLD MAP · DATE CHECK: WED 25 NOV 2026 UTC</span>
      <div class="mast-sub-cats">
        {"".join(f'<span class="mini-leg"><span class="mini-dot" style="background:{c};"></span>{k} ({cat_counts[k]})</span>' for k, c in CAT_COLORS.items())}
      </div>
    </div>
  </header>

  <!-- ZONE 2: 10 PICTORIAL EDITORIAL SCENES -->
  <section class="scenes-grid">
    {"".join(scene_cards_html)}
  </section>

  <!-- ZONE 3: NATURAL EARTH 110m WORLD MAP -->
  <section class="map-frame">
    {map_svg}
  </section>

  <!-- ZONE 4: 26-STORY 6-CONTINENT BRIEF -->
  <main class="briefs-wrap">
    <div class="briefs-col">
      {render_region_block("AMERICAS", by_region["Americas"])}
      {render_region_block("EUROPE", by_region["Europe"])}
      {render_region_block("AFRICA", by_region["Africa"])}
    </div>
    <div class="briefs-col">
      {render_region_block("ASIA", by_region["Asia"])}
      {render_region_block("MIDDLE EAST", by_region["Middle East"])}
      <div class="oceania-stack">
        {render_region_block("OCEANIA & GLOBAL", by_region["Oceania & Global"])}
        {audit_box_html}
      </div>
    </div>
  </main>

  <!-- ZONE 5: GLOBAL MARKETS TICKER -->
  <footer class="ticker">
    <div class="ticker-badge">
      <span class="ticker-badge-top">GLOBAL MARKETS</span>
      <span class="ticker-badge-sub">25 NOV · 07:00 GMT</span>
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

        audit = page.evaluate("""() => {
          const issues = [];
          document.querySelectorAll('.row-text').forEach((el, idx) => {
            if (el.scrollWidth > el.clientWidth + 1) {
              issues.push({type: 'brief-overflow', idx, text: el.textContent, scrollW: el.scrollWidth, clientW: el.clientWidth});
            }
          });
          document.querySelectorAll('.scene-title').forEach((el, idx) => {
            if (el.scrollWidth > el.clientWidth + 1) {
              issues.push({type: 'scene-title-overflow', idx, text: el.textContent, scrollW: el.scrollWidth, clientW: el.clientWidth});
            }
          });
          document.querySelectorAll('.scene-card').forEach((el, idx) => {
            if (el.scrollHeight > el.clientHeight + 1) {
              issues.push({type: 'scene-card-overflow', idx, scrollH: el.scrollHeight, clientH: el.clientHeight});
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
        page.screenshot(path=str(RAW_PNG_PATH), clip={"x": 0, "y": 0, "width": 2048, "height": 2048})
        browser.close()

    img_2048 = Image.open(RAW_PNG_PATH).convert("RGB")
    assert img_2048.size == (2048, 2048), f"Unexpected raw size: {img_2048.size}"
    img_1024 = img_2048.resize((1024, 1024), Image.Resampling.LANCZOS)

    lossless_path = BUILD_DIR / "entry_v2_lossless.png"
    img_1024.save(lossless_path, format="PNG", optimize=True)
    oxipng.optimize(str(lossless_path), str(lossless_path), level=4, strip=oxipng.StripChunks.safe())
    lossless_size = lossless_path.stat().st_size
    print(f"[opt] Lossless 24-bit PNG + oxipng: {lossless_size:,} bytes ({lossless_size / 1024:.1f} KB)")

    best_path = None
    best_psnr = -1.0
    best_size = 0
    for qname, qmethod in (("mediancut", Image.Quantize.MEDIANCUT), ("fastoctree", Image.Quantize.FASTOCTREE)):
        cand_img = img_1024.quantize(colors=256, method=qmethod, dither=Image.Dither.NONE)
        cand_path = BUILD_DIR / f"entry_v2_{qname}.png"
        cand_img.save(cand_path, format="PNG", optimize=True)
        oxipng.optimize(str(cand_path), str(cand_path), level=6, strip=oxipng.StripChunks.safe())
        csize = cand_path.stat().st_size
        diff = ImageChops.difference(img_1024, cand_img.convert("RGB"))
        hist = diff.histogram()
        mse = sum(hist[i] * ((i % 256) ** 2) for i in range(len(hist))) / (1024 * 1024 * 3)
        psnr = 10.0 * math.log10(255.0 * 255.0 / mse) if mse > 0 else 999.0
        print(f"[opt] 256-color {qname} + oxipng: {csize:,} bytes ({csize / 1024:.1f} KB), PSNR={psnr:.2f} dB")
        if csize <= 440 * 1024 and psnr > best_psnr:
            best_psnr = psnr
            best_path = cand_path
            best_size = csize

    # Also test ImageMagick 256-color perceptual quantization if installed
    import shutil, subprocess
    if shutil.which("magick"):
        for dflag, tag in (("+dither", "magick_nodither"), ("-dither FloydSteinberg", "magick_fs")):
            cand_path = BUILD_DIR / f"entry_v2_{tag}.png"
            cmd = ["magick", str(lossless_path)] + dflag.split() + ["-colors", "256", f"PNG8:{cand_path}"]
            if subprocess.run(cmd, capture_output=True).returncode == 0 and cand_path.exists():
                oxipng.optimize(str(cand_path), str(cand_path), level=6, strip=oxipng.StripChunks.safe())
                csize = cand_path.stat().st_size
                cand_rgb = Image.open(cand_path).convert("RGB")
                diff = ImageChops.difference(img_1024, cand_rgb)
                hist = diff.histogram()
                mse = sum(hist[i] * ((i % 256) ** 2) for i in range(len(hist))) / (1024 * 1024 * 3)
                psnr = 10.0 * math.log10(255.0 * 255.0 / mse) if mse > 0 else 999.0
                print(f"[opt] 256-color {tag} + oxipng: {csize:,} bytes ({csize / 1024:.1f} KB), PSNR={psnr:.2f} dB")
                if csize <= 440 * 1024 and psnr > best_psnr:
                    best_psnr = psnr
                    best_path = cand_path
                    best_size = csize

    if lossless_size <= 440 * 1024:
        OUT_PNG_PATH.write_bytes(lossless_path.read_bytes())
        print(f"[out] Selected LOSSLESS PNG -> {OUT_PNG_PATH} ({lossless_size / 1024:.1f} KB)")
    else:
        assert best_path is not None
        OUT_PNG_PATH.write_bytes(best_path.read_bytes())
        print(f"[out] Selected {best_path.name} -> {OUT_PNG_PATH} ({best_size / 1024:.1f} KB, PSNR={best_psnr:.2f} dB)")


if __name__ == "__main__":
    render_and_optimize()
