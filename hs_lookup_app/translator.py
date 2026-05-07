from __future__ import annotations

from abc import ABC, abstractmethod

import requests


class Translator(ABC):
    @abstractmethod
    def translate_text(self, text: str, source_lang: str = "ru", target_lang: str = "zh-CN") -> str:
        raise NotImplementedError


class BaseTranslator(Translator):
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


class GoogleAjaxTranslator(BaseTranslator):
    URL = "https://translate.googleapis.com/translate_a/single"

    def translate_text(self, text: str, source_lang: str = "ru", target_lang: str = "zh-CN") -> str:
        text = (text or "").strip()
        if not text:
            return ""
        if source_lang == "ru" and target_lang == "zh-CN" and text in self.overrides:
            return self.overrides[text]

        try:
            response = self.session.get(
                self.URL,
                params={
                    "client": "gtx",
                    "sl": source_lang,
                    "tl": target_lang,
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


class MyMemoryTranslator(BaseTranslator):
    URL = "https://api.mymemory.translated.net/get"

    def translate_text(self, text: str, source_lang: str = "ru", target_lang: str = "zh-CN") -> str:
        text = (text or "").strip()
        if not text:
            return ""
        if source_lang == "ru" and target_lang == "zh-CN" and text in self.overrides:
            return self.overrides[text]

        try:
            response = self.session.get(
                self.URL,
                params={
                    "q": text,
                    "langpair": f"{source_lang}|{target_lang}",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            translated = (payload.get("responseData") or {}).get("translatedText", "").strip()
            return translated or text
        except Exception:
            return text


def build_translator(provider: str = "mymemory") -> Translator:
    provider_name = (provider or "mymemory").strip().lower()
    if provider_name == "google":
        return GoogleAjaxTranslator()
    return MyMemoryTranslator()
