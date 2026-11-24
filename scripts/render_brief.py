#!/usr/bin/env python
"""Offline Scout brief presentation. No fetching, editorial decisions or delivery."""
from __future__ import annotations

import argparse
import base64
import binascii
from collections import Counter
from datetime import date
from html import escape
import ipaddress
import json
import math
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "brief.schema.json"
STATUS = {"draft": "草稿", "verified": "已核實（輸入標記）", "mixed": "核實程度不一", "unverified": "尚未核實"}
EVIDENCE = {"primary": "第一手來源", "reputable_secondary": "可信次級來源", "community_signal": "社群訊號", "unverified_lead": "待查線索", "mixed": "混合來源"}
ACTIONS = {"read": "延伸閱讀", "watch": "持續觀察", "verify": "補充查證", "park": "暫存備查", "ignore": "略過"}
SCORES = {"importance": "重要性", "user_interest_fit": "興趣契合", "freshness": "新鮮度", "evidence_confidence": "證據信心", "composite": "綜合"}


def safe_source_url(value: str) -> str:
    """Accept explicit HTTP(S) destinations only; never repair input URLs."""
    if not isinstance(value, str) or not value:
        raise ValueError("來源網址必須是非空字串")
    if any(c.isspace() or ord(c) < 32 or 127 <= ord(c) <= 159 for c in value) or "\\" in value:
        raise ValueError("來源網址不可含空白、控制字元或反斜線")
    try:
        parts = urlsplit(value)
        if parts.scheme.lower() not in {"http", "https"} or not parts.netloc or not parts.hostname:
            raise ValueError
        if parts.username is not None or parts.password is not None or "@" in parts.netloc or "%" in parts.netloc:
            raise ValueError
        if parts.port is not None and not 1 <= parts.port <= 65535:
            raise ValueError
        host = parts.hostname
        if ":" in host:
            ipaddress.IPv6Address(host)
        else:
            ascii_host = host.encode("idna").decode("ascii").rstrip(".")
            if len(ascii_host) > 253 or not all(
                re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                for label in ascii_host.split(".")
            ):
                raise ValueError
        # Empty ports and trailing garbage after an IPv6 literal are ambiguous.
        if parts.netloc.endswith(":"):
            raise ValueError
        if parts.netloc.startswith("[") and not re.fullmatch(r"\[[^\]]+\](?::[0-9]+)?", parts.netloc):
            raise ValueError
    except (ValueError, UnicodeError):
        raise ValueError("來源網址必須是無帳密、有效主機與連接埠的 http(s) 網址") from None
    return value


def _validate(value, spec: dict, path: str = "brief") -> None:
    """Validate the subset of JSON Schema used by the existing brief contract."""
    kind = spec.get("type")
    valid = {
        "object": lambda: isinstance(value, dict),
        "array": lambda: isinstance(value, list),
        "string": lambda: isinstance(value, str),
        "integer": lambda: type(value) is int,
        "number": lambda: type(value) in (int, float) and math.isfinite(value),
    }
    if kind not in valid or not valid[kind]():
        raise ValueError(f"{path}: 必須符合 {kind} 型別")
    if "enum" in spec and value not in spec["enum"]:
        raise ValueError(f"{path}: 不支援的分類值")
    if kind == "object":
        props = spec.get("properties", {})
        if any(key not in value for key in spec.get("required", [])):
            raise ValueError(f"{path}: 缺少必要欄位")
        if spec.get("additionalProperties") is False and any(key not in props for key in value):
            raise ValueError(f"{path}: 含契約以外欄位")
        for key, child in props.items():
            if key in value:
                _validate(value[key], child, f"{path}.{key}")
    elif kind == "array":
        if not spec.get("minItems", 0) <= len(value) <= spec.get("maxItems", math.inf):
            raise ValueError(f"{path}: 項目數量超出契約範圍")
        for i, child in enumerate(value):
            _validate(child, spec["items"], f"{path}[{i}]")
        if spec.get("uniqueItems") and any(child in value[:i] for i, child in enumerate(value)):
            raise ValueError(f"{path}: 項目不可重複")
    elif kind == "string":
        if len(value) < spec.get("minLength", 0) or (spec.get("minLength", 0) and not value.strip()):
            raise ValueError(f"{path}: 字串不可空白")
        if len(value) > spec.get("maxLength", math.inf):
            raise ValueError(f"{path}: 字串超出契約範圍")
        # The current schema double-escapes \\d. Do not mutate it: enforce the
        # intended ISO calendar date here and document the narrow divergence.
        if path == "brief.date":
            try:
                if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                    raise ValueError
                date.fromisoformat(value)
            except ValueError:
                raise ValueError("brief.date: 必須是有效的 YYYY-MM-DD 日期") from None
        elif "pattern" in spec and not re.search(spec["pattern"], value):
            raise ValueError(f"{path}: 字串格式不符")
    elif not spec.get("minimum", -math.inf) <= value <= spec.get("maximum", math.inf):
        raise ValueError(f"{path}: 數值超出契約範圍")


