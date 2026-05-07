from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class NormalizedCode:
    raw: str
    compact: str
    display: str


@dataclass(frozen=True)
class SearchMatch:
    code: str
    display_code: str
    name: str


@dataclass(frozen=True)
class CategoryItem:
    code: str
    name: str


@dataclass(frozen=True)
class OkpdItem:
    code: str
    name: str


@dataclass(frozen=True)
class TaxSection:
    duty: str | None = None
    vat: str | None = None
    excise: str | None = None


@dataclass(frozen=True)
class Taxes:
    import_: TaxSection
    export: TaxSection


@dataclass(frozen=True)
class LookupResult:
    hs_code: str
    display_code: str
    name_ru: str
    name_zh: str
    category_path_ru: list[CategoryItem]
    category_path_zh: list[CategoryItem]
    okpd_ru: OkpdItem | None
    okpd_zh: OkpdItem | None
    taxes: Taxes
    source_url: str
    fetched_at: str

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["taxes"]["import"] = payload["taxes"].pop("import_")
        return payload

