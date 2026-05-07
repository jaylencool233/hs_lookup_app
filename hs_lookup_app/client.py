from __future__ import annotations

import requests

from hs_lookup_app.errors import NotFoundError, UpstreamError
from hs_lookup_app.models import SearchMatch


class AltaClient:
    SEARCH_URL = "https://www.alta.ru/tnved/search/"
    DETAIL_URL = "https://www.alta.ru/tnved/code/{code}/"

    def __init__(self, session: requests.Session | None = None, timeout: int = 20) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout

    def build_detail_url(self, compact_code: str) -> str:
        return self.DETAIL_URL.format(code=compact_code)

    def search_code(self, compact_code: str) -> SearchMatch | None:
        try:
            response = self.session.get(
                self.SEARCH_URL,
                params={"tnstr": compact_code},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise UpstreamError("Alta 搜索接口不可访问") from exc
        except ValueError as exc:
            raise UpstreamError("Alta 搜索接口返回了无效 JSON") from exc

        for item in payload:
            display_code = item.get("tnved", "")
            normalized = display_code.replace(" ", "")
            if normalized == compact_code:
                name = item.get("desc") or item.get("name") or ""
                return SearchMatch(code=compact_code, display_code=display_code, name=name)
        return None

    def search_product_name(self, keyword_ru: str) -> list[SearchMatch]:
        query = (keyword_ru or "").strip()
        if not query:
            return []

        try:
            response = self.session.get(
                self.SEARCH_URL,
                params={"tnstr": query},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise UpstreamError("Alta 搜索接口不可访问") from exc
        except ValueError as exc:
            raise UpstreamError("Alta 搜索接口返回了无效 JSON") from exc

        results: list[SearchMatch] = []
        for item in payload:
            display_code = item.get("tnved", "")
            compact_code = display_code.replace(" ", "")
            name = item.get("desc") or item.get("name") or ""
            if not compact_code or not name:
                continue
            results.append(
                SearchMatch(
                    code=compact_code,
                    display_code=display_code,
                    name=name,
                )
            )
        return results

    def fetch_detail_html(self, compact_code: str) -> str:
        try:
            response = self.session.get(self.build_detail_url(compact_code), timeout=self.timeout)
        except requests.RequestException as exc:
            raise UpstreamError("Alta 详情页暂时不可访问") from exc

        if response.status_code == 404:
            raise NotFoundError("未找到该 HS 编码的公开信息")
        if response.status_code >= 400:
            raise UpstreamError("Alta 详情页返回异常状态")

        response.encoding = "utf-8"
        return response.text
