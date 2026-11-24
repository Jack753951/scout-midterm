"""Fixed public feeds; never fetch article links, images or account data."""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from http.client import HTTPException
from urllib.parse import urlsplit, parse_qsl, urlencode, urlunsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener
from xml.etree import ElementTree as ET

TAIPEI = timezone(timedelta(hours=8))
FEEDS = (
    ('BBC 中文', 'https://feeds.bbci.co.uk/zhongwen/trad/rss.xml'),
    ('BBC World', 'https://feeds.bbci.co.uk/news/world/rss.xml'),
    ('UN News', 'https://news.un.org/feed/subscribe/en/news/all/rss.xml'),
    ('NPR World', 'https://feeds.npr.org/1004/rss.xml'),
)
MAX_BYTES = 2_000_000


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url):
    if url not in {u for _, u in FEEDS}:
        raise ValueError('unknown feed')
    req = Request(url, headers={'User-Agent': 'ScoutMorning/1.0', 'Accept-Encoding': 'identity'})
    with build_opener(NoRedirect()).open(req, timeout=12) as response:
        data = response.read(MAX_BYTES + 1)
    return data


class Plain(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain(text):
    p = Plain()
    p.feed((text or '')[:8000]); p.close()
    return ' '.join(' '.join(p.parts).split())


def date_of(value):
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if dt is None or dt.tzinfo is None:
        return None
    return dt.astimezone(TAIPEI)


def link_key(url):
    try:
        p = urlsplit(url)
        if (p.scheme not in ('https', 'http') or not p.hostname or p.username is not None or p.password is not None
                or any(ord(c) < 33 or c in '\\<>"' for c in url)):
            return None
        _ = p.port
        query = [(k,v) for k,v in parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith('utm_') and k not in ('at_medium','at_campaign')]
        return urlunsplit((p.scheme, p.netloc.lower(), p.path, urlencode(sorted(query)), ''))
    except ValueError:
        return None


def parse(data, source, now):
    if len(data) > MAX_BYTES:
        raise ValueError('feed too large')
    xml = data.decode('utf-8-sig')
    if '\x00' in xml or '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():
        raise ValueError('unsupported XML')
    root = ET.fromstring(xml)
    channel = root.find('channel')
    if root.tag != 'rss' or channel is None:
        raise ValueError('not RSS 2.0')
    rows = []
    for item in channel.findall('item')[:400]:
        published = date_of(item.findtext('pubDate'))
        url = (item.findtext('link') or '').strip()
        title = ' '.join((item.findtext('title') or '').split())[:600]
        if not (title and link_key(url) and published and published.date() == now.astimezone(TAIPEI).date() and published <= now):
            continue
        excerpt = plain(item.findtext('description'))
        rows.append(dict(title=title, url=url, source=source, published=published.isoformat(timespec='seconds'), excerpt=excerpt[:159]+'…' if len(excerpt)>160 else excerpt))
    return rows


def collect(now, read=fetch):
    all_rows, status = [], []
    for source, url in FEEDS:
        try:
            rows = parse(read(url), source, now)
        except (OSError, ValueError, ET.ParseError, EOFError, HTTPException) as exc:
            status.append((source, '讀取失敗：'+type(exc).__name__)); continue
        status.append((source, f'符合日期 {len(rows)} 則（去重前）'))
        all_rows.extend(rows)
    seen, rows = set(), []
    for row in sorted(all_rows, key=lambda r:r['published'], reverse=True):
        key = link_key(row['url'])
        if key not in seen:
            rows.append(row); seen.add(key)
    return rows, status
