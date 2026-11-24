import argparse
from datetime import datetime
from html import escape as e
from pathlib import Path
import os
import sys
import tempfile
from .feed import collect, TAIPEI


def render(now, rows, status, analysis=''):
    day = now.date().isoformat()
    cards = ''.join(f'<article><small>{e(r["source"])}　{e(r["published"])}</small><h2><a href="{e(r["url"], quote=True)}" rel="noreferrer noopener">{e(r["title"])}</a></h2><p>{e(r["excerpt"]) or "RSS 未提供摘要。"}</p></article>' for r in rows)
    coverage = ''.join(f'<li>{e(s)}：{e(info)}</li>' for s,info in status)
    ai = '<section><h2>AI 標題導讀（未核實）</h2><p style="white-space:pre-wrap">'+e(analysis)+'</p></section>' if analysis else ''
    return f'''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none';style-src 'unsafe-inline';base-uri 'none';form-action 'none'"><title>Scout RSS 晨報｜{day}</title><style>body{{max-width:46rem;margin:auto;padding:1rem;font:1.05rem/1.7 system-ui,sans-serif;color:#183149;overflow-wrap:anywhere}}h1{{border-top:.4rem solid #265680;padding-top:.5rem}}h2{{font-size:1.25rem;line-height:1.5;margin:.2rem 0}}article,section{{border-top:1px solid #c1cfdc;padding:1rem 0}}small{{color:#455a70}}p{{margin:.4rem 0}}a{{color:#164f82}}</style><main><h1>Scout RSS 晨報</h1><p>{day}（台北）｜{len(rows)} 則｜產生時間 {now:%H:%M}</p><p>依來源發布時間排序。標題與短摘來自 RSS，不是獨立查證；發布時間不等於事件時間。</p>{ai}{cards or '<p>目前沒有符合條件的消息；請查看來源狀態。未用示範資料補足。</p>'}<section><h2>來源狀態</h2><ul>{coverage}</ul></section></main></html>'''


def save(path, html):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.scout-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(html)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def main(argv=None):
    p = argparse.ArgumentParser(description='公開 RSS → 台北當日 HTML 晨報（預設不呼叫 AI、不投遞）')
    p.add_argument('--output-dir', type=Path, default=Path('scout-output'))
    p.add_argument('--ai', action='store_true', help='將標題、出處與網址送至 OpenAI 產生選配導讀，可能產生費用')
    p.add_argument('--telegram', action='store_true', help='將本次 HTML 發送至自行指定的 Telegram 聊天（一次）')
    args = p.parse_args(argv)
    now = datetime.now(TAIPEI)
    rows, status = collect(now)
    all_failed = all(value.startswith('讀取失敗') for _,value in status)
    # Never replace a previous healthy edition with a failed or empty probe.
    suffix = '-unavailable' if all_failed else '-empty' if not rows else ''
    out = args.output_dir / f'{now.date()}{suffix}.html'
    analysis, failed = '', False
    if args.ai and rows:
        from .extras import summarize
        try:
            analysis = summarize(rows)
        except (RuntimeError, ValueError):
            print('AI 導讀失敗；保留 RSS 原版。', file=sys.stderr); failed = True
    save(out, render(now, rows, status, analysis))
    print(f'{len(rows)} 則 | {out.resolve()}')
    for source, msg in status:
        print(f'{source}: {msg}')
    if args.telegram and rows and not failed:
        from .extras import send_document
        try:
            send_document(out)
        except (RuntimeError, ValueError):
            print('Telegram 未取得成功回執；不要自動重送。', file=sys.stderr); failed = True
    return 1 if all_failed or failed else 0
