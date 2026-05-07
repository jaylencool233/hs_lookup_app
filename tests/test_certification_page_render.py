from __future__ import annotations

import unittest

from hs_lookup_app.models import CertificationDocumentGroup, CertificationDocumentItem, ProductCertificationResult
from hs_lookup_app.web import create_app


class _FakeCertificationService:
    def lookup(self, query: str) -> ProductCertificationResult:  # noqa: ARG002
        return ProductCertificationResult(
            query="木制玩具",
            matched_keyword_ru="игрушки из дерева",
            matched_keyword_zh="木制玩具",
            page_title_ru="Сертификация игрушек из дерева",
            page_title_zh="木制玩具认证",
            summary_ru="Требуется подтверждение соответствия.",
            summary_zh="需确认产品符合技术法规要求。",
            certificate_names_ru=["Сертификат соответствия"],
            certificate_names_zh=["合格证书"],
            regulation_codes=["ТР ТС 008/2011"],
            source_url="https://www.rctest.ru/sertifikaciya-produkcii/igrushki/igrushki-iz-dereva/",
            fetched_at="2026-05-07T00:00:00+00:00",
            category_path_ru=["Сертификация продукции", "Игрушки"],
            category_path_zh=["产品认证", "玩具"],
            hero_image_url="https://www.rctest.ru/upload/sample.png",
            intro_paragraphs_ru=["Параграф 1", "Параграф 2", "Параграф 3", "Параграф 4"],
            intro_paragraphs_zh=["段落1", "段落2", "段落3", "段落4"],
            stage_rows_ru=[("申请资料准备", "15 000"), ("测试", "26 400")],
            stage_rows_zh=[("申请资料准备", "15 000"), ("测试", "26 400")],
            faq_items_ru=[("还有疑问？", "请联系我们")],
            faq_items_zh=[("还有疑问？", "请联系我们")],
            document_groups_ru=[
                CertificationDocumentGroup(
                    title="符合EAEU技术法规",
                    items=[
                        CertificationDocumentItem(
                            title="木制玩具TR CU / EAEU合格证书",
                            url="https://www.rctest.ru/xx1",
                            image_url="https://www.rctest.ru/upload/doc1.jpg",
                        )
                    ],
                )
            ],
            document_groups_zh=[
                CertificationDocumentGroup(
                    title="符合EAEU技术法规",
                    items=[
                        CertificationDocumentItem(
                            title="木制玩具TR CU / EAEU合格证书",
                            url="https://www.rctest.ru/xx1",
                            image_url="https://www.rctest.ru/upload/doc1.jpg",
                        )
                    ],
                )
            ],
            similar_products_ru=[("Мягкие игрушки", "https://www.rctest.ru/sertifikaciya-produkcii/igrushki/myagkie-igrushki/", "")],
            similar_products_zh=[("毛绒玩具", "https://www.rctest.ru/sertifikaciya-produkcii/igrushki/myagkie-igrushki/", "")],
        )


class CertificationPageRenderTest(unittest.TestCase):
    def test_render_contains_rich_sections(self) -> None:
        app = create_app(certification_service=_FakeCertificationService())
        client = app.test_client()

        response = client.post("/lookup-certification", data={"query": "木制玩具"})
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("核心说明", body)
        self.assertIn("执行阶段", body)
        self.assertIn("更多信息", body)
        self.assertIn("相关产品", body)
        self.assertIn("https://www.rctest.ru/upload/sample.png", body)
        self.assertIn("查看完整图片", body)
        self.assertIn("image-preview-modal", body)
        self.assertIn("/?tab=certification", body)
        self.assertIn("返回查询", body)

    def test_index_contains_loading_overlay(self) -> None:
        app = create_app(certification_service=_FakeCertificationService())
        client = app.test_client()

        response = client.get("/")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("loading-overlay", body)
        self.assertIn("查询中，请稍候", body)
        self.assertIn("data-loading-form", body)
        self.assertIn("中文品名查HS", body)
        self.assertIn("data-search-panel", body)
        self.assertIn("data-search-tab", body)

    def test_name_lookup_result_page_renders_recommended_candidate(self) -> None:
        from hs_lookup_app.models import HsNameLookupResult, SearchMatch

        class _FakeHsService:
            def lookup(self, code: str):  # noqa: ARG002
                raise AssertionError("should not call code lookup in this test")

            def lookup_by_product_name(self, query: str) -> HsNameLookupResult:  # noqa: ARG002
                candidates = [
                    SearchMatch(code="9503004100", display_code="9503 00 410 0", name="Игрушки из дерева"),
                    SearchMatch(code="9503004900", display_code="9503 00 490 0", name="Прочие игрушки из дерева"),
                ]
                return HsNameLookupResult(
                    query_zh="木制玩具",
                    query_ru="игрушки из дерева",
                    recommended=candidates[0],
                    candidates=candidates,
                )

        app = create_app(service=_FakeHsService(), certification_service=_FakeCertificationService())
        client = app.test_client()

        response = client.post("/lookup-by-name", data={"product_name": "木制玩具"})
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("推荐结果", body)
        self.assertIn("игрушки из дерева", body)
        self.assertIn("9503 00 410 0", body)
        self.assertIn("/?tab=name", body)
        self.assertIn("返回查询", body)


if __name__ == "__main__":
    unittest.main()
