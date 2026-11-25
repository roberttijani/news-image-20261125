#!/usr/bin/env python3
"""
v3 Build script for the Wednesday 25 November 2026 Global Dispatch Broadsheet.

Modeled on the high-hierarchy broadsheet architecture:
  - Top Header (11%): Dark navy dispatch strip, giant serif masthead, crimson italic subtitle,
    6-KPI strip, and 6-continent proportion bar (38 dated stories).
  - Row 1 (23%): 3 large Lead Story Cards (#1-#3) with original FT/Economist geometric vector
    art, epistemic status badges (OFFICIAL / REPORTED), and crimson "WHY IT MATTERS" takeaways.
  - Rows 2-3 (32%): 10 Illustrated Secondary Cards (#4-#13, 2x5 grid) with custom geometric
    vector scenes, sharp black stat pills, concise facts, and source/status tags.
  - Bottom Split (27%): Left (35%) Natural Earth 110m World Map plotting ONLY pins 1-13 with
    zero collisions + continent legend; Right (65%) 2-column brief of 25 more dated stories (#14-#38).
  - Bottom Footer (7%): Strict crimson-bordered DATE CHECK & excluded-wires verification strip.

Renders at 2048x2048 via headless Chromium (Playwright), Lanczos-downscales to 1024x1024 PNG,
and optimizes with PIL quantization + oxipng (< 450 KB).
"""

from __future__ import annotations

import html
import json
import math
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

import oxipng
from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "scripts" / "data" / "ne_110m_countries.geojson"
BUILD_DIR = ROOT / "tmp"
HTML_PATH = BUILD_DIR / "broadsheet_v3.html"
RAW_PNG_PATH = BUILD_DIR / "broadsheet_v3_2048.png"
OUT_PNG_PATH = ROOT / "assets" / "entry.png"

CONT_COLORS: Dict[str, str] = {
    "ASIA": "#0F766E",
    "EUROPE": "#1D4ED8",
    "AMERICAS": "#B91C1C",
    "MIDDLE EAST": "#B45309",
    "AFRICA": "#15803D",
    "OCEANIA & GLOBAL": "#6D28D9",
}

CONT_COUNTS: List[Tuple[str, int]] = [
    ("ASIA", 10),
    ("EUROPE", 9),
    ("AMERICAS", 7),
    ("MIDDLE EAST", 5),
    ("AFRICA", 4),
    ("OCEANIA & GLOBAL", 3),
]

KPIS: List[Tuple[str, str, str]] = [
    ("1ST", "Pakistani astronaut at Tiangong", "#0F766E"),
    ("-6.2%", "Seoul KOSPI AI rout", "#B91C1C"),
    ("+26%", "UK energy cap hike", "#B45309"),
    ("16", "US tariff target economies", "#1D4ED8"),
    ("204", "15-yr-old Sooryavanshi (53b)", "#6D28D9"),
    ("4.90%", "US 10Y Treasury yield", "#0F172A"),
]

# Row 1: 3 Lead Story Cards (#1-#3)
LEADS = [
    {
        "pin": 1,
        "continent": "ASIA",
        "kicker": "SPACE · 00:18 UTC",
        "status": "OFFICIAL",
        "headline": "Shenzhou-24 Launches & Docks with First Pakistani Astronaut",
        "summary": "Long March-2F lifts off from Jiuquan carrying Muhammad Zeeshan Ali to Tiangong as China's first foreign crew member (SCMP, The Hindu).",
        "why": "Cementing Tiangong as an international orbital rival to the aging ISS.",
        "lat": 40.96,
        "lon": 100.29,
        "scene": "shenzhou",
    },
    {
        "pin": 2,
        "continent": "ASIA",
        "kicker": "MARKETS · 07:00 GMT",
        "status": "REPORTED",
        "headline": "Asia Chip Rout Sends KOSPI Down 6.2% as Huang Rally Dies",
        "summary": "Seoul's KOSPI plunges 6.2% (4,697), Nikkei -2.8%, Nvidia -5.9%, and Anthropic slips below IPO price (Bangkok Post, KED Global).",
        "why": "Deepening doubts over 2027 AI capex returns despite Nvidia's CEO reinstatement.",
        "lat": 37.57,
        "lon": 126.98,
        "scene": "kospi",
    },
    {
        "pin": 3,
        "continent": "AMERICAS",
        "kicker": "TRADE · 25 NOV",
        "status": "REPORTED",
        "headline": "US Readies Fresh Tariffs on China, EU, India & 13 Partners",
        "summary": "Washington prepares new duties over subsidized production ahead of the Jan 10 US-China interim deal expiry (AP, Indian Express).",
        "why": "Threatens to reignite global goods inflation just ahead of US Oct PCE data (3.8% forecast).",
        "lat": 38.90,
        "lon": -77.04,
        "scene": "tariffs",
    },
]

# Rows 2-3: 10 Secondary Illustrated Cards (#4-#13)
SECONDARY = [
    {
        "pin": 4,
        "continent": "EUROPE",
        "title": "UK Energy Cap Jumps 26%",
        "stat": "+26% JAN",
        "fact": "Ofgem hikes Great Britain household cap for 3rd straight quarter.",
        "source": "Ofgem, Guardian",
        "status": "OFFICIAL",
        "lat": 53.80,
        "lon": -1.55,
        "scene": "uk_energy",
    },
    {
        "pin": 5,
        "continent": "EUROPE",
        "title": "Eurostar Strike Halts Trains",
        "stat": "HALTED",
        "fact": "Unannounced staff walkout cancels Paris–London Channel Tunnel trains.",
        "source": "AP",
        "status": "REPORTED",
        "lat": 50.95,
        "lon": 1.85,
        "scene": "eurostar",
    },
    {
        "pin": 6,
        "continent": "MIDDLE EAST",
        "title": "Riyadh Tower Hit Again",
        "stat": "11+ HURT",
        "fact": "2nd Houthi strike in a week hits Saudi capital; US warns citizens.",
        "source": "Standard HK, Eg. Gazette",
        "status": "REPORTED",
        "lat": 24.71,
        "lon": 46.67,
        "scene": "riyadh",
    },
    {
        "pin": 7,
        "continent": "AMERICAS",
        "title": "CIA & ODNI Cyber Breach",
        "stat": "4 AGENCIES",
        "fact": "Unclassified US open-source intel network hacked; MSFT declares Code Red.",
        "source": "Cybernews, WSJ",
        "status": "REPORTED",
        "lat": 47.67,
        "lon": -122.12,
        "scene": "cyber",
    },
    {
        "pin": 8,
        "continent": "AFRICA",
        "title": "WHO Ebola Teams Trapped",
        "stat": "1.5M JABS",
        "fact": "Heavy Ituri fighting traps DRC Ebola responders; Gavi buys 1.5M vaccines.",
        "source": "WHO, PRX",
        "status": "OFFICIAL",
        "lat": 1.85,
        "lon": 30.05,
        "scene": "ebola",
    },
    {
        "pin": 9,
        "continent": "OCEANIA & GLOBAL",
        "title": "Australia–Solomons Pact",
        "stat": "SECURITY",
        "fact": "Canberra edges China out with primary Pacific security partner treaty.",
        "source": "Japan Times",
        "status": "OFFICIAL",
        "lat": -9.43,
        "lon": 159.95,
        "scene": "pacific",
    },
    {
        "pin": 10,
        "continent": "MIDDLE EAST",
        "title": "Teen Smashes 204 off 53",
        "stat": "28 SIXES",
        "fact": "15-yr-old Vaibhav Sooryavanshi breaks List A 100 & 200 records vs UAE.",
        "source": "TOI",
        "status": "OFFICIAL",
        "lat": 24.45,
        "lon": 54.38,
        "scene": "cricket",
    },
    {
        "pin": 11,
        "continent": "ASIA",
        "title": "Xi Probes Shanghai Boss",
        "stat": "POLITBURO",
        "fact": "Shock corruption probe widens China leadership shakeup ahead of 2027.",
        "source": "Japan Times, Hindu",
        "status": "OFFICIAL",
        "lat": 31.23,
        "lon": 121.47,
        "scene": "xi_probe",
    },
    {
        "pin": 12,
        "continent": "AMERICAS",
        "title": "Gold Breaks Below $3,600",
        "stat": "-2.25%",
        "fact": "Tech sell-off drags gold to $3,552 & silver -5.22% ($40.79); Brent $89.99.",
        "source": "Mitrade, Bangkok Post",
        "status": "REPORTED",
        "lat": 40.71,
        "lon": -74.01,
        "scene": "gold_drop",
    },
    {
        "pin": 13,
        "continent": "OCEANIA & GLOBAL",
        "title": "UN Nov 25 Femicide Alert",
        "stat": "47,000",
        "fact": "UNODC/UN Women report 5 women killed every hour by partners/family in 2025.",
        "source": "UN News",
        "status": "OFFICIAL",
        "lat": 48.20,
        "lon": 16.37,
        "scene": "un_femicide",
    },
]

# Bottom Right: 25 More Stories (#14-#38) — (pin, continent, prefix, body, source)
BRIEFS: List[Tuple[int, str, str, str, str]] = [
    (14, "AMERICAS", "US", "Pentagon weighs $15B loan to Trump Jr.-linked AI firm Hadrian", "ProPublica"),
    (15, "AMERICAS", "US", "Nvidia's Huang apologizes to staff, cites therapy amid slide", "Eg. Gazette"),
    (16, "AMERICAS", "US", "Markets eye Oct PCE inflation (3.8% f'cast); Dow +0.9% at 50,018", "Mitrade, BP"),
    (17, "ASIA", "US/China", "China extends gallium/germanium/antimony export-ban pause to Jan 27", "IE"),
    (18, "AMERICAS", "Latin America", "IDB says AI could lift regional growth 5% with reforms", "IntelliNews"),
    (19, "EUROPE", "EU", "Europol traces €26M crypto trail in 11-nation IPTV piracy bust", "Brussels Times"),
    (20, "EUROPE", "EU", "Commission warns Bulgaria & Hungary of funding freeze over deficits", "EU Persp."),
    (21, "EUROPE", "Poland", "Leads all EU states in net budget receipts at €6.7B", "IW Report"),
    (22, "EUROPE", "Denmark", "Supreme Court upholds \"non-Western\" housing evictions law", "CBS"),
    (23, "EUROPE", "Europe", "Decathlon confirms customer data breach", "Cybernews"),
    (24, "EUROPE", "Russia/Brunei", "Putin holds Nov 25 talks with Sultan Hassanal Bolkiah", "Kremlin"),
    (25, "EUROPE", "UCL", "Real Madrid thrash PSV 5–1; Como near knockouts; Sporting host Man Utd", "AFP"),
    (26, "MIDDLE EAST", "Israel", "Eisenkot strikes first coalition deal to form government", "Eg. Gazette"),
    (27, "MIDDLE EAST", "Yemen/Iran", "Houthis advance near Aden as Iran vows to break US blockade", "DNE"),
    (28, "MIDDLE EAST", "Gulf", "Allianz pegs Iran war cost to Gulf states at $790B by 2030", "IntelliNews"),
    (29, "AFRICA", "DR Congo", "Revives cobalt export ban from Nov 30 as prices slide", "DNE Africa"),
    (30, "AFRICA", "Nigeria", "Central Bank holds rate at 23% amid energy & inflation risks", "DNE Africa"),
    (31, "AFRICA", "Southern Africa", "Angola seeks $180M for 10% De Beers stake; IMF cuts Botswana to 3%", "IN"),
    (32, "AFRICA", "Togo", "National vaccination coverage climbs to 90% over 45-yr push", "DNE Africa"),
    (33, "ASIA", "South Korea", "Relocating 31 agencies to Sejong; 10-yr ban for AI exam cheats", "Korea Times"),
    (34, "ASIA", "Taiwan", "Voters prepare for 11,000-seat local elections testing ruling DPP", "Japan Times"),
    (35, "ASIA", "Thailand", "Informal economy 48% of GDP; seeks China help on Myanmar mines", "TE, JT"),
    (36, "ASIA", "Philippines/Macau", "BSP proposes payment-rail gambling curbs; Macau revenue steady", "iGT"),
    (37, "OCEANIA & GLOBAL", "Australia", "Defence issues Nov 25 apology to staff; Lamarre-Condon guilty", "Def. AU, Grdn"),
    (38, "OCEANIA & GLOBAL", "Space (ESA)", "Hera mission schedules Nov 25 release of first asteroid Dimorphos images", "SPO"),
]


