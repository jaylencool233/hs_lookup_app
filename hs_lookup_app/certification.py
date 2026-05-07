from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from hs_lookup_app.errors import NotFoundError, ParseError
from hs_lookup_app.models import CertificationDocumentGroup, CertificationDocumentItem, ProductCertificationResult
from hs_lookup_app.translator import Translator, build_translator


def _clean_text(value: str) -> str:
    return " ".join((value or "").split())


def _to_absolute_url(url: str, base_url: str) -> str:
    value = (url or "").strip()
    if not value:
        return ""
    return urljoin(base_url, value)


def _extract_bg_image(style: str) -> str:
    if not style:
        return ""
    match = re.search(r"url\((['\"]?)(.*?)\1\)", style)
    if not match:
        return ""
    return match.group(2).strip()


def _collect_intro_paragraphs(section) -> list[str]:
    paragraphs: list[str] = []
    for tag in section.find_all("p", recursive=False):
        text = _clean_text(tag.get_text(" ", strip=True))
        if not text:
            continue
        if text.lower().startswith("дата публикации"):
            continue
        paragraphs.append(text)
    return paragraphs


def _collect_stage_rows(hidden_block) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if hidden_block is None:
        return rows
    for tr in hidden_block.select(".accordionMod table tr"):
        cells = [_clean_text(td.get_text(" ", strip=True)) for td in tr.select("th, td")]
        if len(cells) < 2:
            continue
        left, right = cells[0], cells[1]
        if left and right:
            rows.append((left, right))
    return rows


def _collect_faq(hidden_block) -> list[tuple[str, str]]:
    faq_items: list[tuple[str, str]] = []
    if hidden_block is None:
        return faq_items

    question_tag = hidden_block.select_one(".accordionMod [itemprop='name'], .accordionMod .accordion-toggle")
    answer_tag = hidden_block.select_one(".accordionMod [itemprop='acceptedAnswer'], .accordionMod .accordion-inner")
    question = _clean_text(question_tag.get_text(" ", strip=True)) if question_tag else ""
    answer = _clean_text(answer_tag.get_text(" ", strip=True)) if answer_tag else ""
    if question and answer:
        faq_items.append((question, answer))

    cta_title = hidden_block.select_one(".cta h2, .cta .h2")
    cta_text = hidden_block.select_one(".cta .cta__text")
    cta_q = _clean_text(cta_title.get_text(" ", strip=True)) if cta_title else ""
    cta_a = _clean_text(cta_text.get_text(" ", strip=True)) if cta_text else ""
    if cta_q and cta_a:
        faq_items.append((cta_q, cta_a))
    return faq_items


def _collect_document_groups(hidden_block, source_url: str) -> list[CertificationDocumentGroup]:
    groups: list[CertificationDocumentGroup] = []
    if hidden_block is None:
        return groups

    for shell in hidden_block.select("div.white-shell"):
        title_tag = shell.select_one(".h3.title")
        group_title = _clean_text(title_tag.get_text(" ", strip=True)) if title_tag else ""
        if not group_title:
            continue

        items: list[CertificationDocumentItem] = []
        for container in shell.select("a.bx_catalog_item_container"):
            item_title = _clean_text(container.get("title") or "")
            title_node = container.select_one(".bx_catalog_item_title")
            if not item_title and title_node is not None:
                item_title = _clean_text(title_node.get_text(" ", strip=True))
            href = _to_absolute_url(container.get("href") or "", source_url)

            image_url = ""
            image_holder = container.select_one(".bx_catalog_item_images")
            if image_holder is not None:
                image_url = _to_absolute_url(_extract_bg_image(image_holder.get("style") or ""), source_url)
            if item_title:
                items.append(CertificationDocumentItem(title=item_title, url=href, image_url=image_url))
        if items:
            groups.append(CertificationDocumentGroup(title=group_title, items=items))
    return groups


def _collect_similar_products(hidden_block, source_url: str) -> list[tuple[str, str, str]]:
    items: list[tuple[str, str, str]] = []
    if hidden_block is None:
        return items

    for product in hidden_block.select(".more .portfolio-item"):
        link = product.select_one("a.portfolio-item-link")
        title_tag = product.select_one(".portfolio-item-title")
        if link is None or title_tag is None:
            continue
        title = _clean_text(title_tag.get_text(" ", strip=True))
        href = _to_absolute_url(link.get("href") or "", source_url)
        image_url = ""
        img = product.select_one("img")
        if img is not None:
            raw_img = img.get("src") or img.get("data-src") or ""
            if "line-empty.png" not in raw_img:
                image_url = _to_absolute_url(raw_img, source_url)
        if title:
            items.append((title, href, image_url))
    return items