CSS = """
:root{color-scheme:light;--paper:#f4f0e7;--card:#fffdf7;--ink:#182d36;--muted:#50616a;--line:#d2d4cb;--accent:#165f60;--gold:#edc879}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI","Microsoft JhengHei","PingFang TC",sans-serif;line-height:1.8;overflow-wrap:anywhere}
a{color:#12585b;text-underline-offset:.2em}a:hover{text-decoration-thickness:2px}a:focus-visible{outline:3px solid #b65a23;outline-offset:4px}h1,h2,h3,p,ul,figure{margin:0}h1,h2{font-family:Georgia,"Noto Serif TC","PMingLiU",serif;line-height:1.4}h1{font-size:clamp(2rem,5vw,3.65rem);letter-spacing:.02em}h2{font-size:1.65rem}h3{font-size:1rem}.wrap{width:min(1140px,calc(100% - 40px));margin:auto}.skip{position:absolute;left:1rem;top:-5rem;background:white;padding:.6rem;z-index:2}.skip:focus{top:1rem}.masthead{display:flex;justify-content:space-between;align-items:center;gap:1rem;border-bottom:2px solid var(--ink);padding:1.25rem 0}.brand{font-family:Georgia,serif;font-weight:700;font-size:1.9rem;letter-spacing:.16em}.edition{font-size:.85rem;text-align:right;color:var(--muted)}.hero{margin:1.5rem 0;background:var(--ink);color:#fffdf7;border-radius:4px;padding:clamp(1.5rem,4vw,3rem);display:grid;grid-template-columns:minmax(0,1.7fr) minmax(0,1fr);gap:2rem;align-items:center}.eyebrow{font-size:.8rem;letter-spacing:.14em;font-weight:700;margin-bottom:.8rem}.hero .eyebrow{color:var(--gold)}.hero .meta{color:#d4e1df;margin-top:1rem}.hero figure{color:#d4e1df}.hero svg{width:100%;height:auto;display:block}.hero figcaption{font-size:.75rem;text-align:center}.chip{display:inline-block;border:1px solid #a8b9b5;border-radius:100px;padding:.12rem .65rem;font-size:.78rem;font-weight:600}.hero .chip{margin-top:1rem}.notice{border-left:4px solid var(--accent);padding:1rem 1.25rem;background:#e4ece5;margin:1rem 0}.preview{background:#fff0c9;border-color:#8b4b1f}.contents{padding:1.25rem 0 1.5rem;border-bottom:1px solid var(--line)}.contents ul{padding-left:1.4rem;margin-top:.5rem;columns:2;column-gap:2rem}.contents li{break-inside:avoid;margin:.35rem 0}.section-label{font-size:.85rem;letter-spacing:.12em;margin:1.8rem 0 .8rem}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1.25rem;align-items:start}.card{min-width:0;background:var(--card);border:1px solid var(--line);border-top:4px solid var(--accent);border-radius:4px;padding:1.5rem;break-inside:avoid;scroll-margin-top:1rem}.card:first-child{grid-column:1/-1}.card-header{display:flex;gap:1rem;align-items:flex-start;margin-bottom:1rem}.rank{color:#6a7d7e;font:2.8rem/1 Georgia,serif}.category{font-size:.8rem;color:var(--accent);font-weight:700;letter-spacing:.1em;margin-bottom:.35rem}.card-visual{float:right;width:100px;margin:0 0 .5rem 1rem;opacity:.9}.card-visual svg{display:block;width:100%;height:auto}.evidence{display:flex;flex-wrap:wrap;gap:.45rem;margin:.8rem 0}.warning{background:#fff0c9;color:#6c3b13;border-color:#b58844}.muted,.freshness{color:var(--muted);font-size:.87rem}.block{margin-top:1rem}.body-copy{white-space:pre-line}.sources{list-style:none;padding:0;margin-top:.6rem;clear:both}.sources li{border-top:1px solid var(--line);padding:.8rem 0}.source-url{display:block;font-size:.8rem;overflow-wrap:anywhere}.source-meta{font-size:.8rem;color:var(--muted)}.score-grid{display:flex;flex-wrap:wrap;gap:.5rem;margin:.5rem 0 0}.score{font-size:.75rem;background:#edf0e9;padding:.15rem .45rem}.action{margin-top:1rem;border-top:1px solid var(--line);padding-top:.8rem;font-size:.9rem;font-weight:600}.assumptions{padding-left:1.3rem}.footer{border-top:2px solid var(--ink);margin-top:2rem;padding:1.5rem 0 2rem;color:var(--muted);font-size:.8rem}.footer p+p{margin-top:.3rem}
@media(max-width:700px){.wrap{width:calc(100% - 28px)}.hero{grid-template-columns:minmax(0,1fr);gap:1rem}.hero figure{max-width:260px;margin:auto}.grid{grid-template-columns:minmax(0,1fr)}.card:first-child{grid-column:auto}.card{padding:1.15rem}.contents ul{columns:1}.masthead{align-items:flex-start}.brand{font-size:1.5rem}.edition{max-width:50%}h2{font-size:1.4rem}}
@media print{body{background:white;color:black}.wrap{width:100%}.hero{background:white;color:black;border:1px solid #999}.hero .eyebrow,.hero .meta,.hero figure{color:#333}.grid{display:block}.card{margin-bottom:1rem}.skip{display:none}a{color:black}.source-url{font-size:9pt}}
"""