# ---------------------------------------------------------------------------
# 13 Original Geometric Editorial Vector Scenes (FT / Economist flat print)
# ---------------------------------------------------------------------------
def render_scene_svg(kind: str) -> str:
    # Wide Lead Cards (1-3): 580 x 216 viewBox
    if kind == "shenzhou":
        return '''<svg viewBox="0 0 580 216" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
  <rect width="580" height="216" fill="#0D192E"/>
  <g fill="#F8F5EE" opacity="0.85">
    <circle cx="48" cy="34" r="2.2"/><circle cx="118" cy="22" r="1.6"/><circle cx="212" cy="40" r="1.8"/>
    <circle cx="318" cy="26" r="2.1" fill="#FDE68A"/><circle cx="468" cy="30" r="1.9"/><circle cx="534" cy="56" r="2.2" fill="#93C5FD"/>
    <circle cx="76" cy="82" r="1.5"/><circle cx="418" cy="112" r="1.6"/>
  </g>
  <ellipse cx="290" cy="336" rx="390" ry="160" fill="#0F766E" opacity="0.35"/>
  <ellipse cx="290" cy="346" rx="378" ry="156" fill="#1D4ED8"/>
  <ellipse cx="290" cy="353" rx="372" ry="152" fill="#1E3A8A"/>
  <path d="M55 210 Q180 165 320 184 T540 208 L580 216 L0 216 Z" fill="#15803D" opacity="0.52"/>
  <path d="M72 195 Q290 144 508 195" fill="none" stroke="#5EEAD4" stroke-width="3.6" opacity="0.88"/>
  <path d="M56 154 Q188 78 332 88" fill="none" stroke="#5EEAD4" stroke-width="2.4" stroke-dasharray="7 5"/>
  <!-- Tiangong Orbital Station -->
  <g transform="translate(394, 84) rotate(-10)">
    <rect x="-56" y="-62" width="18" height="48" rx="1.5" fill="#D97706" stroke="#0F172A" stroke-width="2"/>
    <rect x="-56" y="14" width="18" height="48" rx="1.5" fill="#D97706" stroke="#0F172A" stroke-width="2"/>
    <rect x="38" y="-62" width="18" height="48" rx="1.5" fill="#D97706" stroke="#0F172A" stroke-width="2"/>
    <rect x="38" y="14" width="18" height="48" rx="1.5" fill="#D97706" stroke="#0F172A" stroke-width="2"/>
    <line x1="-47" y1="-62" x2="-47" y2="-14" stroke="#FDE68A" stroke-width="1.3"/>
    <line x1="-47" y1="14" x2="-47" y2="62" stroke="#FDE68A" stroke-width="1.3"/>
    <line x1="47" y1="-62" x2="47" y2="-14" stroke="#FDE68A" stroke-width="1.3"/>
    <line x1="47" y1="14" x2="47" y2="62" stroke="#FDE68A" stroke-width="1.3"/>
    <rect x="-74" y="-12" width="148" height="24" rx="6" fill="#F8F5EE" stroke="#0F172A" stroke-width="2.2"/>
    <rect x="-18" y="-17" width="36" height="34" rx="4" fill="#E5DFD2" stroke="#0F172A" stroke-width="2.2"/>
    <circle cx="0" cy="0" r="6.5" fill="#0F766E" stroke="#0F172A" stroke-width="1.6"/>
    <rect x="-76" y="-7" width="10" height="14" fill="#B91C1C"/>
  </g>
  <!-- Shenzhou-24 Capsule approaching docking port -->
  <g transform="translate(204, 108) rotate(-10)">
    <polygon points="-64,0 -92,-10 -82,0 -92,10" fill="#F59E0B"/>
    <polygon points="-64,0 -79,-4 -79,4" fill="#FEF3C7"/>
    <rect x="-42" y="-38" width="14" height="26" fill="#2563EB" stroke="#0F172A" stroke-width="1.8"/>
    <rect x="-42" y="12" width="14" height="26" fill="#2563EB" stroke="#0F172A" stroke-width="1.8"/>
    <rect x="-62" y="-11" width="38" height="22" rx="2" fill="#CBD5E1" stroke="#0F172A" stroke-width="2"/>
    <path d="M-24 -12 L8 -14 L22 -9 L22 9 L8 14 L-24 12 Z" fill="#F8F5EE" stroke="#0F172A" stroke-width="2"/>
    <circle cx="29" cy="0" r="10" fill="#F8F5EE" stroke="#0F172A" stroke-width="2"/>
    <rect x="39" y="-4" width="8" height="8" fill="#0F766E" stroke="#0F172A" stroke-width="1.6"/>
    <rect x="-8" y="-4" width="12" height="8" rx="1.5" fill="#0F766E"/>
  </g>
  <line x1="256" y1="99" x2="314" y2="90" stroke="#5EEAD4" stroke-width="3.2" stroke-dasharray="5 4"/>
  <!-- China + Pakistan orbital mission emblem -->
  <g transform="translate(426, 166)">
    <rect x="0" y="0" width="140" height="36" rx="4" fill="#0F172A" stroke="#5EEAD4" stroke-width="1.8"/>
    <rect x="8" y="8" width="28" height="20" rx="2" fill="#B91C1C"/>
    <polygon points="18,12 19.5,16 24,16 20.4,18.5 21.8,23 18,20.3 14.2,23 15.6,18.5 12,16 16.5,16" fill="#FDE047"/>
    <rect x="42" y="8" width="28" height="20" rx="2" fill="#15803D"/>
    <rect x="42" y="8" width="6.5" height="20" fill="#F8F5EE"/>
    <circle cx="59" cy="18" r="5.5" fill="#F8F5EE"/>
    <circle cx="61" cy="16.5" r="4.8" fill="#15803D"/>
    <text x="104" y="23" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="700" font-size="13" fill="#5EEAD4">SZ-24</text>
  </g>
</svg>'''

    if kind == "kospi":
        return '''<svg viewBox="0 0 580 216" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
  <rect width="580" height="216" fill="#131926"/>
  <g stroke="#243047" stroke-width="1.2">
    <line x1="0" y1="48" x2="580" y2="48"/><line x1="0" y1="92" x2="580" y2="92"/>
    <line x1="0" y1="136" x2="580" y2="136"/><line x1="0" y1="180" x2="580" y2="180"/>
    <line x1="96" y1="0" x2="96" y2="216"/><line x1="192" y1="0" x2="192" y2="216"/>
    <line x1="288" y1="0" x2="288" y2="216"/><line x1="384" y1="0" x2="384" y2="216"/>
    <line x1="480" y1="0" x2="480" y2="216"/>
  </g>
  <polygon points="22,62 84,52 146,78 208,74 270,122 332,148 394,174 460,192 460,216 22,216" fill="#B91C1C" opacity="0.24"/>
  <!-- Candlesticks -->
  <line x1="44" y1="40" x2="44" y2="76" stroke="#22C55E" stroke-width="2.6"/><rect x="34" y="48" width="20" height="18" fill="#16A34A"/>
  <line x1="96" y1="34" x2="96" y2="68" stroke="#22C55E" stroke-width="2.6"/><rect x="86" y="42" width="20" height="17" fill="#16A34A"/>
  <line x1="152" y1="44" x2="152" y2="96" stroke="#F87171" stroke-width="2.6"/><rect x="141" y="54" width="22" height="32" fill="#DC2626"/>
  <line x1="212" y1="68" x2="212" y2="118" stroke="#F87171" stroke-width="2.6"/><rect x="201" y="76" width="22" height="30" fill="#DC2626"/>
  <line x1="274" y1="88" x2="274" y2="152" stroke="#F87171" stroke-width="2.8"/><rect x="262" y="96" width="24" height="44" fill="#B91C1C"/>
  <line x1="336" y1="116" x2="336" y2="178" stroke="#F87171" stroke-width="2.8"/><rect x="324" y="124" width="24" height="40" fill="#B91C1C"/>
  <line x1="398" y1="142" x2="398" y2="198" stroke="#F87171" stroke-width="3"/><rect x="385" y="150" width="26" height="38" fill="#EF4444"/>
  <polyline points="26,58 96,48 152,72 212,92 274,126 336,154 420,186" fill="none" stroke="#FCA5A5" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"/>
  <polygon points="436,192 412,191 422,172" fill="#FCA5A5"/>
  <!-- Cracked AI Processor -->
  <g transform="translate(466, 28)">
    <rect x="10" y="10" width="66" height="66" rx="6" fill="#1E3A8A" stroke="#60A5FA" stroke-width="2.6"/>
    <rect x="22" y="22" width="42" height="42" rx="3" fill="#0F172A" stroke="#93C5FD" stroke-width="1.8"/>
    <text x="43" y="49" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="20" fill="#93C5FD">AI</text>
    <g stroke="#60A5FA" stroke-width="2.6">
      <line x1="24" y1="0" x2="24" y2="10"/><line x1="43" y1="0" x2="43" y2="10"/><line x1="62" y1="0" x2="62" y2="10"/>
      <line x1="24" y1="76" x2="24" y2="86"/><line x1="43" y1="76" x2="43" y2="86"/><line x1="62" y1="76" x2="62" y2="86"/>
      <line x1="0" y1="24" x2="10" y2="24"/><line x1="0" y1="43" x2="10" y2="43"/><line x1="0" y1="62" x2="10" y2="62"/>
      <line x1="76" y1="24" x2="86" y2="24"/><line x1="76" y1="43" x2="86" y2="43"/><line x1="76" y1="62" x2="86" y2="62"/>
    </g>
    <polyline points="18,16 40,34 32,48 64,70" fill="none" stroke="#EF4444" stroke-width="3.6" stroke-linecap="round"/>
  </g>
  <rect x="18" y="144" width="218" height="56" rx="5" fill="#B91C1C" stroke="#FCA5A5" stroke-width="2"/>
  <text x="127" y="169" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="25" fill="#FFFFFF">KOSPI -6.2%</text>
  <text x="127" y="190" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="700" font-size="13" fill="#FEE2E2">NVDA -5.9% · NKY -2.8%</text>
</svg>'''

    if kind == "tariffs":
        return '''<svg viewBox="0 0 580 216" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
  <rect width="580" height="216" fill="#E6EEF5"/>
  <rect x="0" y="144" width="580" height="72" fill="#1D4ED8"/>
  <rect x="0" y="172" width="580" height="44" fill="#1E3A8A"/>
  <path d="M0 162 Q36 154 72 162 T144 162 T216 162 T288 162 T360 162 T432 162 T504 162 T576 162" fill="none" stroke="#93C5FD" stroke-width="2.4"/>
  <path d="M-20 188 Q24 180 68 188 T156 188 T244 188 T332 188 T420 188 T508 188 T596 188" fill="none" stroke="#60A5FA" stroke-width="2"/>
  <!-- Container Vessel -->
  <g transform="translate(34, 44)">
    <rect x="24" y="34" width="42" height="62" fill="#F8F5EE" stroke="#0F172A" stroke-width="2.2"/>
    <rect x="30" y="42" width="30" height="12" fill="#1E3A8A"/>
    <rect x="36" y="18" width="14" height="16" fill="#B91C1C" stroke="#0F172A" stroke-width="2"/>
    <rect x="74" y="70" width="56" height="26" fill="#B91C1C" stroke="#0F172A" stroke-width="2"/>
    <rect x="132" y="70" width="56" height="26" fill="#0F766E" stroke="#0F172A" stroke-width="2"/>
    <rect x="190" y="70" width="56" height="26" fill="#D97706" stroke="#0F172A" stroke-width="2"/>
    <rect x="248" y="70" width="52" height="26" fill="#334155" stroke="#0F172A" stroke-width="2"/>
    <rect x="82" y="42" width="56" height="26" fill="#1D4ED8" stroke="#0F172A" stroke-width="2"/>
    <rect x="140" y="42" width="56" height="26" fill="#D97706" stroke="#0F172A" stroke-width="2"/>
    <rect x="198" y="42" width="56" height="26" fill="#0F766E" stroke="#0F172A" stroke-width="2"/>
    <rect x="112" y="14" width="56" height="26" fill="#B91C1C" stroke="#0F172A" stroke-width="2"/>
    <rect x="170" y="14" width="56" height="26" fill="#1D4ED8" stroke="#0F172A" stroke-width="2"/>
    <path d="M10 96 L320 96 L300 126 L26 126 Z" fill="#0F172A"/>
    <path d="M18 114 L308 114 L300 126 L26 126 Z" fill="#B91C1C"/>
  </g>
  <!-- Customs Tariff Barrier -->
  <g transform="translate(394, 24)">
    <rect x="0" y="0" width="14" height="176" fill="#F8F5EE" stroke="#0F172A" stroke-width="2.2"/>
    <rect x="0" y="14" width="14" height="20" fill="#B91C1C"/><rect x="0" y="52" width="14" height="20" fill="#B91C1C"/>
    <rect x="0" y="90" width="14" height="20" fill="#B91C1C"/><rect x="0" y="128" width="14" height="20" fill="#B91C1C"/>
  </g>
  <!-- Embossed Red Tariff Seal -->
  <g transform="translate(492, 92) rotate(-8)">
    <circle cx="0" cy="0" r="60" fill="#F8F5EE" stroke="#B91C1C" stroke-width="5"/>
    <circle cx="0" cy="0" r="50" fill="none" stroke="#B91C1C" stroke-width="1.8" stroke-dasharray="5 3"/>
    <text x="0" y="-16" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="13.5" fill="#B91C1C" letter-spacing="1">US TARIFFS</text>
    <text x="0" y="20" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="40" fill="#0F172A">16</text>
    <text x="0" y="38" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="700" font-size="11.5" fill="#B91C1C">ECONOMIES</text>
  </g>
</svg>'''

    # Secondary Cards (4-13): 382 x 192 viewBox
    if kind == "uk_energy":
        return '''<svg viewBox="0 0 382 192" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
  <rect width="382" height="192" fill="#DCE5EE"/>
  <rect x="0" y="140" width="382" height="52" fill="#D5CCB8"/>
  <line x1="0" y1="140" x2="382" y2="140" stroke="#0F172A" stroke-width="2"/>
  <g transform="translate(20, 32)">
    <polygon points="8,42 62,10 116,42" fill="#334155" stroke="#0F172A" stroke-width="2.2"/>
    <rect x="86" y="6" width="16" height="22" fill="#991B1B" stroke="#0F172A" stroke-width="2"/>
    <rect x="16" y="42" width="92" height="78" fill="#C25E44" stroke="#0F172A" stroke-width="2.2"/>
    <rect x="28" y="54" width="22" height="22" fill="#FDE68A" stroke="#0F172A" stroke-width="1.8"/>
    <rect x="74" y="54" width="22" height="22" fill="#FDE68A" stroke="#0F172A" stroke-width="1.8"/>
    <rect x="52" y="88" width="20" height="32" fill="#1D4ED8" stroke="#0F172A" stroke-width="1.8"/>
    <g transform="translate(12, 108)">
      <rect x="0" y="6" width="102" height="26" rx="4" fill="#F8F5EE" stroke="#0F172A" stroke-width="2"/>
      <line x1="18" y1="6" x2="18" y2="32" stroke="#0F172A" stroke-width="2"/><line x1="36" y1="6" x2="36" y2="32" stroke="#0F172A" stroke-width="2"/>
      <line x1="54" y1="6" x2="54" y2="32" stroke="#0F172A" stroke-width="2"/><line x1="72" y1="6" x2="72" y2="32" stroke="#0F172A" stroke-width="2"/>
      <line x1="88" y1="6" x2="88" y2="32" stroke="#0F172A" stroke-width="2"/>
    </g>
  </g>
  <g transform="translate(254, 114)">
    <circle cx="0" cy="0" r="72" fill="#F8F5EE" stroke="#0F172A" stroke-width="3"/>
    <path d="M-56 10 A58 58 0 0 1 -25 -52" fill="none" stroke="#15803D" stroke-width="13"/>
    <path d="M-21 -53 A58 58 0 0 1 25 -52" fill="none" stroke="#D97706" stroke-width="13"/>
    <path d="M29 -49 A58 58 0 0 1 56 10" fill="none" stroke="#B91C1C" stroke-width="15"/>
    <polygon points="-5,4 4,7 46,-32" fill="#0F172A"/>
    <circle cx="0" cy="0" r="9" fill="#B91C1C" stroke="#0F172A" stroke-width="2"/>
    <rect x="-44" y="18" width="88" height="30" rx="4" fill="#0F172A"/>
    <text x="0" y="40" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="22" fill="#FCA5A5">+26%</text>
    <text x="14" y="-12" font-family="Barlow, sans-serif" font-weight="800" font-size="20" fill="#0F172A">£</text>
  </g>
</svg>'''

    if kind == "eurostar":
        return '''<svg viewBox="0 0 382 192" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
  <rect width="382" height="192" fill="#DCE4EE"/>
  <path d="M0 70 Q120 18 264 52 L382 28 L382 142 L0 142 Z" fill="#6B8E76"/>
  <rect x="0" y="138" width="382" height="54" fill="#B8B0A0"/>
  <rect x="26" y="28" width="192" height="112" rx="4" fill="#D4CBB8" stroke="#0F172A" stroke-width="2.4"/>
  <path d="M52 140 L52 80 A70 50 0 0 1 192 80 L192 140 Z" fill="#18202C" stroke="#0F172A" stroke-width="2.4"/>
  <line x1="94" y1="140" x2="26" y2="192" stroke="#334155" stroke-width="4.5"/>
  <line x1="176" y1="140" x2="256" y2="192" stroke="#334155" stroke-width="4.5"/>
  <line x1="72" y1="158" x2="200" y2="158" stroke="#64748B" stroke-width="3"/>
  <line x1="48" y1="174" x2="228" y2="174" stroke="#64748B" stroke-width="3.2"/>
  <g transform="translate(88, 64)">
    <path d="M18 14 Q64 4 108 14 L132 54 Q134 74 112 78 L12 78 Q-4 74 4 54 Z" fill="#1D4ED8" stroke="#0F172A" stroke-width="2.4"/>
    <path d="M4 54 L128 54 L124 64 L2 64 Z" fill="#F59E0B"/>
    <path d="M22 20 Q64 14 102 20 L114 44 L12 44 Z" fill="#0F172A" stroke="#93C5FD" stroke-width="1.6"/>
    <ellipse cx="22" cy="70" rx="8" ry="3.5" fill="#FEF3C7"/><ellipse cx="106" cy="70" rx="8" ry="3.5" fill="#FEF3C7"/>
  </g>
  <g transform="translate(274, 24)">
    <rect x="40" y="66" width="10" height="96" fill="#334155" stroke="#0F172A" stroke-width="2"/>
    <rect x="22" y="2" width="46" height="74" rx="10" fill="#0F172A" stroke="#F8F5EE" stroke-width="2"/>
    <circle cx="45" cy="24" r="13" fill="#EF4444" stroke="#FCA5A5" stroke-width="2.2"/>
    <circle cx="45" cy="54" r="10" fill="#334155"/>
    <rect x="-14" y="128" width="114" height="24" rx="3" fill="#0F172A"/>
    <text x="43" y="144" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="700" font-size="11" fill="#FDE047">PARIS ↔ LONDON</text>
  </g>
</svg>'''

    if kind == "riyadh":
        return '''<svg viewBox="0 0 382 192" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
  <rect width="382" height="192" fill="#F3D6B3"/>
  <rect x="0" y="0" width="382" height="66" fill="#D97706" opacity="0.32"/>
  <rect x="0" y="148" width="382" height="44" fill="#C49A6C"/>
  <g fill="#475569" stroke="#0F172A" stroke-width="1.6">
    <rect x="20" y="106" width="28" height="74"/><rect x="54" y="90" width="34" height="90"/><rect x="96" y="114" width="26" height="66"/>
    <rect x="262" y="104" width="30" height="76"/><rect x="298" y="88" width="36" height="92"/><rect x="340" y="112" width="28" height="68"/>
  </g>
  <g transform="translate(154, 16)">
    <path d="M8 164 L14 8 C14 2 62 2 62 8 L68 164 Z" fill="#1E293B" stroke="#0F172A" stroke-width="2.4"/>
    <path d="M24 22 C24 42 52 42 52 22 L52 14 L24 14 Z" fill="#F3D6B3" stroke="#0F172A" stroke-width="1.8"/>
    <line x1="26" y1="46" x2="24" y2="160" stroke="#93C5FD" stroke-width="1.4" opacity="0.7"/>
    <line x1="38" y1="46" x2="38" y2="160" stroke="#93C5FD" stroke-width="1.4" opacity="0.7"/>
    <line x1="50" y1="46" x2="52" y2="160" stroke="#93C5FD" stroke-width="1.4" opacity="0.7"/>
  </g>
  <path d="M16 138 Q88 30 186 72" fill="none" stroke="#B91C1C" stroke-width="3.2" stroke-dasharray="7 5"/>
  <path d="M356 146 Q282 50 218 64" fill="none" stroke="#1D4ED8" stroke-width="2.6" stroke-dasharray="5 4"/>
  <circle cx="206" cy="70" r="17" fill="#334155" opacity="0.85"/><circle cx="228" cy="60" r="21" fill="#475569" opacity="0.75"/>
  <circle cx="256" cy="50" r="24" fill="#64748B" opacity="0.60"/><circle cx="288" cy="44" r="20" fill="#94A3B8" opacity="0.45"/>
  <polygon points="194,48 201,63 218,60 205,72 215,88 198,80 186,92 189,75 174,69 190,64" fill="#DC2626" stroke="#0F172A" stroke-width="1.6"/>
  <polygon points="195,58 199,66 208,65 201,72 205,80 196,76 190,81 192,72 184,69 192,66" fill="#FDE047"/>
  <rect x="12" y="156" width="136" height="24" rx="3" fill="#0F172A"/>
  <text x="80" y="172" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="700" font-size="11.5" fill="#FCA5A5">RIYADH · 2ND HIT</text>
</svg>'''

    if kind == "cyber":
        return '''<svg viewBox="0 0 382 192" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
  <rect width="382" height="192" fill="#0E141F"/>
  <g font-family="IBMPlexMono, monospace" font-size="10.5" fill="#1E293B" font-weight="700">
    <text x="12" y="22">01001101 10110010 00111010 11010101 01011001</text>
    <text x="12" y="182">ERR_AUTH_BYPASS // ODNI_CIA // CODE_RED</text>
  </g>
  <g transform="translate(26, 28)">
    <path d="M52 4 L102 22 L102 72 C102 108 52 132 52 132 C52 132 2 108 2 72 L2 22 Z" fill="#1E3A8A" stroke="#93C5FD" stroke-width="2.5"/>
    <circle cx="52" cy="58" r="13" fill="#F8F5EE"/><polygon points="44,68 60,68 64,96 40,96" fill="#F8F5EE"/>
    <polyline points="64,12 42,40 66,62 34,90 58,124" fill="none" stroke="#EF4444" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
    <polyline points="64,12 42,40 66,62 34,90 58,124" fill="none" stroke="#FCA5A5" stroke-width="1.8" stroke-linecap="round"/>
  </g>
  <g transform="translate(154, 30)">
    <rect x="0" y="0" width="210" height="134" rx="6" fill="#182234" stroke="#475569" stroke-width="2"/>
    <rect x="0" y="0" width="210" height="24" rx="6" fill="#334155"/>
    <circle cx="15" cy="12" r="4" fill="#EF4444"/><circle cx="28" cy="12" r="4" fill="#F59E0B"/><circle cx="41" cy="12" r="4" fill="#22C55E"/>
    <rect x="14" y="34" width="182" height="36" rx="4" fill="#B91C1C"/>
    <text x="105" y="59" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="22" fill="#FFFFFF" letter-spacing="1.4">CODE RED</text>
    <g transform="translate(16, 82)">
      <rect x="0" y="0" width="13" height="13" fill="#EF4444"/><rect x="16" y="0" width="13" height="13" fill="#22C55E"/>
      <rect x="0" y="16" width="13" height="13" fill="#3B82F6"/><rect x="16" y="16" width="13" height="13" fill="#F59E0B"/>
    </g>
    <text x="58" y="94" font-family="IBMPlexMono, monospace" font-weight="700" font-size="12.5" fill="#FCA5A5">MSFT OUTAGE</text>
    <text x="58" y="111" font-family="IBMPlexMono, monospace" font-weight="600" font-size="12" fill="#93C5FD">CIA / ODNI HACK</text>
  </g>
</svg>'''

    if kind == "ebola":
        return '''<svg viewBox="0 0 382 192" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
  <rect width="382" height="192" fill="#E8E4D4"/>
  <path d="M0 104 Q86 58 190 88 T382 80 L382 192 L0 192 Z" fill="#4D7C5A" opacity="0.45"/>
  <path d="M0 134 Q120 104 246 128 T382 120 L382 192 L0 192 Z" fill="#3F6B4E"/>
  <g transform="translate(36, 54)">
    <polygon points="0,46 92,8 184,46" fill="#0F766E" stroke="#0F172A" stroke-width="2.4"/>
    <rect x="12" y="46" width="160" height="64" fill="#F8F5EE" stroke="#0F172A" stroke-width="2.4"/>
    <path d="M72 110 L72 68 Q92 58 112 68 L112 110 Z" fill="#1E293B" stroke="#0F172A" stroke-width="2"/>
    <rect x="26" y="66" width="26" height="9" fill="#B91C1C"/><rect x="34.5" y="57.5" width="9" height="26" fill="#B91C1C"/>
    <text x="144" y="84" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="18" fill="#0F766E">WHO</text>
  </g>
  <g transform="translate(18, 162)">
    <rect x="0" y="0" width="224" height="16" rx="2" fill="#B91C1C" stroke="#0F172A" stroke-width="2"/>
    <polygon points="18,0 32,0 24,16 10,16" fill="#FDE047"/><polygon points="54,0 68,0 60,16 46,16" fill="#FDE047"/>
    <polygon points="90,0 104,0 96,16 82,16" fill="#FDE047"/><polygon points="126,0 140,0 132,16 118,16" fill="#FDE047"/>
    <polygon points="162,0 176,0 168,16 154,16" fill="#FDE047"/><polygon points="198,0 212,0 204,16 190,16" fill="#FDE047"/>
  </g>
  <g transform="translate(274, 34)">
    <path d="M42 0 L84 16 L84 62 C84 96 42 118 42 118 C42 118 0 96 0 62 L0 16 Z" fill="#0F766E" stroke="#0F172A" stroke-width="2.4"/>
    <rect x="28" y="22" width="28" height="9" rx="2" fill="#D97706" stroke="#0F172A" stroke-width="1.6"/>
    <rect x="24" y="31" width="36" height="54" rx="4" fill="#F8F5EE" stroke="#0F172A" stroke-width="1.8"/>
    <rect x="24" y="50" width="36" height="22" fill="#5EEAD4"/>
    <text x="42" y="66" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="13.5" fill="#0F172A">1.5M</text>
    <text x="42" y="100" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="700" font-size="10" fill="#FFFFFF">GAVI</text>
  </g>
  <rect x="266" y="158" width="104" height="22" rx="3" fill="#0F172A"/>
  <text x="318" y="173" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="700" font-size="11" fill="#FDE047">ITURI · DRC</text>
</svg>'''

    if kind == "pacific":
        return '''<svg viewBox="0 0 382 192" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
  <rect width="382" height="192" fill="#154C79"/>
  <g stroke="#38BDF8" stroke-width="1" opacity="0.28">
    <line x1="0" y1="48" x2="382" y2="48"/><line x1="0" y1="96" x2="382" y2="96"/><line x1="0" y1="144" x2="382" y2="144"/>
    <line x1="95" y1="0" x2="95" y2="192"/><line x1="191" y1="0" x2="191" y2="192"/><line x1="287" y1="0" x2="287" y2="192"/>
  </g>
  <path d="M20 134 L46 102 L92 92 L124 76 L146 98 L166 138 L150 172 L110 178 L74 166 L32 170 Z" fill="#D4A359" stroke="#0F172A" stroke-width="2.4"/>
  <text x="94" y="144" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="13.5" fill="#0F172A" letter-spacing="1">AUSTRALIA</text>
  <g fill="#4ADE80" stroke="#0F172A" stroke-width="1.8">
    <ellipse cx="268" cy="54" rx="17" ry="7" transform="rotate(24 268 54)"/>
    <ellipse cx="298" cy="68" rx="20" ry="8" transform="rotate(28 298 68)"/>
    <ellipse cx="328" cy="84" rx="17" ry="7" transform="rotate(24 328 84)"/>
  </g>
  <text x="322" y="112" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="11.5" fill="#F8F5EE">SOLOMON IS.</text>
  <path d="M140 104 Q206 54 280 66" fill="none" stroke="#FDE047" stroke-width="3.6" stroke-dasharray="7 5"/>
  <circle cx="140" cy="104" r="5.5" fill="#FDE047" stroke="#0F172A" stroke-width="2"/>
  <circle cx="282" cy="66" r="5.5" fill="#FDE047" stroke="#0F172A" stroke-width="2"/>
  <g transform="translate(200, 82)">
    <path d="M42 0 L84 14 L84 52 C84 80 42 98 42 98 C42 98 0 80 0 52 L0 14 Z" fill="#F8F5EE" stroke="#0F172A" stroke-width="2.4"/>
    <path d="M42 7 L76 19 L76 50 C76 72 42 88 42 88 C42 88 8 72 8 50 L8 19 Z" fill="#1D4ED8"/>
    <polygon points="42,18 47,32 62,32 50,41 55,55 42,46 29,55 34,41 22,32 37,32" fill="#FDE047"/>
    <text x="42" y="72" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="700" font-size="9.5" fill="#FFFFFF">TREATY</text>
  </g>
</svg>'''

    if kind == "cricket":
        # Clean FT/Economist geometric cricket graphic (no cartoon person): geometric wickets, willow bat silhouette, soaring ball arc & scoreboard
        return '''<svg viewBox="0 0 382 192" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
  <rect width="382" height="192" fill="#1E1B4B"/>
  <polygon points="34,10 156,136 0,136" fill="#A78BFA" opacity="0.14"/>
  <polygon points="348,10 382,136 226,136" fill="#A78BFA" opacity="0.14"/>
  <rect x="0" y="130" width="382" height="62" fill="#15803D"/>
  <rect x="0" y="148" width="382" height="44" fill="#166534"/>
  <polygon points="36,192 98,132 162,132 126,192" fill="#E6D3A3" stroke="#B45309" stroke-width="1.4"/>
  <!-- Crisp geometric cricket stumps & bails -->
  <g stroke="#FDE68A" stroke-width="4" stroke-linecap="round">
    <line x1="68" y1="108" x2="68" y2="168"/><line x1="80" y1="108" x2="80" y2="168"/><line x1="92" y1="108" x2="92" y2="168"/>
  </g>
  <line x1="65" y1="107" x2="95" y2="107" stroke="#D97706" stroke-width="3.5" stroke-linecap="round"/>
  <!-- Geometric diagonal willow cricket bat -->
  <g transform="translate(148, 126) rotate(-32)">
    <rect x="-11" y="-66" width="22" height="72" rx="3" fill="#F5D08A" stroke="#0F172A" stroke-width="2.4"/>
    <line x1="0" y1="-64" x2="0" y2="4" stroke="#B45309" stroke-width="1.8"/>
    <rect x="-4" y="6" width="8" height="28" rx="2" fill="#1D4ED8" stroke="#0F172A" stroke-width="2"/>
  </g>
  <!-- Soaring sixes trajectory + crimson seam ball -->
  <path d="M120 68 Q186 10 264 38" fill="none" stroke="#FDE047" stroke-width="3.4" stroke-dasharray="6 4"/>
  <circle cx="272" cy="40" r="12" fill="#DC2626" stroke="#FFFFFF" stroke-width="2"/>
  <path d="M263 36 Q272 42 281 36" fill="none" stroke="#FFFFFF" stroke-width="1.6"/>
  <!-- Stadium Scoreboard -->
  <g transform="translate(212, 62)">
    <rect x="0" y="0" width="156" height="106" rx="6" fill="#0F172A" stroke="#A78BFA" stroke-width="2.4"/>
    <rect x="8" y="8" width="140" height="22" rx="3" fill="#6D28D9"/>
    <text x="78" y="23" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="13" fill="#FFFFFF">INDIA A vs UAE</text>
    <text x="78" y="64" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="36" fill="#FDE047">204</text>
    <text x="78" y="83" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="700" font-size="13.5" fill="#E9D5FF">53 BALLS · 28×6s</text>
    <text x="78" y="99" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="600" font-size="10.5" fill="#86EFAC">AGE 15 WORLD REC</text>
  </g>
</svg>'''

    if kind == "xi_probe":
        # 11. Xi Probes Shanghai Boss: Red-lacquered Great Hall colonnade, geometric Pudong skyline, crimson anti-corruption seal
        return '''<svg viewBox="0 0 382 192" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
  <rect width="382" height="192" fill="#2A1215"/>
  <rect x="0" y="142" width="382" height="50" fill="#180A0C"/>
  <!-- Geometric Great Hall / Zhongnanhai colonnade backdrop -->
  <g fill="#7F1D1D" stroke="#0F172A" stroke-width="1.6">
    <rect x="14" y="34" width="20" height="110"/><rect x="52" y="34" width="20" height="110"/>
    <rect x="90" y="34" width="20" height="110"/><rect x="128" y="34" width="20" height="110"/>
  </g>
  <rect x="6" y="22" width="152" height="16" fill="#B91C1C" stroke="#FDE047" stroke-width="1.4"/>
  <!-- Stylized Shanghai Pudong geometric towers (right) -->
  <g fill="#334155" stroke="#0F172A" stroke-width="1.8">
    <rect x="266" y="76" width="24" height="70"/>
    <polygon points="296,146 306,40 318,40 328,146" fill="#475569"/>
    <rect x="334" y="64" width="26" height="82"/>
  </g>
  <!-- Oriental Pearl geometric silhouette -->
  <line x1="238" y1="36" x2="238" y2="146" stroke="#CBD5E1" stroke-width="4"/>
  <circle cx="238" cy="112" r="14" fill="#94A3B8" stroke="#0F172A" stroke-width="2"/>
  <circle cx="238" cy="68" r="10" fill="#94A3B8" stroke="#0F172A" stroke-width="2"/>
  <circle cx="238" cy="40" r="4" fill="#FDE047"/>
  <!-- Anti-corruption Dossier & Magnifier / Red Stamp (center) -->
  <g transform="translate(116, 48)">
    <rect x="0" y="0" width="118" height="122" rx="4" fill="#F8F5EE" stroke="#0F172A" stroke-width="2.4"/>
    <rect x="12" y="14" width="94" height="12" fill="#B91C1C"/>
    <line x1="12" y1="40" x2="96" y2="40" stroke="#64748B" stroke-width="3.5"/>
    <line x1="12" y1="54" x2="84" y2="54" stroke="#94A3B8" stroke-width="3.5"/>
    <line x1="12" y1="68" x2="90" y2="68" stroke="#94A3B8" stroke-width="3.5"/>
    <!-- Red official investigation seal -->
    <g transform="translate(66, 94) rotate(-12)">
      <rect x="-42" y="-15" width="84" height="30" rx="3" fill="#FEF2F2" stroke="#B91C1C" stroke-width="3"/>
      <text x="0" y="5" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="14" fill="#B91C1C" letter-spacing="0.8">PROBED</text>
    </g>
  </g>
  <rect x="248" y="156" width="122" height="24" rx="3" fill="#0F172A" stroke="#FDE047" stroke-width="1.2"/>
  <text x="309" y="172" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="700" font-size="11" fill="#FDE047">SHANGHAI · 2027</text>
</svg>'''

    if kind == "gold_drop":
        # 12. Gold Breaks Below $3,600: Geometric bullion stack, dashed $3,600 floor broken, crimson drop arrow & $3,552 badge
        return '''<svg viewBox="0 0 382 192" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
  <rect width="382" height="192" fill="#18181B"/>
  <g stroke="#27272A" stroke-width="1.2">
    <line x1="0" y1="46" x2="382" y2="46"/><line x1="0" y1="92" x2="382" y2="92"/><line x1="0" y1="138" x2="382" y2="138"/>
  </g>
  <!-- $3,600 Support Line Broken -->
  <line x1="14" y1="76" x2="368" y2="76" stroke="#FDE047" stroke-width="2" stroke-dasharray="7 5"/>
  <text x="20" y="68" font-family="IBMPlexMono, monospace" font-weight="700" font-size="11.5" fill="#FDE047">$3,600 SUPPORT BROKEN</text>
  <!-- Geometric Gold Bullion Stack (left) -->
  <g transform="translate(22, 92)">
    <polygon points="8,66 22,38 92,38 106,66" fill="#D97706" stroke="#0F172A" stroke-width="2"/>
    <polygon points="22,38 92,38 82,50 32,50" fill="#FDE047"/>
    <polygon points="108,66 122,38 192,38 206,66" fill="#B45309" stroke="#0F172A" stroke-width="2"/>
    <polygon points="122,38 192,38 182,50 132,50" fill="#FBBF24"/>
    <polygon points="58,38 72,10 142,10 156,38" fill="#F59E0B" stroke="#0F172A" stroke-width="2"/>
    <polygon points="72,10 142,10 132,22 82,22" fill="#FEF08A"/>
    <text x="107" y="33" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="12" fill="#0F172A">999.9 AU</text>
  </g>
  <!-- Sharp Crimson Plunge Trajectory -->
  <polyline points="226,48 264,66 292,104 334,132" fill="none" stroke="#EF4444" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>
  <polygon points="348,140 324,138 334,120" fill="#EF4444"/>
  <!-- Price Readout Card -->
  <rect x="218" y="146" width="152" height="36" rx="4" fill="#B91C1C" stroke="#FCA5A5" stroke-width="1.6"/>
  <text x="294" y="164" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="16" fill="#FFFFFF">AU $3,552</text>
  <text x="294" y="177" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="700" font-size="10" fill="#FEE2E2">AG -5.22% · BRENT $90</text>
</svg>'''

    # 13. UN Nov 25 Femicide Alert: UN diplomatic blue backdrop, olive wreath arc, stark geometric memorial clock "5 / HOUR" & crimson 25 NOV ribbon
    return '''<svg viewBox="0 0 382 192" width="100%" height="100%" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
  <rect width="382" height="192" fill="#163A5F"/>
  <!-- Concentric UN globe rings -->
  <g fill="none" stroke="#60A5FA" stroke-width="1.4" opacity="0.35">
    <circle cx="118" cy="100" r="70"/><circle cx="118" cy="100" r="48"/><circle cx="118" cy="100" r="26"/>
    <line x1="48" y1="100" x2="188" y2="100"/><line x1="118" y1="30" x2="118" y2="170"/>
  </g>
  <!-- Memorial Clock Dial (5 women / hour) -->
  <g transform="translate(118, 100)">
    <circle cx="0" cy="0" r="54" fill="#F8F5EE" stroke="#0F172A" stroke-width="3"/>
    <path d="M0 0 L0 -46 A46 46 0 0 1 40 -23 Z" fill="#B91C1C" opacity="0.88"/>
    <line x1="0" y1="0" x2="0" y2="-36" stroke="#0F172A" stroke-width="3.6" stroke-linecap="round"/>
    <line x1="0" y1="0" x2="28" y2="-16" stroke="#B91C1C" stroke-width="3.2" stroke-linecap="round"/>
    <circle cx="0" cy="0" r="5" fill="#0F172A"/>
    <text x="0" y="28" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="14" fill="#B91C1C">5 / HOUR</text>
  </g>
  <!-- Right: UNODC / UN Women Stark Editorial Data Panel -->
  <g transform="translate(198, 34)">
    <rect x="0" y="0" width="166" height="128" rx="5" fill="#0F172A" stroke="#93C5FD" stroke-width="2"/>
    <rect x="0" y="0" width="166" height="28" rx="5" fill="#B91C1C"/>
    <text x="83" y="19" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="13.5" fill="#FFFFFF" letter-spacing="0.8">UN · 25 NOV ALERT</text>
    <text x="83" y="68" text-anchor="middle" font-family="Barlow, sans-serif" font-weight="800" font-size="36" fill="#F8F5EE">47,000</text>
    <text x="83" y="88" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="700" font-size="11.5" fill="#FCA5A5">KILLED IN 2025</text>
    <line x1="16" y1="98" x2="150" y2="98" stroke="#334155" stroke-width="1.4"/>
    <text x="83" y="116" text-anchor="middle" font-family="IBMPlexMono, monospace" font-weight="600" font-size="10.5" fill="#93C5FD">UNODC / UN WOMEN</text>
  </g>
</svg>'''


