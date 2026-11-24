import json
import unittest
from pathlib import Path
from scripts.render_brief import render_brief


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(Path(__file__).with_name('example.json').read_text(encoding='utf-8'))

    def test_headlines_link_to_original_order(self):
        html = render_brief(self.data)
        for n, item in enumerate(self.data['items'], 1):
            self.assertIn(f'href="#item-{n}">{item["headline"]}</a>', html)
            self.assertIn(f'id="item-{n}"', html)

    def test_missing_date_remains_unknown(self):
        card = render_brief(self.data).split('id="item-3"')[1]
        self.assertIn('待查線索', card)
        self.assertIn('發布時間未提供', card)
        self.assertIn('來源只有群組轉述', card.split('<details')[0])

    def test_missing_source_is_rejected(self):
        self.data['items'][0]['sources'] = []
        with self.assertRaises(ValueError):
            render_brief(self.data)

    def test_non_web_link_is_rejected(self):
        self.data['items'][0]['sources'][0]['url'] = 'file:///not-a-web-link'
        with self.assertRaises(ValueError):
            render_brief(self.data)

    def test_repeat_does_not_duplicate(self):
        html = render_brief(self.data)
        self.assertEqual(html, render_brief(self.data))
        self.assertEqual(html.count('<article '), 3)
