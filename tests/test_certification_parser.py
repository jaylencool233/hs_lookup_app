from __future__ import annotations

from pathlib import Path
import unittest

from hs_lookup_app.certification import parse_certification_page


FIXTURE = Path(__file__).parent / "fixtures" / "rctest_wooden_toys.html"
BATTERY_FIXTURE = Path(__file__).parent / "fixtures" / "rctest_battery_toys.html"
SOFT_FIXTURE = Path(__file__).parent / "fixtures" / "rctest_soft_toys.html"


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

    def test_parse_battery_toys_page_extracts_all_document_groups(self) -> None:
        raw = BATTERY_FIXTURE.read_bytes()
        html = raw.decode("cp1251", errors="replace")
        result = parse_certification_page(
            html=html,
            source_url="https://www.rctest.ru/sertifikaciya-produkcii/igrushki/igrushki-s-elementami-pitaniya/",
            fetched_at="2026-05-08T00:00:00+00:00",
        )

        self.assertGreaterEqual(len(result.document_groups_ru or []), 4)
        self.assertEqual(sum(len(group.items) for group in result.document_groups_ru or []), 7)

    def test_parse_soft_toys_page_extracts_document_groups(self) -> None:
        raw = SOFT_FIXTURE.read_bytes()
        html = raw.decode("cp1251", errors="replace")
        result = parse_certification_page(
            html=html,
            source_url="https://www.rctest.ru/sertifikaciya-produkcii/igrushki/myagkie-igrushki/",
            fetched_at="2026-05-08T00:00:00+00:00",
        )

        self.assertGreaterEqual(len(result.document_groups_ru or []), 3)
        self.assertEqual(sum(len(group.items) for group in result.document_groups_ru or []), 5)
        self.assertGreaterEqual(len(result.certificate_names_ru), 5)


if __name__ == "__main__":
    unittest.main()