# ---------------------------------------------------------------------------
# Compact Natural Earth 110m World Map (Bottom-Left: 688 x 436, ONLY Pins 1-13)
# ---------------------------------------------------------------------------
def ne_project_raw(lat_deg: float, lon_deg: float) -> Tuple[float, float]:
    phi = math.radians(max(-89.9, min(89.9, lat_deg)))
    lam = math.radians(lon_deg)
    phi2 = phi * phi
    phi4 = phi2 * phi2
    l_val = 0.870700 - 0.131979 * phi2 - 0.013791 * phi4 + 0.003971 * (phi4 * phi4 * phi2) - 0.001529 * (phi4 * phi4 * phi4)
    d_val = phi * (1.007226 + 0.015085 * phi2 - 0.044475 * (phi4 * phi2) + 0.028874 * (phi4 * phi4) - 0.005916 * (phi4 * phi4 * phi2))
    return (l_val * lam, -d_val)


MAP_W = 688.0
MAP_H = 382.0
LON_MIN, LON_MAX = -165.0, 179.0
LAT_MIN, LAT_MAX = -54.0, 74.0

_X_MIN = ne_project_raw(0.0, LON_MIN)[0]
_X_MAX = ne_project_raw(0.0, LON_MAX)[0]
_Y_TOP = ne_project_raw(LAT_MAX, 0.0)[1]
_Y_BOT = ne_project_raw(LAT_MIN, 0.0)[1]

