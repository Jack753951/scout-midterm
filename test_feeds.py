from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
from scout_morning import cli, feed

NOW = datetime(2026, 11, 24, 8, tzinfo=feed.TAIPEI)


def rss(url='https://example.org/news', date='Mon, 23 Nov 2026 16:00:00 GMT'):
    return f'<rss><channel><item><title>Teaching fixture</title><link>{url}</link><pubDate>{date}</pubDate><description>&lt;b&gt;Sample excerpt&lt;/b&gt;</description></item></channel></rss>'.encode()


class FeedTests(TestCase):
    def test_local_midnight_inclusive_and_no_html_from_feed(self):
        row, = feed.parse(rss(), 'Fixture', NOW)
        self.assertEqual(row['excerpt'], 'Sample excerpt')
        self.assertEqual(row['published'], '2026-11-24T00:00:00+08:00')
        self.assertIn('https://example.org/news', cli.render(NOW, [row], []))

    def test_time_and_link_rejections(self):
        for date in ('', 'Mon, 23 Nov 2026 15:59:59 GMT', 'Mon, 23 Nov 2026 18:00:00', 'Tue, 24 Nov 2026 00:00:01 GMT'):
            self.assertEqual(feed.parse(rss(date=date), 'Fixture', NOW), [])
        for url in ('file:///sample', 'https://user@example.org/test'):
            self.assertEqual(feed.parse(rss(url=url), 'Fixture', NOW), [])

    def test_duplicate_tracking_and_one_failed_source(self):
        def reader(url):
            if url == feed.FEEDS[0][1]:
                raise OSError('simulated')
            return rss('https://example.org/news?utm_source=' + str(len(url)))
        rows, states = feed.collect(NOW, reader)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(states), len(feed.FEEDS))
        self.assertIn('讀取失敗', states[0][1])

    def test_hostile_or_oversize_xml(self):
        for data in (b'<!DOCTYPE rss><rss/>', b'<html/>', b' '*(feed.MAX_BYTES+1)):
            with self.assertRaises(ValueError):
                feed.parse(data,'Fixture',NOW)

    def test_empty_and_failed_do_not_overwrite_success_or_call_extras(self):
        from types import ModuleType
        with TemporaryDirectory() as d, mock.patch.object(cli, 'datetime') as clock, mock.patch.dict('sys.modules',{'scout_morning.extras':ModuleType('forbidden')}):
            clock.now.return_value = NOW
            ok = Path(d)/'2026-11-24.html'
            ok.write_text('prior edition', encoding='utf8')
            for status, code, suffix in [('讀取失敗：OSError',1,'unavailable'), ('符合日期 0 則（去重前）',0,'empty')]:
                with mock.patch.object(cli,'collect',return_value=([],[('Fixture',status)])):
                    self.assertEqual(cli.main(['--output-dir',d,'--ai','--telegram']), code)
                    self.assertIn('沒有符合條件', (Path(d)/f'2026-11-24-{suffix}.html').read_text(encoding='utf8'))
                    self.assertEqual(ok.read_text(encoding='utf8'),'prior edition')

    def test_default_never_imports_extras_with_real_rows(self):
        from types import ModuleType
        rows=feed.parse(rss(), 'Fixture', NOW)
        with TemporaryDirectory() as d, mock.patch.object(cli,'collect',return_value=(rows,[('Fixture','ok')])), mock.patch.dict('sys.modules',{'scout_morning.extras':ModuleType('forbidden')}):
            self.assertEqual(cli.main(['--output-dir',d]),0)
            html=next(Path(d).glob('*.html')).read_text(encoding='utf8')
            self.assertEqual(html.count('<article>'),1)
            self.assertNotIn('AI 標題導讀',html)
