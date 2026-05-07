from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import re

from hs_lookup_app.client import AltaClient
from hs_lookup_app.errors import NotFoundError, ValidationError
from hs_lookup_app.models import CategoryItem, HsNameLookupResult, LookupResult, OkpdItem, SearchMatch
from hs_lookup_app.normalizer import normalize_hs_code
from hs_lookup_app.parser import AltaParser
from hs_lookup_app.translator import Translator, build_translator


class HsLookupService:
    STOP_WORDS = {
        "и",
        "в",
        "во",
        "на",
        "из",
        "для",
        "по",
        "с",
        "со",
        "к",
        "ко",
        "о",
        "об",
        "от",
        "до",
        "под",
        "над",
    }
    NAME_SUFFIXES = (
        "ными",
        "ными",
        "овыми",
        "евыми",
        "ыми",
        "ими",
        "ого",
        "ему",
        "ому",
        "ыми",
        "ыми",
        "ая",
        "яя",
        "ое",
        "ее",
        "ый",
        "ий",
        "ой",
        "ую",
        "юю",
        "ым",
        "им",
        "ом",
        "ем",
        "ых",
        "их",
        "ые",
        "ие",
        "а",
        "я",
        "ы",
        "и",
        "у",
        "ю",
        "о",
        "е",
        "ов",
        "ев",
    )

    def __init__(
        self,
        alta_client: AltaClient | None = None,
        parser: AltaParser | None = None,
        translator: Translator | None = None,
        cache_ttl_seconds: int = 3600,
    ) -> None:
        self.alta_client = alta_client or AltaClient()
        self.parser = parser or AltaParser()
        self.translator = translator or build_translator("mymemory")
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[str, tuple[datetime, LookupResult]] = {}

    def _translate_value(self, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if any(char.isdigit() for char in value) or "%" in value:
            return value
        return self.translator.translate_text(value)

    def _score_candidate(self, keyword_ru: str, candidate: SearchMatch) -> tuple[int, int, int]:
        normalized_query = " ".join(keyword_ru.lower().split())
        normalized_name = " ".join((candidate.name or "").lower().split())
        query_words = [word for word in re.split(r"\s+", normalized_query) if word]
        whole_match = 1 if normalized_query and normalized_query in normalized_name else 0
        matched_words = sum(1 for word in query_words if word in normalized_name)
        shorter_name_bonus = -len(normalized_name)
        return (whole_match, matched_words, shorter_name_bonus)

    def _normalize_search_term(self, term: str) -> str:
        return " ".join((term or "").lower().split()).strip()

    def _strip_suffixes(self, word: str) -> list[str]:
        variants: list[str] = []
        for suffix in self.NAME_SUFFIXES:
            if word.endswith(suffix) and len(word) - len(suffix) >= 4:
                stem = word[: -len(suffix)]
                if stem and stem not in variants:
                    variants.append(stem)
                if stem.endswith("н") and len(stem) > 4:
                    trimmed = stem[:-1]
                    if trimmed not in variants:
                        variants.append(trimmed)
        return variants

    def _build_search_terms(self, query_ru: str) -> list[str]:
        normalized = self._normalize_search_term(query_ru)
        if not normalized:
            return []

        terms: list[str] = [normalized]
        tokens = [token for token in re.split(r"\s+", normalized) if token and token not in self.STOP_WORDS]

        for token in tokens:
            if token not in terms:
                terms.append(token)
            for variant in self._strip_suffixes(token):
                if variant not in terms:
                    terms.append(variant)

        if len(tokens) > 1:
            collapsed = " ".join(tokens)
            if collapsed not in terms:
                terms.append(collapsed)

        return terms

    def lookup(self, raw_code: str) -> LookupResult:
        normalized = normalize_hs_code(raw_code)
        cached = self._cache.get(normalized.compact)
        if cached:
            cached_at, result = cached
            if datetime.now() - cached_at < timedelta(seconds=self.cache_ttl_seconds):
                return result

        search_match = self.alta_client.search_code(normalized.compact)
        if search_match is None:
            raise NotFoundError("未找到该 HS 编码的公开信息")

        html = self.alta_client.fetch_detail_html(normalized.compact)
        parsed = self.parser.parse(html, self.alta_client.build_detail_url(normalized.compact))

        category_path_zh = [
            CategoryItem(code=item.code, name=self.translator.translate_text(item.name))
            for item in parsed.category_path_ru
        ]
        okpd_zh = None
        if parsed.okpd_ru is not None:
            okpd_zh = OkpdItem(
                code=parsed.okpd_ru.code,
                name=self.translator.translate_text(parsed.okpd_ru.name),
            )

        translated = replace(
            parsed,
            display_code=normalized.display,
            name_zh=self.translator.translate_text(parsed.name_ru),
            category_path_zh=category_path_zh,
            okpd_zh=okpd_zh,
            taxes=replace(
                parsed.taxes,
                import_=replace(
                    parsed.taxes.import_,
                    duty=self._translate_value(parsed.taxes.import_.duty),
                    vat=self._translate_value(parsed.taxes.import_.vat),
                    excise=self._translate_value(parsed.taxes.import_.excise),
                ),
                export=replace(
                    parsed.taxes.export,
                    duty=self._translate_value(parsed.taxes.export.duty),
                    vat=self._translate_value(parsed.taxes.export.vat),
                    excise=self._translate_value(parsed.taxes.export.excise),
                ),
            ),
        )
        self._cache[normalized.compact] = (datetime.now(), translated)
        return translated

    def lookup_by_product_name(self, product_name_zh: str) -> HsNameLookupResult:
        query_zh = (product_name_zh or "").strip()
        if not query_zh:
            raise ValidationError("请输入中文品名")

        query_ru = self.translator.translate_text(
            query_zh,
            source_lang="zh-CN",
            target_lang="ru",
        ).strip()
        if not query_ru or query_ru == query_zh:
            raise NotFoundError("俄文翻译失败，请尝试更具体的中文品名")

        candidates: list[SearchMatch] = []
        seen_codes: set[str] = set()
        for term in self._build_search_terms(query_ru):
            matches = self.alta_client.search_product_name(term)
            for match in matches:
                if match.code in seen_codes:
                    continue
                seen_codes.add(match.code)
                candidates.append(match)

        if not candidates:
            raise NotFoundError("未找到匹配的公开 HS 候选，请尝试更完整或更专业的品名")

        ranked = sorted(
            candidates,
            key=lambda item: self._score_candidate(query_ru, item),
            reverse=True,
        )
        return HsNameLookupResult(
            query_zh=query_zh,
            query_ru=query_ru,
            recommended=ranked[0],
            candidates=ranked,
        )
