from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from hs_lookup_app.client import AltaClient
from hs_lookup_app.errors import NotFoundError
from hs_lookup_app.models import CategoryItem, LookupResult, OkpdItem
from hs_lookup_app.normalizer import normalize_hs_code
from hs_lookup_app.parser import AltaParser
from hs_lookup_app.translator import GoogleAjaxTranslator


class HsLookupService:
    def __init__(
        self,
        alta_client: AltaClient | None = None,
        parser: AltaParser | None = None,
        translator: GoogleAjaxTranslator | None = None,
        cache_ttl_seconds: int = 3600,
    ) -> None:
        self.alta_client = alta_client or AltaClient()
        self.parser = parser or AltaParser()
        self.translator = translator or GoogleAjaxTranslator()
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