CSS += """
body{line-height:1.65}.masthead{padding:.8rem 0}.hero{display:block;margin:1rem 0;padding:1.2rem 1.5rem}.hero h1{font-size:clamp(1.7rem,4vw,2.7rem)}.hero .meta{margin-top:.4rem}.hero .chip{margin-top:.5rem}.eyebrow{margin-bottom:.3rem}.notice{padding:.65rem 1rem;font-size:.85rem}.grid{gap:1rem}.card,.card:first-child{grid-column:auto;padding:0;overflow:hidden}.card-body{padding:1rem 1.2rem}.card-header{align-items:start;gap:.75rem}.card h2,.card:first-child h2{font-size:1.3rem}.card .rank{font-size:1.5rem}.source-image{margin:0;background:#e5e9e4}.source-image img{display:block;width:100%;height:auto;max-height:380px;object-fit:contain;aspect-ratio:16/9}.source-image figcaption{padding:.5rem 1rem;font-size:.72rem;color:var(--muted)}.missing-image{padding:1rem;background:#e5e9e4;color:var(--muted);font-size:.8rem}.evidence{margin:.6rem 0;display:flex;gap:.4rem;flex-wrap:wrap}.lead{font-size:1rem;white-space:pre-line}.uncertainty{font-size:.75rem;color:#704417;margin:.4rem 0}.composite{font-weight:700;background:#e4ece5}.block{margin-top:.9rem;padding-top:.6rem}.footer{font-size:.75rem;padding:1rem 0}.section-label{margin:1rem 0 .6rem}details{border-top:1px solid var(--line);margin-top:.85rem;padding-top:.6rem}summary{cursor:pointer;font-weight:600;font-size:.85rem;padding:.25rem 0}summary:focus-visible{outline:3px solid #b65a23;outline-offset:3px}.edition-details{margin-bottom:1rem}.edition-details ul{padding-left:1.3rem}.excerpt-label{font-size:.72rem;color:var(--muted)}
@media(max-width:700px){.card,.card:first-child{padding:0}.card-body{padding:.9rem 1rem}.hero{padding:1rem}.source-image img{max-height:300px}.grid{grid-template-columns:minmax(0,1fr)}}
"""


CSS += """
.card,.card:first-child{overflow:visible}.card-header>div{min-width:0}.commentary{border-left:3px solid var(--accent);padding:.35rem .65rem;margin-top:.5rem;background:#eef2eb;font-size:.9rem;white-space:pre-line}.market-time{font-size:.8rem;margin-top:.5rem;color:var(--accent)}.market-radar{border:1px solid var(--line);background:var(--card);padding:1rem;margin:1rem 0;min-width:0}.market-radar h2{font-size:1.2rem}.market-radar ul{padding-left:1.4rem}.market-radar li{margin:.75rem 0}.radar-note{font-size:.85rem}.card-compact{grid-column:1/-1;display:grid;grid-template-columns:minmax(0,160px) minmax(0,1fr)}.card-compact .source-image img{max-height:100px;aspect-ratio:16/9}.card-compact .source-image figcaption{font-size:.65rem;padding:.4rem .6rem}.card-compact .missing-image{font-size:.72rem;padding:.6rem}.card-compact .card-body{padding:.75rem 1rem;min-width:0}.card-compact h2{font-size:1.1rem}.card-compact .evidence{margin:.35rem 0}.card-compact .lead{font-size:.9rem}.card-compact .commentary{margin-top:.35rem}.card-compact details{margin-top:.5rem}.uncertainty{white-space:pre-line}.source-image,.source-image figcaption{min-width:0;overflow-wrap:anywhere}
@media(max-width:700px){.card-compact{grid-template-columns:minmax(0,88px) minmax(0,1fr)}.card-compact .card-body{padding:.65rem}.card-compact .source-image img{max-height:66px}.card-compact .card-header{gap:.4rem}.card-compact .rank{font-size:1.1rem}.card-compact h2{font-size:1rem}}
@media print{.card-compact{display:block}}
"""


CSS += """
.reading-overview,.reading-index,.evidence-summary{margin:1rem 0;padding:1rem 1.2rem;border:1px solid var(--line);background:var(--card);min-width:0}.reading-overview h2,.reading-index h2,.evidence-summary h2{font-size:1.2rem}.overview-list{padding-left:1.5rem;margin:.8rem 0 0}.overview-list>li{padding:.6rem 0}.overview-list>li+li{border-top:1px solid var(--line)}.overview-headline{font-size:1.05rem;font-weight:700;white-space:pre-wrap}.overview-list .commentary{margin-top:.35rem}.reading-note{font-size:.8rem;color:var(--muted);margin:.35rem 0}.evidence-counts,.category-links{display:flex;flex-wrap:wrap;gap:.4rem 1rem;list-style:none;padding:0;margin:.65rem 0}.evidence-counts{font-size:.85rem}.category-links a{display:inline-block;padding:.35rem .5rem;border:1px solid var(--line);border-radius:4px}.category-count{font-size:.78rem;color:var(--muted);margin-left:.4rem}.category-name,.category,.index-group h3{white-space:pre-wrap}.index-group{margin-top:1rem}.source-provenance{font-size:.8rem;color:var(--muted);white-space:pre-wrap;margin:.4rem 0}.back-to-index{display:inline-block;font-size:.8rem;padding:.4rem 0;margin-top:.4rem}.card:target,.card:focus-visible{outline:3px solid var(--accent);outline-offset:3px}.reading-index{scroll-margin-top:1rem}.reading-index:focus-visible{outline:3px solid var(--accent);outline-offset:3px}.reading-index .edition-details{margin-bottom:0}
.card-header .rank{flex:0 0 auto;white-space:nowrap}
.freshness{white-space:pre-wrap;font-size:.8rem;color:var(--muted);margin:.4rem 0}.reading-guide dl{margin:.6rem 0}.reading-guide dt{font-weight:600;margin-top:.5rem}.reading-guide dd{margin:0;font-size:.85rem}.reading-guide p{font-size:.85rem;margin:.5rem 0}
@media screen{
  .wrap{width:min(49rem,calc(100% - 2rem))}
  .grid{grid-template-columns:minmax(0,1fr);gap:1.6rem}
  .card-compact{display:block}
  .card .card-body{padding:clamp(1rem,3vw,2rem)}
  .card h2,.card:first-child h2{font-size:clamp(1.35rem,3vw,1.85rem);line-height:1.45}
  .card .lead,.body-copy{font-size:1.1rem;line-height:1.85}
  .card .lead{margin:.5rem 0 0}.card .excerpt-label{font-size:.82rem}
  .card .commentary,.overview-list .commentary{font-size:1rem;line-height:1.8;padding:.5rem .85rem}
  .uncertainty{font-size:.94rem;line-height:1.7;margin:.5rem 0}
  .card .source-provenance,.card .freshness{font-size:.88rem}
  .card .source-image{margin:.85rem 0 0;background:transparent}
  .card .source-image img{aspect-ratio:auto;width:auto;max-width:100%;height:auto;max-height:14rem}
  .card .source-image figcaption,.card .missing-image{font-size:.82rem;padding:.35rem 0;color:var(--muted);background:none}
  .edition-jumps{display:flex;flex-wrap:wrap;gap:.35rem 1.1rem;margin-top:.7rem}
  .edition-jumps a{color:white;padding:.35rem 0;font-weight:600}
  .overview-list>li{padding:.85rem 0}.overview-list>li::marker{font-weight:700;color:var(--accent)}
  .overview-headline{font-size:1.18rem}.card summary,.edition-details summary{font-size:1rem;padding:.55rem 0}
}
@media(max-width:480px){.card-compact{grid-template-columns:minmax(0,1fr)}.card-compact .card-body{padding:.9rem 1rem}.card-compact .source-image img{max-height:220px}.card-compact .source-image figcaption,.card-compact .missing-image{padding:.5rem 1rem}.reading-overview,.reading-index,.evidence-summary{padding:.85rem 1rem}.contents ul{columns:1}}
@media print{details::details-content{display:block;content-visibility:visible;height:auto;overflow:visible}details> :not(summary){display:block}.grid,.card-compact{display:block}.card,.reading-overview,.reading-index,.evidence-summary{break-inside:auto}.contents ul{columns:1}.back-to-index{display:none}.source-image img{max-height:200px}}
"""