PAD_X = 8.0
PAD_Y = 10.0
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
        lat = max(LAT_MIN - 2, min(LAT_MAX + 3, lat))
        if prev_lon is not None and abs(lon - prev_lon) > 180:
            continue
        prev_lon = lon
        x, y = project(lat, lon)
        pts.append(f"{x:.1f},{y:.1f}")
    return "M" + "L".join(pts) + "Z" if len(pts) >= 3 else ""


def build_map_svg() -> str:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        gj = json.load(f)

    globe_pts = (
        [project(lat, -180.0) for lat in range(int(LAT_MIN), int(LAT_MAX) + 1, 3)]
        + [project(LAT_MAX, lon) for lon in range(-180, 181, 6)]
        + [project(lat, 180.0) for lat in range(int(LAT_MAX), int(LAT_MIN) - 1, -3)]
        + [project(LAT_MIN, lon) for lon in range(180, -181, -6)]
    )
    globe_d = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in globe_pts) + "Z"

    grat_paths = []
    for lat in (-30, 0, 30, 60):
        pts = [project(lat, lon) for lon in range(-180, 181, 6)]
        d = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        grat_paths.append(f'<path d="{d}" class="{"grat-eq" if lat == 0 else "grat"}"/>')
    for lon in (-120, -60, 0, 60, 120):
        pts = [project(lat, lon) for lat in range(int(LAT_MIN), int(LAT_MAX) + 1, 4)]
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

    # Clean continent watermarks safely away from pins 1-13 (EUROPE unclipped!)
    cont_labels = [
        ("N. AMERICA", 59.0, -98.0),
        ("S. AMERICA", -18.0, -58.0),
        ("EUROPE", 63.0, 26.0),
        ("AFRICA", 14.0, 10.0),
        ("ASIA", 60.0, 88.0),
        ("OCEANIA", -26.0, 134.0),
    ]
    cont_svg = [
        f'<text x="{project(la, lo)[0]:.1f}" y="{project(la, lo)[1]:.1f}" class="cont-lbl">{html.escape(lb)}</text>'
        for lb, la, lo in cont_labels
    ]

    # Plot ONLY Pins 1-13 (3 Lead Cards + 10 Secondary Cards)
    pin_items = []
    for item in LEADS:
        pin_items.append((item["pin"], item["continent"], item["lat"], item["lon"], True))
    for item in SECONDARY:
        pin_items.append((item["pin"], item["continent"], item["lat"], item["lon"], False))

    # Curated callout hints for clean zero-overlap placement (zero overlap with labels)
    hints: Dict[int, Tuple[float, float]] = {
        1: (-18.0, -8.0),    # Jiuquan
        2: (22.0, -14.0),    # Seoul
        3: (-12.0, 20.0),    # Washington DC
        4: (-26.0, -18.0),   # UK Energy
        5: (-22.0, 14.0),    # Eurostar
        6: (-14.0, 18.0),    # Riyadh
        7: (-16.0, 10.0),    # Redmond/Cyber
        8: (0.0, 10.0),      # DRC Ituri
        9: (6.0, 0.0),       # Solomons
        10: (24.0, 12.0),    # UAE Cricket
        11: (22.0, 16.0),    # Shanghai
        12: (24.0, -14.0),   # NYC Gold
        13: (16.0, 12.0),    # Vienna UN (below EUROPE label)
    }

    nodes = []
    for pin, cont, lat, lon, is_lead in pin_items:
        ax, ay = project(lat, lon)
        dx, dy = hints.get(pin, (0.0, 0.0))
        r = 15.5 if is_lead else 13.5
        nodes.append({
            "pin": pin, "cont": cont, "ax": ax, "ay": ay,
            "x": ax + dx, "y": ay + dy, "tx": ax + dx, "ty": ay + dy,
            "r": r, "is_lead": is_lead,
        })

    pad_x, pad_y = 22.0, 26.0
    for _ in range(400):
        moved = False
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                ni, nj = nodes[i], nodes[j]
                dx, dy = nj["x"] - ni["x"], nj["y"] - ni["y"]
                dist = math.hypot(dx, dy)
                min_d = ni["r"] + nj["r"] + 7.0
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

    min_gap = min(
        math.hypot(nodes[j]["x"] - nodes[i]["x"], nodes[j]["y"] - nodes[i]["y"]) - (nodes[i]["r"] + nodes[j]["r"])
        for i in range(len(nodes)) for j in range(i + 1, len(nodes))
    )
    print(f"[map] 13 scene pins laid out; min edge-to-edge gap = {min_gap:.2f}px")
    assert min_gap >= 4.0, f"Pin collision: min_gap={min_gap:.2f}"

    leaders, anchors, badges = [], [], []
    for n in sorted(nodes, key=lambda item: (item["is_lead"], item["pin"])):
        col = "#B91C1C" if n["is_lead"] else CONT_COLORS[n["cont"]]
        ax, ay, bx, by, r = n["ax"], n["ay"], n["x"], n["y"], n["r"]
        if math.hypot(bx - ax, by - ay) > 5.0:
            leaders.append(
                f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="#F8F5EE" stroke-width="4" stroke-linecap="round" opacity="0.9"/>'
                f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{col}" stroke-width="2" stroke-linecap="round"/>'
            )
            anchors.append(f'<circle cx="{ax:.1f}" cy="{ay:.1f}" r="3.8" fill="{col}" stroke="#F8F5EE" stroke-width="1.6"/>')
        if n["is_lead"]:
            badges.append(
                f'<g><circle cx="{bx:.1f}" cy="{by:.1f}" r="{r + 3.0:.1f}" fill="#F8F5EE"/>'
                f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{r:.1f}" fill="#B91C1C" stroke="#0F172A" stroke-width="2.2"/>'
                f'<text x="{bx:.1f}" y="{by + 0.8:.1f}" class="pin-num pin-lead">{n["pin"]}</text></g>'
            )
        else:
            badges.append(
                f'<g><circle cx="{bx:.1f}" cy="{by:.1f}" r="{r + 2.2:.1f}" fill="#F8F5EE"/>'
                f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{r:.1f}" fill="{col}"/>'
                f'<text x="{bx:.1f}" y="{by + 0.7:.1f}" class="pin-num">{n["pin"]}</text></g>'
            )

    return f'''<svg viewBox="0 0 {int(MAP_W)} {int(MAP_H)}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
  <defs><clipPath id="globeClip"><path d="{globe_d}"/></clipPath></defs>
  <rect width="{int(MAP_W)}" height="{int(MAP_H)}" fill="#F2EDE3"/>
  <path d="{globe_d}" fill="#E6E0D3" stroke="#B4AC9C" stroke-width="1.4"/>
  <g clip-path="url(#globeClip)">{"".join(grat_paths)}{"".join(country_paths)}{"".join(cont_svg)}</g>
  <path d="{globe_d}" fill="none" stroke="#9B9384" stroke-width="1.4"/>
  <g>{"".join(leaders)}</g><g>{"".join(anchors)}</g><g>{"".join(badges)}</g>
</svg>'''


