from __future__ import annotations

import requests


class GoogleAjaxTranslator:
    URL = "https://translate.googleapis.com/translate_a/single"

    def __init__(self, session: requests.Session | None = None, timeout: int = 20) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout
        self.overrides = {
            "Беспошлинно": "免税",
            "Не облагается": "不征税",
            "Импорт": "进口",
            "Экспорт": "出口",
            "Позиция ОКПД 2": "OKPD 2 分类",
        }

    def translate_text(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        if text in self.overrides:
            return self.overrides[text]

        try:
            response = self.session.get(
                self.URL,
                params={
                    "client": "gtx",
                    "sl": "ru",
                    "tl": "zh-CN",
                    "dt": "t",
                    "q": text,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            parts = [item[0] for item in payload[0] if item and item[0]]
            translated = "".join(parts).strip()
            return translated or text
        except Exception:
            return text