CSS += """
@media screen {
  :root{--paper:#f6f8fb;--card:white;--ink:#162d45;--accent:#234f87;--muted:#475969;--line:#c8d3dd}
  .wrap{width:min(66rem,calc(100% - 2rem))}
  .issue-head{border-top:.45rem solid var(--accent);padding:1.1rem 0 .8rem}
  .issue-head h1,.overview-headline{font-family:"Microsoft JhengHei","PingFang TC",system-ui,sans-serif}
  .issue-head h1{font-size:clamp(1.35rem,2.4vw,2rem);letter-spacing:0}
  .issue-line{display:flex;flex-wrap:wrap;gap:.25rem 1rem;color:var(--muted);font-size:.85rem}
  .reading-overview{margin:0;padding:clamp(1rem,3vw,2rem);border:0;background:#e4eef8}
  .reading-overview h2{font-size:1.2rem;color:var(--accent)}
  .overview-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,16rem),1fr));gap:1.2rem;list-style:none;padding:0;margin:.6rem 0}
  .overview-list>li,.overview-list>li+li{min-width:0;border:0;padding:0}
  .overview-headline{display:block;color:var(--ink);font-weight:750;font-size:clamp(1.18rem,2vw,1.6rem);line-height:1.4;text-decoration-thickness:1px;text-decoration-color:#8da6bf}
  .overview-list .reading-note{margin:.35rem 0 0;font-weight:600;color:#304e6a}
  .overview-list .uncertainty{font-size:.91rem;margin:.15rem 0;color:#64421b;line-height:1.5}
  .overview-list details{border:0;margin:0;padding:0}.overview-list summary{color:var(--accent);font-size:.9rem;min-height:2.5rem;padding:.45rem 0}
  .edition-jumps a{color:var(--accent);padding:.45rem .1rem}
  .edition-jumps{margin:.65rem 0}.issue-notes{color:var(--muted);font-size:.87rem}
  main,.market-radar,.reading-index,.evidence-summary,.footer,.issue-notes,.edition-jumps{max-width:49rem;margin-inline:auto}
  .card,.card:first-child{border-top:2px solid var(--line);border-radius:0}
  @media(max-width:620px){.issue-head{padding:.5rem 0}.overview-list{display:block}
    .overview-list>li+li{border-top:1px solid #bacbdc;padding-top:.55rem;margin-top:.45rem}}
}
"""


