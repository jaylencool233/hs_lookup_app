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
class HsNameLookupResult:
    query_zh: str
    query_ru: str
    recommended: SearchMatch
    candidates: list[SearchMatch]

    def to_dict(self) -> dict:
        return asdict(self)


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


@dataclass(frozen=True)
class ProductCertificationResult:
    query: str
    matched_keyword_ru: str
    matched_keyword_zh: str
    page_title_ru: str
    page_title_zh: str
    summary_ru: str
    summary_zh: str
    certificate_names_ru: list[str]
    certificate_names_zh: list[str]
    regulation_codes: list[str]
    source_url: str
    fetched_at: str
    category_path_ru: list[str] | None = None
    category_path_zh: list[str] | None = None
    hero_image_url: str = ""
    intro_paragraphs_ru: list[str] | None = None
    intro_paragraphs_zh: list[str] | None = None
    stage_rows_ru: list[tuple[str, str]] | None = None
    stage_rows_zh: list[tuple[str, str]] | None = None
    faq_items_ru: list[tuple[str, str]] | None = None
    faq_items_zh: list[tuple[str, str]] | None = None
    document_groups_ru: list["CertificationDocumentGroup"] | None = None
    document_groups_zh: list["CertificationDocumentGroup"] | None = None
    similar_products_ru: list[tuple[str, str, str]] | None = None
    similar_products_zh: list[tuple[str, str, str]] | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CertificationDocumentItem:
    title: str
    url: str
    image_url: str


@dataclass(frozen=True)
class CertificationDocumentGroup:
    title: str
    items: list[CertificationDocumentItem]
