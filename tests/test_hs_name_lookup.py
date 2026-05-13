from __future__ import annotations

from dataclasses import dataclass
import unittest

from hs_lookup_app.models import LookupResult, SearchMatch
from hs_lookup_app.service import HsLookupService


class _FakeTranslator:
    def translate_text(self, text: str, source_lang: str = "ru", target_lang: str = "zh-CN") -> str:
        mapping = {
            "木制玩具": "игрушки из дерева",
            "毛绒玩具": "мягкие игрушки",
            "聚酯短纤维机织布": "ткань из полиэфирных штапельных волокон",
        }
        if source_lang == "zh-CN" and target_lang == "ru":
            return mapping.get(text, text)
        return text


class _FakeAltaClient:
    def search_product_name(self, keyword_ru: str) -> list[SearchMatch]:
        if keyword_ru == "игрушки из дерева":
            return [
                SearchMatch(code="9503004100", display_code="9503 00 410 0", name="Игрушки из дерева"),
                SearchMatch(code="9503004900", display_code="9503 00 490 0", name="Прочие игрушки из дерева"),
                SearchMatch(code="9503002100", display_code="9503 00 210 0", name="Куклы и игрушки"),
            ]
        if keyword_ru == "ткань из полиэфирных штапельных волокон":
            return [
                SearchMatch(code="5512199000", display_code="5512 19 900 0", name="Ткань из полиэфирных штапельных волокон"),
            ]
        return []


class _FallbackAltaClient:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def search_product_name(self, keyword_ru: str) -> list[SearchMatch]:
        self.queries.append(keyword_ru)
        if keyword_ru == "полиэфир":
            return [
                SearchMatch(code="5512199000", display_code="5512 19 900 0", name="Ткань из полиэфирных волокон"),
            ]
        return []


@dataclass
class _FakeDbCandidate:
    code: str
    display_code: str
    name_ru: str
    name_zh: str


class _FakeRepository:
    def __init__(self) -> None:
        self.detail_result: LookupResult | None = None
        self.candidates: list[_FakeDbCandidate] = []
        self.saved_results: list[LookupResult] = []
        self.detail_queries: list[str] = []
        self.keyword_queries: list[str] = []

    def find_detail_by_code(self, code: str) -> LookupResult | None:
        self.detail_queries.append(code)
        return self.detail_result

    def search_candidates_by_keyword(self, keyword: str) -> list[_FakeDbCandidate]:
        self.keyword_queries.append(keyword)
        return self.candidates

    def upsert_lookup_result(self, result: LookupResult) -> None:
        self.saved_results.append(result)


class _NeverCalledAltaClient:
    def search_code(self, compact_code: str):
        raise AssertionError(f"should not call search_code for {compact_code}")

    def fetch_detail_html(self, compact_code: str):
        raise AssertionError(f"should not call fetch_detail_html for {compact_code}")

    def search_product_name(self, keyword_ru: str):
        raise AssertionError(f"should not call search_product_name for {keyword_ru}")


class HsNameLookupServiceTest(unittest.TestCase):
    def test_lookup_by_chinese_name_returns_ranked_candidates(self) -> None:
        service = HsLookupService(alta_client=_FakeAltaClient(), translator=_FakeTranslator())

        result = service.lookup_by_product_name("木制玩具")

        self.assertEqual(result.query_zh, "木制玩具")
        self.assertEqual(result.query_ru, "игрушки из дерева")
        self.assertEqual(result.recommended.code, "9503004100")
        self.assertGreaterEqual(len(result.candidates), 3)
        self.assertEqual(result.candidates[0].code, result.recommended.code)

    def test_lookup_by_chinese_name_translates_from_zh_to_ru(self) -> None:
        service = HsLookupService(alta_client=_FakeAltaClient(), translator=_FakeTranslator())

        result = service.lookup_by_product_name("聚酯短纤维机织布")

        self.assertEqual(result.query_ru, "ткань из полиэфирных штапельных волокон")
        self.assertEqual(result.recommended.code, "5512199000")

    def test_lookup_by_chinese_name_tries_fallback_keywords(self) -> None:
        client = _FallbackAltaClient()
        service = HsLookupService(alta_client=client, translator=_FakeTranslator())

        result = service.lookup_by_product_name("聚酯短纤维机织布")

        self.assertIn("ткань из полиэфирных штапельных волокон", client.queries)
        self.assertIn("полиэфир", client.queries)
        self.assertEqual(result.recommended.code, "5512199000")

    def test_lookup_prefers_database_detail_without_calling_alta(self) -> None:
        repo = _FakeRepository()
        repo.detail_result = LookupResult(
            hs_code="9503004100",
            display_code="9503 00 410 0",
            name_ru="Игрушки из дерева",
            name_zh="木制玩具",
            category_path_ru=[],
            category_path_zh=[],
            okpd_ru=None,
            okpd_zh=None,
            taxes=None,  # type: ignore[arg-type]
            source_url="https://www.alta.ru/tnved/code/9503004100/",
            fetched_at="2026-05-13T00:00:00+00:00",
        )
        service = HsLookupService(
            alta_client=_NeverCalledAltaClient(),
            translator=_FakeTranslator(),
            repository=repo,
        )

        result = service.lookup("9503004100")

        self.assertEqual(result.name_zh, "木制玩具")
        self.assertEqual(repo.detail_queries, ["9503004100"])

    def test_lookup_by_product_name_prefers_database_candidates(self) -> None:
        repo = _FakeRepository()
        repo.candidates = [
            _FakeDbCandidate(
                code="9503004100",
                display_code="9503 00 410 0",
                name_ru="Игрушки из дерева",
                name_zh="木制玩具",
            )
        ]
        service = HsLookupService(
            alta_client=_NeverCalledAltaClient(),
            translator=_FakeTranslator(),
            repository=repo,
        )

        result = service.lookup_by_product_name("木制玩具")

        self.assertEqual(result.recommended.code, "9503004100")
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(repo.keyword_queries, ["木制玩具"])


if __name__ == "__main__":
    unittest.main()