def safe_image_data(value: str) -> str:
    """Bounded raster-only data URI. No IO, SVG, arbitrary MIME or URL fetching."""
    if not isinstance(value, str) or len(value) > 266691:
        raise ValueError("圖片資料超出上限")
    match = re.fullmatch(r"data:image/(jpeg|png);base64,([A-Za-z0-9+/]+={0,2})", value)
    if not match:
        raise ValueError("圖片必須是 base64 JPEG 或 PNG")
    try:
        raw = base64.b64decode(match[2], validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("圖片 base64 無效") from None
    if len(raw) > 200000 or base64.b64encode(raw).decode("ascii") != match[2]:
        raise ValueError("圖片資料無效或過大")
    if match[1] == "png":
        if (len(raw) < 45 or not raw.startswith(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
                or not raw.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82")):
            raise ValueError("PNG 簽章無效")
        width, height = int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")
    else:
        if not raw.startswith(b"\xff\xd8\xff") or not raw.endswith(b"\xff\xd9"):
            raise ValueError("JPEG 簽章無效")
        # Scan bounded JPEG marker segments for dimensions before the scan data.
        pos, width, height = 2, 0, 0
        while pos < len(raw) - 2:
            if raw[pos] != 255:
                raise ValueError("JPEG 標記無效")
            while pos < len(raw) and raw[pos] == 255:
                pos += 1
            if pos >= len(raw):
                break
            marker = raw[pos]
            pos += 1
            if marker in (0xDA, 0xD9):
                break
            length = int.from_bytes(raw[pos:pos + 2], "big")
            if length < 2 or pos + length > len(raw):
                raise ValueError("JPEG 區段無效")
            if marker in (0xC0, 0xC1, 0xC2):
                if length < 8:
                    raise ValueError("JPEG 尺寸無效")
                height = int.from_bytes(raw[pos + 3:pos + 5], "big")
                width = int.from_bytes(raw[pos + 5:pos + 7], "big")
                break
            pos += length
    if not (width > 0 and height > 0 and width * height <= 12000000 and max(width, height) <= 12000):
        raise ValueError("圖片尺寸無效或過大")
    return value


def image_attribution(image: dict) -> str:
    """Escaped provenance; caller validates the image URLs before rendering."""
    return (f'{_e(image["caption"])} {_e(image["credit"])} '
            f'<a href="{_e(image["source_url"])}" rel="noopener noreferrer" referrerpolicy="no-referrer">來源頁</a> · '
            f'<a href="{_e(image["original_url"])}" rel="noopener noreferrer" referrerpolicy="no-referrer">原圖</a>'
            '<br>來源配圖不等於事件證據；圖片權利未核實。')


def source_image(item: dict, *, compact: bool = False) -> str:
    image = item.get("image")
    if image is None:
        label = item.get("image_status") or "未取得可用來源配圖"
        return f'<p class="missing-image">無來源圖片 · {_e(label)}（不以插圖替代）</p>'
    data_uri = safe_image_data(image["data_uri"])
    if image["source_url"] not in {s["url"] for s in item["sources"]}:
        raise ValueError("圖片來源必須對應條目引用")
    for key in ("source_url", "original_url"):
        safe_source_url(image[key])
        if urlsplit(image[key]).scheme != "https":
            raise ValueError("圖片出處必須是 HTTPS")
    attribution = '來源配圖 · 圖片權利未核實。完整出處見下方。' if compact else image_attribution(image)
    return (f'<figure class="source-image"><img src="{data_uri}" '
            f'alt="{_e(image["caption"])}" loading="lazy" decoding="async" referrerpolicy="no-referrer">'
            f'<figcaption>{attribution}</figcaption></figure>')


def _e(value) -> str:
    return escape(str(value), quote=True)


REFERENCE_KINDS = {"trading_day": "交易日", "reporting_period": "資料期間", "event_date": "事件日期"}


def validate_market_references(data: dict) -> dict:
    """Check internal references, never claim to verify fetched source evidence.

    Exact quote/source-read verification belongs to editorial: saved briefs do
    not contain the fetched document. No network or semantic inference here.
    """
    by_rank = {}
    edition_date = date.fromisoformat(data["date"])
    for position, item in enumerate(data["items"], 1):
        rank = item["rank"]
        if rank in by_rank:
            raise ValueError("條目排序不可重複")
        by_rank[rank] = (position, item)
        context = item.get("market_context")
        is_market = item.get("market_scope", "none") != "none"
        if is_market != (context is not None):
            raise ValueError("市場條目必須附參照時間；非市場條目不可附市場脈絡")
        if context is not None:
            try:
                reference_date = date.fromisoformat(context["reference_date"])
            except ValueError:
                raise ValueError("市場參照日期無效") from None
            if reference_date > edition_date:
                raise ValueError("市場參照日期不可晚於本期日期")
            safe_source_url(context["source_url"])
            if context["source_url"] not in {source["url"] for source in item["sources"]}:
                raise ValueError("市場時間出處必須對應條目引用")
    radar = data.get("market_radar")
    if radar is not None:
        ranks = radar["item_ranks"]
        if (radar["status"] == "available") != bool(ranks):
            raise ValueError("市場雷達狀態與引用數量不符")
        for rank in ranks:
            if rank not in by_rank or by_rank[rank][1].get("market_scope", "none") == "none":
                raise ValueError("市場雷達僅可引用已選市場條目")
    return by_rank


def commentary_html(item: dict) -> str:
    text = item.get("commentary", "舊版資料未提供短評；本工具不補寫分析。")
    return f'<p class="commentary"><strong>Scout短評／分析</strong> · {_e(text)}</p>'


def market_time_html(item: dict) -> str:
    context = item.get("market_context")
    if context is None:
        return ""
    return (f'<p class="market-time"><strong>市場參照時間（非發布時間）</strong> · '
            f'{REFERENCE_KINDS[context["reference_kind"]]} '
            f'<time datetime="{_e(context["reference_date"])}">{_e(context["reference_date"])}</time> · '
            f'{_e(context["period_label"])}</p>')


def market_radar_html(data: dict, by_rank: dict) -> str:
    radar = data.get("market_radar")
    entries = []
    if radar is None:
        note = "市場雷達不可用：舊版資料未提供；本工具不推算或補寫。"
    elif radar["status"] == "unavailable":
        note = "市場雷達不可用 · " + radar["note"]
    else:
        note = radar["note"]
        # Use only explicitly selected ranks; sorting is presentation, not a new ranking.
        for rank in sorted(radar["item_ranks"]):
            position, item = by_rank[rank]
            entries.append(f'<li><a href="#item-{position}">{rank:02d} · {_e(item["headline"])}</a>'
                           f'{market_time_html(item)}{commentary_html(item)}</li>')
    listing = f'<ul>{"".join(entries)}</ul>' if entries else ""
    return (f'<section class="market-radar" aria-labelledby="radar-title"><h2 id="radar-title">市場雷達</h2>'
            f'<p class="radar-note">{_e(note)}</p>{listing}'
            '<p class="muted">僅引用本期市場新聞，非即時報價或投資建議。</p></section>')


def citation_hostname(source: dict) -> str:
    """Exact lowercased URL hostname, not a publisher or registrable domain.

    Call only after source URL validation; retain subdomains and trailing dots.
    """
    return urlsplit(source['url']).hostname.lower()


def source_provenance_html(item: dict) -> str:
    """Expose supplied first-citation metadata without choosing a primary source."""
    source = item['sources'][0]
    publication = source.get('published_at')
    date_label = f'發布：{_e(publication)}' if publication else '發布時間未提供'
    return (f'<p class="source-provenance">首筆引用：{_e(citation_hostname(source))} · '
            f'{date_label} · {len(item["sources"])} 筆引用連結<br>'
            '首筆不代表第一手來源；發布字串為輸入資料，非事件時間。</p>')


def reading_guide_html() -> str:
    """Fixed interpretation help, not a new assessment of supplied evidence."""
    definitions = {
        'primary': '輸入標為第一手材料，例如原始文件或當事方說法；不等於獨立核實，也不保證當事方主張正確。',
        'reputable_secondary': '輸入標為可信次級報導或轉述；這個類別不是逐句查證保證。',
        'community_signal': '社群討論或經驗訊號；不能單獨當作已核實新聞。',
        'unverified_lead': '仍待查證的線索；不應據此當成確定事實。',
        'mixed': '輸入標為混合來源或不同核實程度；不表示整則已核實，仍須逐項看限制。',
    }
    labels = ''.join(f'<dt>{label}</dt><dd>{definitions[key]}</dd>' for key, label in EVIDENCE.items())
    return ('<details class="reading-guide"><summary>如何讀這份晨報：時效與證據標記</summary>'
            '<p>摘要與影響是Scout整理，非來源逐字引文；Scout短評／分析是解讀，不是已發生結果的保證。請連同限制與來源閱讀。</p>'
            '<p>刊期是本期輸入日期；頁首時效範圍與各則時效說明沿用輸入。來源發布字串不等於事件時間；未提供就保留未知，不換算相對日期、不推算更新時間。此離線文件不會自動更新。</p>'
            f'<dl>{labels}</dl><p>所有證據標記沿用輸入，不由排版工具重新評定。編輯評分不是機率，也不是查證完成率。</p></details>')


def reading_desk_html(data: dict, assumptions_html: str) -> str:
    """Navigation and metadata only, after schema/URL validation; never rerank."""
    items = data['items']
    overview = []
    for position, item in enumerate(items[:3], 1):
        comment = item.get('commentary', '舊版未提供短評；本工具不補寫分析。')
        caveat = item.get('uncertainty_summary', '舊版未提供精簡限制提示；請展開完整查證備註。')
        overview.append(
            f'<li><a class="overview-headline" href="#item-{position}">{_e(item["headline"])}</a>'
            f'<p class="reading-note">證據標記：{EVIDENCE[item["evidence_quality"]]}</p>'
            f'<p class="uncertainty">限制：{_e(caveat)}</p>'
            f'<details><summary>讀短評</summary><p class="commentary"><strong>Scout短評／分析</strong> · {_e(comment)}</p></details></li>')
    groups = {}
    for position, item in enumerate(items, 1):
        groups.setdefault(item['category'], []).append((position, item))
    quick_links, complete = [], []
    for category, members in groups.items():
        if len(quick_links) < 6:
            quick_links.append(
                f'<li><a href="#item-{members[0][0]}"><span class="category-name">{_e(category)}</span>'
                f'<span class="category-count">{len(members)} 則</span></a></li>')
        links = ''.join(f'<li><a href="#item-{position}">{_e(item["headline"])}</a></li>'
                        for position, item in members)
        complete.append(f'<section class="index-group"><h3>{_e(category)}</h3>'
                        f'<p class="reading-note">{len(members)} 則</p><ul>{links}</ul></section>')

    partial = '僅列前 6 類；其餘請展開全部分類索引。' if len(groups) > 6 else '已列出全部分類。'
    return f'''<section class="reading-overview" aria-labelledby="overview-title">
<h2 id="overview-title">先看這幾則</h2><ol class="overview-list">{''.join(overview)}</ol>
<p class="reading-note">依本期原始順序選讀，不重新排名，非獨立核實。</p></section>
<nav class="edition-jumps" aria-label="晨報閱讀捷徑"><a href="#item-1">從第一則讀起</a><a href="#reading-index">按分類找新聞</a><a href="#evidence-title">查看證據說明</a></nav>
<p class="issue-notes">選材範圍：{_e(data['freshness_window'])} 來源配圖不等於事件證據。</p>

<section class="reading-index" id="reading-index" tabindex="-1" aria-labelledby="index-title">
<nav class="category-nav" aria-labelledby="index-title"><h2 id="index-title">依分類跳讀</h2>
<p class="reading-note">依分類首次出現順序；跳至該分類第一則，不重新分組或改變正文順序。{partial}</p>
<ul class="category-links">{''.join(quick_links)}</ul></nav>
<details class="edition-details"><summary>全部分類索引（{len(groups)} 類／{len(items)} 則）</summary>
<nav class="contents" aria-label="本期完整分類索引">{''.join(complete)}</nav>{assumptions_html}</details></section>'''


def evidence_summary_html(items: list) -> str:
    counts = Counter(item['evidence_quality'] for item in items)
    evidence = ''.join(f'<li>{label}：{counts[key]} 則</li>' for key, label in EVIDENCE.items())
    hosts = {citation_hostname(source) for item in items for source in item['sources']}
    citations = sum(len(item['sources']) for item in items)
    return f'''<section class="evidence-summary" aria-labelledby="evidence-title"><h2 id="evidence-title">本期證據與引用概況</h2><p>來源標記 ≠ 獨立核實</p>
<p>{len(items)} 則已選條目 · {citations} 筆引用連結 · {len(hosts)} 個不同主機名稱</p><ul class="evidence-counts">{evidence}</ul>
<p class="reading-note">僅統計輸入中已選條目與引用；證據類別沿用輸入。主機名稱依 URL 小寫去重，保留子網域；引用連結數含重複。非嘗試來源覆蓋率，不代表來源獨立性，也不代表交叉查證。</p>{reading_guide_html()}</section>'''


def render_brief(data: dict, *, design_preview: bool = False, saved_replay: bool = False) -> str:
    """Render schema-shaped data to a self-contained, escaped zh-Hant document.

    Raises ValueError for malformed input/unsafe URLs. Evidence and order are
    supplied by Hermes, not inferred or upgraded by this presentation helper.
    """
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    _validate(data, schema)
    by_rank = validate_market_references(data)
    for item in data["items"]:
        for source in item["sources"]:
            safe_source_url(source["url"])
    e = _e
    cards = []
    for position, item in enumerate(data["items"], 1):
        # Position is used for IDs, never untrusted or potentially duplicate ranks.
        sources = []
        for source in item["sources"]:
            sources.append(
                f'<li><a href="{e(source["url"])}" rel="noopener noreferrer" referrerpolicy="no-referrer">'
                f'{e(source["title"])}<span class="source-url">{e(source["url"])}</span></a>'
                f'<p class="source-meta">發布：{e(source.get("published_at") or "未提供")} · '
                f'類型：{e(source.get("source_type") or "未提供")}</p></li>'
            )
        quality = item["evidence_quality"]
        warning = " warning" if quality in {"community_signal", "unverified_lead", "mixed"} else ""
        scores = ''.join(f'<span class="score">{label} {e(item["scores"][key])}/10</span>' for key, label in SCORES.items())
        notes = item.get("verification_notes") or "未提供核實備註；來源標記不等於逐項獨立查證。"
        caveat = item.get('uncertainty_summary') or '舊版未提供精簡限制提示；請展開完整查證備註。'
        full_text = item['why_it_matters']
        # Explicit editorial presentation wins at every rank/position. Only
        # field-less legacy items retain their historical rank-based layout.
        compact = item.get('display_tier', 'compact' if item['rank'] > 10 else 'full') == 'compact'
        limit = 45 if compact else 70
        lead = full_text if len(full_text) <= limit else full_text[:limit - 1] + '…'
        excerpt = '<p class="excerpt-label">摘要節錄（Scout整理，非來源逐字引文）；完整敘述與限制見下方</p>' if len(full_text) > limit else '<p class="excerpt-label">摘要與影響（Scout整理，非來源逐字引文）</p>'
        context = item.get('market_context')
        context_detail = (f'<section class="block"><h3>市場時間出處（輸入引文，非本工具核實）</h3>'
                          f'<p class="body-copy">{e(context["evidence_quote"])}</p>'
                          f'<a href="{e(context["source_url"])}" rel="noopener noreferrer" referrerpolicy="no-referrer">參照日期出處</a></section>') if context else ''
        tier = 'card-compact' if compact else 'card-full'
        image_html = source_image(item, compact=compact)
        image_detail = (f'<section class="block image-provenance"><h3>圖片說明與出處</h3>'
                        f'<p>{image_attribution(item["image"])}</p></section>') if compact and item.get('image') else ''
        cards.append(f'''<article class="card {tier}" id="item-{position}" aria-labelledby="headline-{position}" tabindex="-1">
<div class="card-body">
<div class="card-header"><span class="rank" aria-label="排序 {item['rank']}">{item['rank']:02d}</span><div><p class="category">{e(item['category'])}</p><h2 id="headline-{position}">{e(item['headline'])}</h2></div></div>
<div class="evidence"><span class="chip composite">綜合 {e(item['scores']['composite'])}/10</span><span class="chip{warning}">{EVIDENCE[quality]}</span></div>
<p class="lead">{e(lead)}</p>{excerpt}
{commentary_html(item)}{market_time_html(item)}
<p class="uncertainty">限制：{e(caveat)}</p>
<p class="freshness">時效說明（輸入標記） · {e(item['freshness'])}</p>
{source_provenance_html(item)}
{image_html}
<details class="item-details"><summary>來源、查證與完整內容</summary>
<section class="block"><h3>摘要與影響（Scout整理）</h3><p class="body-copy">{e(item['why_it_matters'])}</p></section>
<section class="block"><h3>查證備註／缺口</h3><p class="body-copy muted">{e(notes)}</p></section>
{context_detail}
{image_detail}
<section class="block"><h3>來源與日期</h3><ul class="sources">{''.join(sources)}</ul></section>
<section class="block"><h3>編輯評分 <span class="muted">／輸入值，非機率</span></h3><div class="score-grid">{scores}</div></section>
<p class="action">建議下一步 → {ACTIONS[item['suggested_next_action']]}<br><span class="muted">僅呈現建議，不執行外部操作。</span></p>
</details><a class="back-to-index" href="#reading-index">回到分類索引</a></div></article>''')
    assumptions = ''.join(f'<li>{e(text)}</li>' for text in data.get("assumptions", []))
    assumptions_html = f'<section><h2>閱讀前提／覆蓋限制</h2><ul class="assumptions">{assumptions}</ul></section>' if assumptions else ''
    preview = '<aside class="notice preview"><strong>設計預覽 · 非新聞 · 不供決策</strong><p>所有條目、來源連結與分數均為版面佔位；日期為示範日期，不代表採集或核實時間。</p></aside>' if design_preview else ''
    title_prefix = "設計預覽（非新聞）｜" if design_preview else ""
    # The issue date appears separately; keep the complete archive title in <title>.
    heading = data['title'].removesuffix('｜' + data['date']).rstrip() or data['title']
    # CSP is defense in depth; escaped text and fixed markup remain the boundary.
    return f'''<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; script-src 'none'; connect-src 'none'; base-uri 'none'; form-action 'none'">
<meta name="referrer" content="no-referrer"><title>{title_prefix}{e(data['title'])}｜Scout</title>
<style>{CSS}</style></head><body>
<a class="skip" href="#main">跳至簡報內容</a><div class="wrap">
{preview}<header class="issue-head"><h1 id="brief-title">{e(heading)}</h1>
<p class="issue-line"><span>每日選讀 / 本期 {len(data['items'])} 則條目</span><time datetime="{e(data['date'])}">{e(data['date'])}</time><span>{STATUS[data['status']]}</span>{'<span>存檔重排，非重新採集</span>' if saved_replay else ''}</p></header>
{reading_desk_html(data, assumptions_html)}
{market_radar_html(data, by_rank)}
<main id="main" tabindex="-1"><h2 class="section-label">逐則閱讀</h2><div class="grid">{''.join(cards)}</div></main>
{evidence_summary_html(data['items'])}
<footer class="footer"><p>Scout · Hermes 研究與編輯。評分為輸入值，非機率。來源圖片權利未核實；無圖時不替代。</p><p>離線 HTML · 無 JavaScript、外部字型或追蹤。僅點擊出處連結才離開文件。Telegram 文件附件（.html）。</p></footer>
</div></body></html>
'''


def demo_data() -> dict:
    """Explicit layout placeholders, not fabricated news or source evidence."""
    headlines = ["主題佔位：一則值得深入閱讀的觀察", "來源佔位：先看證據，再下結論", "追蹤佔位：保留問題，不急著行動"]
    qualities = ["unverified_lead", "community_signal", "mixed"]
    return {
        "title": "設計預覽｜給好奇心一份有脈絡的簡報", "status": "draft",
        "date": "2026-09-19", "freshness_window": "版面示範，非即時情報",
        "market_radar": {"status": "unavailable", "item_ranks": [], "note": "非新聞設計佔位，沒有市場資料；不補寫數字或走勢。"},
        "assumptions": ["本頁只有版面佔位，不包含新聞、研究結論或已核實事件。", "example.org 為示範連結，不能作為條目證據；全部分數為佔位。"],
        "items": [{
            "rank": i, "headline": headline, "category": "設計佔位 · 非新聞",
            "commentary": "短評佔位：僅示範分析欄位，不作事件判斷。", "market_scope": "none",
            "uncertainty_summary": "非新聞設計佔位，沒有實際來源證據。",
            "why_it_matters": "摘要佔位：此處放置 Hermes 選定的資訊重點與背景。\n影響佔位：說明它為何與讀者有關，並保留限制與不確定性。本段不陳述任何新聞事件。",
            "freshness": "非新聞，無採集時間", "evidence_quality": qualities[i - 1],
            "sources": [{"title": "版面示範連結（非證據）", "url": "https://example.org/", "published_at": "不適用：佔位", "source_type": "設計佔位"}],
            "scores": {key: 0 for key in SCORES}, "verification_notes": "未查證；此為設計佔位，分數與證據標籤僅展示元件。",
            "suggested_next_action": "verify",
        } for i, headline in enumerate(headlines, 1)],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Scout 離線 HTML 排版；不查證、不傳送。")
    parser.add_argument("input", help="brief JSON；--demo 時填 -")
    parser.add_argument("output", help="輸出 .html 路徑")
    parser.add_argument("--demo", action="store_true", help="僅產生明確標示非新聞的設計預覽")
    args = parser.parse_args(argv)
    output = Path(args.output)
    try:
        if output.suffix.lower() != ".html":
            raise ValueError("輸出必須使用 .html 副檔名")
        if not args.demo and Path(args.input).resolve() == output.resolve():
            raise ValueError("輸入與輸出不可相同")
        if args.demo and args.input != "-":
            raise ValueError("--demo 的輸入請使用 -，避免忽略真實資料")
        data = demo_data() if args.demo else json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
        rendered = render_brief(data, design_preview=args.demo)
        output.write_text(rendered, encoding="utf-8")
    except (OSError, ValueError, RecursionError, OverflowError):
        # Do not echo JSON, unsafe URLs, or credential-bearing input in logs.
        print("ERROR: 無法產生 HTML；請檢查輸入契約、來源 URL 與檔案路徑。", file=sys.stderr)
        return 1
    print("PASS: Scout HTML rendered (local file only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