def find_font_uri(filename: str) -> str:
    for p in (
        Path("C:/Windows/Fonts") / filename,
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Windows/Fonts" / filename,
    ):
        if p.exists():
            return p.resolve().as_uri()
    raise FileNotFoundError(f"Font not found: {filename}")


def try_font_uri(filename: str) -> str | None:
    try:
        return find_font_uri(filename)
    except FileNotFoundError:
        return None


def build_html() -> str:
    italic_uri = try_font_uri("LibreBaskerville-Italic.ttf")
    italic_face = (
        f"@font-face {{ font-family: 'LibreBask'; font-weight: 400; font-style: italic; src: url('{italic_uri}'); }}"
        if italic_uri else ""
    )
    fonts_css = f"""
    @font-face {{ font-family: 'LibreBask'; font-weight: 400; src: url('{find_font_uri("LibreBaskerville-Regular.ttf")}'); }}
    @font-face {{ font-family: 'LibreBask'; font-weight: 700; src: url('{find_font_uri("LibreBaskerville-Bold.ttf")}'); }}
    {italic_face}
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

    kpi_html = "".join(
        f'<div class="kpi-box"><span class="kpi-val" style="color:{col};">{html.escape(val)}</span>'
        f'<span class="kpi-lbl">{html.escape(lbl)}</span></div>'
        for val, lbl, col in KPIS
    )

    total_stories = sum(c for _, c in CONT_COUNTS)
    assert total_stories == 38
    cont_bar_segs = "".join(
        f'<span style="width:{(cnt / total_stories) * 100:.2f}%;background:{CONT_COLORS[name]};"></span>'
        for name, cnt in CONT_COUNTS
    )
    cont_bar_lbls = " · ".join(
        f'<span class="cb-item"><span class="cb-dot" style="background:{CONT_COLORS[name]};"></span>{name} {cnt}</span>'
        for name, cnt in CONT_COUNTS
    )

    leads_html = []
    for item in LEADS:
        st_cls = "st-official" if item["status"] == "OFFICIAL" else "st-reported"
        leads_html.append(f'''
        <article class="lead-card">
          <div class="lead-top">
            <div class="lead-top-l">
              <span class="num-badge-lead">{item["pin"]}</span>
              <span class="lead-kicker">{html.escape(item["kicker"])}</span>
            </div>
            <span class="status-tag {st_cls}">{item["status"]}</span>
          </div>
          <div class="lead-art">{render_scene_svg(item["scene"])}</div>
          <div class="lead-body">
            <h2 class="lead-hl">{html.escape(item["headline"])}</h2>
            <p class="lead-sum">{html.escape(item["summary"])}</p>
            <div class="lead-why"><span class="why-lbl">WHY IT MATTERS:</span> {html.escape(item["why"])}</div>
          </div>
        </article>''')

    sec_html = []
    for item in SECONDARY:
        col = CONT_COLORS[item["continent"]]
        st_cls = "st-official" if item["status"] == "OFFICIAL" else "st-reported"
        sec_html.append(f'''
        <article class="sec-card" style="border-top-color:{col};">
          <div class="sec-art">
            {render_scene_svg(item["scene"])}
            <span class="sec-pin" style="background:{col};">{item["pin"]}</span>
            <span class="sec-stat">{html.escape(item["stat"])}</span>
          </div>
          <div class="sec-body">
            <h3 class="sec-title">{html.escape(item["title"])}</h3>
            <p class="sec-fact">{html.escape(item["fact"])}</p>
            <div class="sec-foot">
              <span class="sec-src">{html.escape(item["source"])}</span>
              <span class="status-tag status-sm {st_cls}">{item["status"]}</span>
            </div>
          </div>
        </article>''')

    def render_brief_col(items: List[Tuple[int, str, str, str, str]]) -> str:
        out = []
        for pin, cont, prefix, body, src in items:
            col = CONT_COLORS[cont]
            out.append(
                f'<div class="b-row">'
                f'<span class="b-pin" style="background:{col};">{pin}</span>'
                f'<span class="b-txt"><strong class="b-pre">{html.escape(prefix)}:</strong> '
                f'{html.escape(body)} <span class="b-src">({html.escape(src)})</span></span>'
                f'</div>'
            )
        return "".join(out)

    brief_left = render_brief_col(BRIEFS[:13])   # #14-#26 (13 items)
    brief_right = render_brief_col(BRIEFS[13:])  # #27-#38 (12 items)

    map_legend = "".join(
        f'<span class="ml-item"><span class="ml-dot" style="background:{CONT_COLORS[name]};"></span>{name.replace("OCEANIA & GLOBAL", "OCEANIA/GLB")} ({cnt})</span>'
        for name, cnt in CONT_COUNTS
    )

    map_svg = build_map_svg()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Wednesday 25 November 2026 — Global Dispatch</title>
<style>
{fonts_css}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{
  width: 2048px; height: 2048px; overflow: hidden;
  background: #F8F5EE; color: #0F172A;
  font-family: 'Barlow', sans-serif;
  -webkit-font-smoothing: antialiased;
  text-rendering: geometricPrecision;
}}
.page {{
  width: 2048px; height: 2048px;
  padding: 14px 28px 14px 28px;
  display: flex; flex-direction: column;
  background: #F8F5EE;
}}

/* 1. TOP HEADER (~224px, ~11%) */
.header {{ display: flex; flex-direction: column; flex-shrink: 0; }}
.navy-banner {{
  height: 28px; background: #0F172A; color: #F8F5EE;
  display: flex; align-items: center; justify-content: center;
  font-family: 'IBMPlexMono', monospace; font-size: 14px; font-weight: 700;
  letter-spacing: 0.14em;
}}
.mast-main {{
  display: flex; flex-direction: column; align-items: center;
  padding: 5px 0 4px 0;
  border-bottom: 2px solid #0F172A;
}}
.mast-title {{
  font-family: 'LibreBask', Georgia, serif;
  font-size: 52px; font-weight: 700; line-height: 1.04;
  letter-spacing: -0.015em; color: #0F172A;
}}
.mast-sub {{
  font-family: 'LibreBask', Georgia, serif; font-style: italic;
  font-size: 18px; color: #B91C1C; margin-top: 2px;
  letter-spacing: 0.01em;
}}
.kpi-strip {{
  display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px;
  margin-top: 7px;
}}
.kpi-box {{
  background: #FFFFFF; border: 1.5px solid #D4CCBD; border-top: 3px solid #0F172A;
  padding: 4px 8px; display: flex; align-items: baseline; gap: 8px; min-width: 0;
}}
.kpi-val {{
  font-family: 'Barlow', sans-serif; font-variant-numeric: tabular-nums;
  font-size: 26px; font-weight: 800; line-height: 1.05; flex-shrink: 0;
}}
.kpi-lbl {{
  font-family: 'OpenSansSemi', sans-serif; font-size: 14px; font-weight: 700;
  color: #334155; line-height: 1.12; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}}
.cont-prop {{
  margin-top: 6px; display: flex; flex-direction: column; gap: 3px;
}}
.cont-track {{
  height: 7px; display: flex; border-radius: 3px; overflow: hidden;
  border: 1px solid #C9C1B2;
}}
.cont-labels {{
  display: flex; justify-content: space-between; align-items: center;
  font-family: 'IBMPlexMono', monospace; font-size: 12.5px; font-weight: 700; color: #334155;
}}
.cb-item {{ display: inline-flex; align-items: center; gap: 5px; }}
.cb-dot {{ width: 9px; height: 9px; border-radius: 2px; display: inline-block; }}

/* 2. ROW 1 — 3 LARGE LEAD STORY CARDS (456px, ~22.6%) */
.leads-grid {{
  margin-top: 9px; height: 458px;
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px;
  flex-shrink: 0;
}}
.lead-card {{
  display: flex; flex-direction: column;
  background: #FFFFFF; border: 1.8px solid #0F172A; border-top: 5px solid #B91C1C;
  overflow: hidden; min-width: 0; min-height: 0;
}}
.lead-top {{
  height: 34px; padding: 0 10px;
  background: #F2EDE3; border-bottom: 1.5px solid #D4CCBD;
  display: flex; align-items: center; justify-content: space-between;
  flex-shrink: 0;
}}
.lead-top-l {{ display: flex; align-items: center; gap: 8px; }}
.num-badge-lead {{
  display: inline-flex; align-items: center; justify-content: center;
  width: 24px; height: 24px; border-radius: 50%;
  background: #B91C1C; color: #FFFFFF;
  font-family: 'Barlow', sans-serif; font-size: 15px; font-weight: 800;
}}
.lead-kicker {{
  font-family: 'IBMPlexMono', monospace; font-size: 13px; font-weight: 700;
  color: #1E293B; letter-spacing: 0.05em;
}}
.status-tag {{
  font-family: 'IBMPlexMono', monospace; font-size: 11.5px; font-weight: 700;
  padding: 2px 7px; border-radius: 3px; letter-spacing: 0.05em; color: #FFFFFF;
}}
.status-sm {{ font-size: 10px; padding: 1px 5px; }}
.st-official {{ background: #0F172A; }}
.st-reported {{ background: #475569; }}
.lead-art {{
  height: 214px; width: 100%; flex-shrink: 0;
  border-bottom: 1.5px solid #0F172A; overflow: hidden; background: #0F172A;
}}
.lead-body {{
  flex: 1; padding: 9px 12px 9px 12px;
  display: flex; flex-direction: column; justify-content: space-between;
  min-height: 0;
}}
.lead-hl {{
  font-family: 'LibreBask', Georgia, serif; font-size: 21px; font-weight: 700;
  line-height: 1.18; color: #0F172A; letter-spacing: -0.01em;
  text-wrap: balance;
}}
.lead-sum {{
  font-family: 'OpenSansSemi', sans-serif; font-size: 16.5px; font-weight: 600;
  line-height: 1.24; color: #334155;
}}
.lead-why {{
  background: #FDF2F2; border-left: 4px solid #B91C1C;
  padding: 5px 8px; font-family: 'OpenSansSemi', sans-serif;
  font-size: 15.5px; font-weight: 600; line-height: 1.22; color: #1E293B;
}}
.why-lbl {{
  font-family: 'Barlow', sans-serif; font-weight: 800; color: #B91C1C;
  letter-spacing: 0.04em;
}}

/* 3. ROWS 2-3 — 10 SECONDARY ILLUSTRATED CARDS (644px, ~31.9%) */
.sec-grid {{
  margin-top: 10px; height: 644px;
  display: grid; grid-template-columns: repeat(5, 1fr); grid-template-rows: repeat(2, 1fr);
  gap: 10px; flex-shrink: 0;
}}
.sec-card {{
  display: flex; flex-direction: column;
  background: #FFFFFF; border: 1.5px solid #0F172A; border-top: 4px solid #0F172A;
  overflow: hidden; min-width: 0; min-height: 0;
}}
.sec-art {{
  position: relative; height: 174px; width: 100%; flex-shrink: 0;
  border-bottom: 1.5px solid #0F172A; overflow: hidden; background: #0F172A;
}}
.sec-pin {{
  position: absolute; top: 6px; left: 6px;
  display: inline-flex; align-items: center; justify-content: center;
  width: 26px; height: 26px; border-radius: 50%;
  color: #FFFFFF; font-family: 'Barlow', sans-serif; font-size: 15.5px; font-weight: 800;
  border: 2px solid #F8F5EE; box-shadow: 0 1px 3px rgba(0,0,0,0.45);
}}
.sec-stat {{
  position: absolute; top: 6px; right: 6px;
  background: #0F172A; color: #FDE047;
  font-family: 'IBMPlexMono', monospace; font-size: 12px; font-weight: 700;
  padding: 2px 7px; border-radius: 3px; border: 1.2px solid #F8F5EE;
  letter-spacing: 0.04em;
}}
.sec-body {{
  flex: 1; padding: 6px 9px 6px 9px;
  display: flex; flex-direction: column; justify-content: space-between;
  min-height: 0;
}}
.sec-title {{
  font-family: 'Barlow', sans-serif; font-size: 20px; font-weight: 800;
  line-height: 1.1; color: #0F172A; letter-spacing: -0.01em;
  white-space: nowrap; overflow: hidden;
}}
.sec-fact {{
  font-family: 'OpenSansSemi', sans-serif; font-size: 15.5px; font-weight: 600;
  line-height: 1.22; color: #262C36;
}}
.sec-foot {{
  display: flex; justify-content: space-between; align-items: center; gap: 6px;
  border-top: 1px dotted #D4CCBD; padding-top: 4px;
}}
.sec-src {{
  font-family: 'IBMPlexMono', monospace; font-size: 11px; font-weight: 600;
  color: #475569; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}

/* 4. BOTTOM SPLIT SECTION (568px, ~28%) */
.bottom-split {{
  margin-top: 10px; height: 568px;
  display: grid; grid-template-columns: 692px 1fr; gap: 14px;
  flex-shrink: 0;
}}
.map-panel {{
  display: flex; flex-direction: column;
  background: #FFFFFF; border: 1.8px solid #0F172A; overflow: hidden;
}}
.panel-hdr {{
  height: 30px; padding: 0 10px;
  background: #0F172A; color: #F8F5EE;
  display: flex; align-items: center; justify-content: space-between;
  font-family: 'Barlow', sans-serif; font-size: 15px; font-weight: 800;
  letter-spacing: 0.07em; flex-shrink: 0;
}}
.panel-hdr-sub {{
  font-family: 'IBMPlexMono', monospace; font-size: 11.5px; font-weight: 600; color: #CBD5E1;
}}
.map-canvas {{ flex: 1; background: #F2EDE3; overflow: hidden; min-height: 0; }}
.map-canvas svg {{ display: block; width: 100%; height: 100%; }}
.land {{ fill: #D8D0BE; stroke: #857E70; stroke-width: 0.85; stroke-linejoin: round; }}
.grat {{ fill: none; stroke: #CBC3B4; stroke-width: 0.7; stroke-dasharray: 3 4; }}
.grat-eq {{ fill: none; stroke: #B2AA9A; stroke-width: 1.0; stroke-dasharray: 5 4; }}
.cont-lbl {{
  font-family: 'Barlow', sans-serif; font-size: 11.5px; font-weight: 800;
  letter-spacing: 0.16em; fill: #5F594D; fill-opacity: 0.68; text-anchor: middle;
}}
.pin-num {{
  font-family: 'Barlow', sans-serif; font-variant-numeric: tabular-nums;
  font-size: 15px; font-weight: 800; fill: #FFFFFF;
  text-anchor: middle; dominant-baseline: central;
}}
.pin-lead {{ font-size: 17px; }}
.map-legend {{
  padding: 6px 10px; background: #F2EDE3; border-top: 1.5px solid #D4CCBD;
  display: flex; flex-wrap: wrap; gap: 6px 10px; justify-content: space-between;
  font-family: 'IBMPlexMono', monospace; font-size: 11px; font-weight: 700; color: #1E293B;
  flex-shrink: 0;
}}
.ml-item {{ display: inline-flex; align-items: center; gap: 4px; }}
.ml-dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
.ml-note {{ width: 100%; font-size: 10.5px; color: #475569; border-top: 1px dotted #C4BBA9; padding-top: 3px; }}

/* Right: 25 More Stories (2 crisp columns) */
.brief-panel {{
  display: flex; flex-direction: column;
  background: #FFFFFF; border: 1.8px solid #0F172A; overflow: hidden;
}}
.brief-cols {{
  flex: 1; padding: 6px 12px 6px 12px;
  display: grid; grid-template-columns: 1fr 1fr; column-gap: 16px;
  min-height: 0;
}}
.brief-col {{
  display: flex; flex-direction: column; justify-content: space-between;
  min-width: 0;
}}
.b-row {{
  display: flex; align-items: flex-start; gap: 7px;
  padding: 3px 0; border-bottom: 1px dotted #D6CFC1;
  min-width: 0;
}}
.b-row:last-child {{ border-bottom: none; }}
.b-pin {{
  display: inline-flex; align-items: center; justify-content: center;
  width: 24px; height: 21px; border-radius: 4px; margin-top: 1px;
  color: #FFFFFF; font-family: 'Barlow', sans-serif; font-variant-numeric: tabular-nums;
  font-size: 13.5px; font-weight: 800; flex-shrink: 0;
}}
.b-txt {{
  font-family: 'OpenSansCond', sans-serif; font-size: 17.5px; font-weight: 600;
  line-height: 1.15; color: #171A20; letter-spacing: -0.005em;
}}
.b-pre {{ font-weight: 700; color: #0F172A; }}
.b-src {{ color: #64748B; font-size: 15px; font-weight: 600; }}

/* 5. BOTTOM STRICT DATE CHECK FOOTER (84px, ~4.2%) */
.date-footer {{
  margin-top: 9px; flex: 1; min-height: 76px;
  background: #FDF2F2; border: 2px solid #B91C1C; border-left: 8px solid #B91C1C;
  padding: 6px 14px;
  display: grid; grid-template-columns: 1fr 395px; gap: 16px; align-items: center;
}}
.df-main {{
  font-family: 'OpenSansSemi', sans-serif; font-size: 16.5px; font-weight: 600;
  line-height: 1.3; color: #1E293B;
}}
.df-pill {{
  display: inline-block; background: #B91C1C; color: #FFFFFF;
  font-family: 'Barlow', sans-serif; font-size: 15px; font-weight: 800;
  padding: 2px 9px; border-radius: 3px; letter-spacing: 0.06em; margin-right: 7px;
  vertical-align: 1px;
}}
.df-excl {{ color: #7F1D1D; font-weight: 700; }}
.df-right {{
  border-left: 1.5px solid #E5B4B4; padding-left: 14px;
  display: flex; flex-direction: column; gap: 5px;
  font-family: 'IBMPlexMono', monospace; font-size: 12.5px; font-weight: 700; color: #0F172A;
}}
.df-right-sub {{ color: #7F1D1D; font-size: 12px; }}
</style>
</head>
<body>
<div class="page">
  <!-- 1. TOP HEADER -->
  <header class="header">
    <div class="navy-banner">THE WORLD IN ONE DAY · GLOBAL DISPATCH · WIRES VERIFIED WED 25 NOV 2026 UTC</div>
    <div class="mast-main">
      <h1 class="mast-title">Wednesday 25 November 2026</h1>
      <div class="mast-sub">38 dated stories · 13 original vector scenes · 6 continents · strict source &amp; date verification</div>
    </div>
    <div class="kpi-strip">{kpi_html}</div>
    <div class="cont-prop">
      <div class="cont-track">{cont_bar_segs}</div>
      <div class="cont-labels">{cont_bar_lbls}</div>
    </div>
  </header>

  <!-- 2. ROW 1: 3 LEAD STORY CARDS -->
  <section class="leads-grid">{"".join(leads_html)}</section>

  <!-- 3. ROWS 2-3: 10 SECONDARY ILLUSTRATED CARDS -->
  <section class="sec-grid">{"".join(sec_html)}</section>

  <!-- 4. BOTTOM SPLIT: WORLD MAP (LEFT) + 25 MORE STORIES (RIGHT) -->
  <section class="bottom-split">
    <div class="map-panel">
      <div class="panel-hdr">
        <span>WHERE IT HAPPENED</span>
        <span class="panel-hdr-sub">PINS 1–13 · NATURAL EARTH 110m</span>
      </div>
      <div class="map-canvas">{map_svg}</div>
      <div class="map-legend">
        {map_legend}
        <div class="ml-note">Double-ring crimson 1–3 = Lead Stories · Colored 4–13 = Illustrated Secondary Scenes</div>
      </div>
    </div>
    <div class="brief-panel">
      <div class="panel-hdr">
        <span>ALSO ON WEDNESDAY 25 NOVEMBER: 25 MORE STORIES</span>
        <span class="panel-hdr-sub">#14–#38 · 6 CONTINENTS</span>
      </div>
      <div class="brief-cols">
        <div class="brief-col">{brief_left}</div>
        <div class="brief-col">{brief_right}</div>
      </div>
    </div>
  </section>

  <!-- 5. STRICT DATE CHECK FOOTER -->
  <footer class="date-footer">
    <div class="df-main">
      <span class="df-pill">DATE CHECK ✓</span>
      All 38 stories verified Wed 25 Nov 2026 UTC (wires read to 12:00 UTC; markets intraday/close).
      <span class="df-excl">Deliberately excluded earlier wires:</span>
      Huawei verdict (24 Nov), Senegal AFCON CAS ruling (24 Nov), Cartagena siege onset (24 Nov),
      Zaporizhzhia strike (24 Nov), Eskişehir crash (24 Nov), Quebec monarch oath (23 Nov).
    </div>
    <div class="df-right">
      <div>STATUS: OFFICIAL · REPORTED · ONGOING</div>
      <div class="df-right-sub">ORIGINAL VECTOR ART &amp; MAP DRAWN IN CODE</div>
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
          document.querySelectorAll('.lead-card, .sec-card, .brief-panel, .map-panel').forEach((el, idx) => {
            if (el.scrollHeight > el.clientHeight + 2) {
              issues.push({type: 'card-v-overflow', cls: el.className, idx, scrollH: el.scrollHeight, clientH: el.clientHeight});
            }
          });
          document.querySelectorAll('.sec-title, .kpi-lbl').forEach((el, idx) => {
            if (el.scrollWidth > el.clientWidth + 1) {
              issues.push({type: 'text-h-overflow', cls: el.className, idx, text: el.textContent, scrollW: el.scrollWidth, clientW: el.clientWidth});
            }
          });
          const pg = document.querySelector('.page');
          const df = document.querySelector('.date-footer').getBoundingClientRect();
          return {
            issues,
            pageScrollH: pg.scrollHeight,
            footerBottom: Math.round(df.bottom),
            fontsLoaded: Array.from(document.fonts).filter(f => f.status === 'loaded').length,
          };
        }""")
        print("[audit]", json.dumps(audit, indent=2))
        page.screenshot(path=str(RAW_PNG_PATH), clip={"x": 0, "y": 0, "width": 2048, "height": 2048})
        browser.close()

    img_2048 = Image.open(RAW_PNG_PATH).convert("RGB")
    assert img_2048.size == (2048, 2048), f"Unexpected raw size: {img_2048.size}"
    img_1024 = img_2048.resize((1024, 1024), Image.Resampling.LANCZOS)

    lossless_path = BUILD_DIR / "entry_v3_lossless.png"
    img_1024.save(lossless_path, format="PNG", optimize=True)
    oxipng.optimize(str(lossless_path), str(lossless_path), level=4, strip=oxipng.StripChunks.safe())
    lossless_size = lossless_path.stat().st_size
    print(f"[opt] Lossless 24-bit PNG + oxipng: {lossless_size:,} bytes ({lossless_size / 1024:.1f} KB)")

    best_path = None
    best_psnr = -1.0
    best_size = 0
    for qname, qmethod in (("mediancut", Image.Quantize.MEDIANCUT), ("fastoctree", Image.Quantize.FASTOCTREE)):
        cand_img = img_1024.quantize(colors=256, method=qmethod, dither=Image.Dither.NONE)
        cand_path = BUILD_DIR / f"entry_v3_{qname}.png"
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

    if shutil.which("magick"):
        for dflag, tag in (("+dither", "magick_nodither"), ("-dither FloydSteinberg", "magick_fs")):
            cand_path = BUILD_DIR / f"entry_v3_{tag}.png"
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

    # Write 4 QA zoomed crops from the final 1024x1024 entry.png for visual inspection
    final_im = Image.open(OUT_PNG_PATH).convert("RGB")
    final_im.crop((0, 0, 1024, 360)).save(BUILD_DIR / "qa_leads.png")
    final_im.crop((0, 340, 1024, 680)).save(BUILD_DIR / "qa_secondary.png")
    final_im.crop((0, 665, 380, 1024)).save(BUILD_DIR / "qa_map.png")
    final_im.crop((350, 665, 1024, 1024)).save(BUILD_DIR / "qa_briefs.png")
    print("[qa] Saved zoomed QA crops to tmp/qa_*.png")


if __name__ == "__main__":
    render_and_optimize()