def _dedupe(items: list[str]) -> list[str]:
    output: list[str] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output


def _resolve_content_container(section):
    hidden_block = section.select_one("div.hidden-xs")
    if hidden_block is not None:
        return hidden_block
    return section


def parse_certification_page(html: str, source_url: str, fetched_at: str | None = None) -> ProductCertificationResult:
    soup = BeautifulSoup(html, "html.parser")

    section = soup.select_one("section.col-lg-8.col-md-8.col-sm-8.col-xs-12") or soup.find(
        "section",
        class_=lambda value: value and "col-lg-8" in value,
    )
    if section is None:
        raise ParseError("未找到认证主内容区")

    title_tag = section.find("h1") or soup.find("h1")
    if title_tag is None:
        raise ParseError("未找到认证页面标题")
    page_title_ru = _clean_text(title_tag.get_text(" ", strip=True))

    intro_paragraphs_ru = _collect_intro_paragraphs(section)
    summary_ru = ""
    for text in intro_paragraphs_ru:
        lowered = text.lower()
        if "требуется" in lowered or "соответств" in lowered:
            summary_ru = text
            break
    if not summary_ru and intro_paragraphs_ru:
        summary_ru = intro_paragraphs_ru[0]
    if not summary_ru:
        raise ParseError("未找到认证摘要")

    certificate_names_ru: list[str] = []
    for tag in section.select(".bx_catalog_item_title span, .bx_catalog_item_title"):
        text = _clean_text(tag.get_text(" ", strip=True))
        if text and text not in certificate_names_ru:
            certificate_names_ru.append(text)

    regulations = _dedupe(re.findall(r"ТР\s?(?:ТС|ЕАЭС)\s?\d+\s?/\s?\d{4}", section.get_text(" ", strip=True)))

    category_path_ru: list[str] = []
    for span in soup.select(".breadcrumb a, .breadcrumbs a, ul.vmenu_root a span"):
        text = _clean_text(span.get_text(" ", strip=True))
        if text and text not in category_path_ru:
            category_path_ru.append(text)

    hero_image_url = ""
    og_image = soup.select_one("meta[property='og:image']")
    if og_image is not None:
        hero_image_url = _to_absolute_url(og_image.get("content") or "", source_url)
    if not hero_image_url:
        first_doc = section.select_one(".white-shell .bx_catalog_item_images")
        if first_doc is not None:
            hero_image_url = _to_absolute_url(_extract_bg_image(first_doc.get("style") or ""), source_url)

    content_container = _resolve_content_container(section)
    stage_rows_ru = _collect_stage_rows(content_container)
    faq_items_ru = _collect_faq(content_container)
    document_groups_ru = _collect_document_groups(content_container, source_url=source_url)
    similar_products_ru = _collect_similar_products(content_container, source_url=source_url)

    timestamp = fetched_at or datetime.now(timezone.utc).isoformat()
    return ProductCertificationResult(
        query="",
        matched_keyword_ru="",
        matched_keyword_zh="",
        page_title_ru=page_title_ru,
        page_title_zh="",
        summary_ru=summary_ru,
        summary_zh="",
        certificate_names_ru=certificate_names_ru,
        certificate_names_zh=[],
        regulation_codes=regulations,
        source_url=source_url,
        fetched_at=timestamp,
        category_path_ru=category_path_ru,
        category_path_zh=[],
        hero_image_url=hero_image_url,
        intro_paragraphs_ru=intro_paragraphs_ru,
        intro_paragraphs_zh=[],
        stage_rows_ru=stage_rows_ru,
        stage_rows_zh=[],
        faq_items_ru=faq_items_ru,
        faq_items_zh=[],
        document_groups_ru=document_groups_ru,
        document_groups_zh=[],
        similar_products_ru=similar_products_ru,
        similar_products_zh=[],
    )


