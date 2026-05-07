from __future__ import annotations

from pathlib import Path
import unittest

from hs_lookup_app.certification import parse_certification_page


FIXTURE = Path(__file__).parent / "fixtures" / "rctest_wooden_toys.html"


class CertificationParserTest(unittest.TestCase):
    def test_parse_rctest_page_extracts_rich_sections(self) -> None:
        raw = FIXTURE.read_bytes()
        html = raw.decode("cp1251", errors="replace")
        result = parse_certification_page(
            html=html,
            source_url="https://www.rctest.ru/sertifikaciya-produkcii/igrushki/igrushki-iz-dereva/",
            fetched_at="2026-05-07T00:00:00+00:00",
        )

        self.assertIn("Сертификация", result.page_title_ru)
        self.assertTrue(result.summary_ru)
        self.assertGreaterEqual(len(result.intro_paragraphs_ru), 4)
        self.assertTrue(result.hero_image_url)
        self.assertGreaterEqual(len(result.stage_rows_ru), 4)
        self.assertGreaterEqual(len(result.document_groups_ru), 2)
        self.assertGreaterEqual(len(result.document_groups_ru[0].items), 1)
        self.assertGreaterEqual(len(result.similar_products_ru), 5)
        self.assertGreaterEqual(len(result.faq_items_ru), 1)


if __name__ == "__main__":
    unittest.main()