class RCTestCertificationService:
    INDEX = [
        {
            "keyword_ru": "игрушки из дерева",
            "keyword_zh": "木制玩具",
            "url": "https://www.rctest.ru/sertifikaciya-produkcii/igrushki/igrushki-iz-dereva/",
        },
        {
            "keyword_ru": "мягкие игрушки",
            "keyword_zh": "毛绒玩具",
            "url": "https://www.rctest.ru/sertifikaciya-produkcii/igrushki/myagkie-igrushki/",
        },
        {
            "keyword_ru": "игрушки с элементами питания",
            "keyword_zh": "带电池玩具",
            "url": "https://www.rctest.ru/sertifikaciya-produkcii/igrushki/igrushki-s-elementami-pitaniya/",
        },
    ]

    def __init__(self, translator: Translator | None = None, session=None, timeout: int = 20) -> None:
        self.translator = translator or build_translator("mymemory")
        self.session = session
        self.timeout = timeout
        self._cache: dict[str, ProductCertificationResult] = {}

    def _limit_summary(self, text: str, max_len: int = 220) -> str:
        compact = _clean_text(text)
        if len(compact) <= max_len:
            return compact
        return compact[: max_len - 1].rstrip() + "…"

    def _translate_texts(self, parsed: ProductCertificationResult, entry: dict) -> ProductCertificationResult:
        summary_ru = self._limit_summary(parsed.summary_ru)
        certificate_names_ru = parsed.certificate_names_ru[:3]
        category_path_ru = (parsed.category_path_ru or [])[-2:]
        intro_paragraphs_ru = parsed.intro_paragraphs_ru or []
        stage_rows_ru = parsed.stage_rows_ru or []
        faq_items_ru = parsed.faq_items_ru or []
        document_groups_ru = parsed.document_groups_ru or []
        similar_products_ru = parsed.similar_products_ru or []

        intro_paragraphs_zh = [self.translator.translate_text(item) for item in intro_paragraphs_ru]
        stage_rows_zh = [(self.translator.translate_text(label), value) for label, value in stage_rows_ru]
        faq_items_zh = [(self.translator.translate_text(q), self.translator.translate_text(a)) for q, a in faq_items_ru]
        document_groups_zh = [
            CertificationDocumentGroup(
                title=self.translator.translate_text(group.title),
                items=[
                    CertificationDocumentItem(
                        title=self.translator.translate_text(item.title),
                        url=item.url,
                        image_url=item.image_url,
                    )
                    for item in group.items
                ],
            )
            for group in document_groups_ru
        ]
        similar_products_zh = [
            (self.translator.translate_text(title), url, image_url)
            for title, url, image_url in similar_products_ru
        ]

        return ProductCertificationResult(
            query=entry["keyword_zh"],
            matched_keyword_ru=entry["keyword_ru"],
            matched_keyword_zh=entry["keyword_zh"],
            page_title_ru=parsed.page_title_ru,
            page_title_zh=self.translator.translate_text(parsed.page_title_ru),
            summary_ru=summary_ru,
            summary_zh=self.translator.translate_text(summary_ru),
            certificate_names_ru=certificate_names_ru,
            certificate_names_zh=[self.translator.translate_text(item) for item in certificate_names_ru],
            regulation_codes=parsed.regulation_codes,
            source_url=parsed.source_url,
            fetched_at=parsed.fetched_at,
            category_path_ru=category_path_ru,
            category_path_zh=[self.translator.translate_text(item) for item in category_path_ru],
            hero_image_url=parsed.hero_image_url,
            intro_paragraphs_ru=intro_paragraphs_ru,
            intro_paragraphs_zh=intro_paragraphs_zh,
            stage_rows_ru=stage_rows_ru,
            stage_rows_zh=stage_rows_zh,
            faq_items_ru=faq_items_ru,
            faq_items_zh=faq_items_zh,
            document_groups_ru=document_groups_ru,
            document_groups_zh=document_groups_zh,
            similar_products_ru=similar_products_ru,
            similar_products_zh=similar_products_zh,
        )

    def _match_entry(self, query: str) -> dict | None:
        query = query.strip().lower()
        if not query:
            return None
        for entry in self.INDEX:
            if query in entry["keyword_zh"] or query in entry["keyword_ru"]:
                return entry
        return None

    def lookup(self, query: str) -> ProductCertificationResult:
        cache_key = query.strip().lower()
        if cache_key in self._cache:
            return self._cache[cache_key]

        entry = self._match_entry(query)
        if entry is None:
            raise NotFoundError("未找到对应产品认证要求")

        import requests

        session = self.session or requests.Session()
        response = session.get(entry["url"], timeout=self.timeout)
        if response.status_code == 404:
            raise NotFoundError("未找到对应产品认证要求")
        response.raise_for_status()
        html = response.content.decode("cp1251", errors="replace")
        parsed = parse_certification_page(html=html, source_url=entry["url"])
        translated = self._translate_texts(parsed, entry)
        self._cache[cache_key] = translated
        return translated
