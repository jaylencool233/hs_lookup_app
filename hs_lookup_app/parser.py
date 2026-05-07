from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup

from hs_lookup_app.errors import ParseError
from hs_lookup_app.models import CategoryItem, LookupResult, OkpdItem, TaxSection, Taxes


def _clean_text(value: str) -> str:
    return " ".join((value or "").split())


def _format_display_code(hs_code: str) -> str:
    compact = _clean_text(hs_code).replace(" ", "")
    if len(compact) == 10 and compact.isdigit():
        return f"{compact[:4]} {compact[4:6]} {compact[6:9]} {compact[9:]}"
    return _clean_text(hs_code)


def _extract_category_items(fieldset) -> list[CategoryItem]:
    items: list[CategoryItem] = []
    for item in fieldset.select("ul.pTnved_position li.pTnved_item"):
        code_tag = item.find("b")
        blocks = item.find_all("div")
        if not code_tag or len(blocks) < 2:
            continue
        code = _clean_text(code_tag.get_text(" ", strip=True))
        name = _clean_text(blocks[-1].get_text(" ", strip=True))
        items.append(CategoryItem(code=code, name=name))
    return items


def _extract_tax_section(fieldset) -> TaxSection:
    mapping: dict[str, str] = {}
    for row in fieldset.select("tr.pTnved_item"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        label = _clean_text(cells[0].get_text(" ", strip=True))
        primary_value = cells[1].select_one("b.black")
        if primary_value is not None:
            value = _clean_text(primary_value.get_text(" ", strip=True))
        else:
            value = _clean_text(cells[1].get_text(" ", strip=True))
        mapping[label] = value or None

    return TaxSection(
        duty=mapping.get("Базовая ставка таможенной пошлины"),
        vat=mapping.get("НДС"),
        excise=mapping.get("Акциз"),
    )


def parse_detail_page(html: str, source_url: str, fetched_at: str | None = None) -> LookupResult:
    soup = BeautifulSoup(html, "html.parser")

    code_tag = soup.select_one(".jCopyTnvedCode")
    if not code_tag:
        raise ParseError("未找到 HS 编码节点")

    hs_code = _clean_text(code_tag.get("data-original-code") or code_tag.get_text(" ", strip=True))
    display_code = _format_display_code(code_tag.get_text(" ", strip=True) or hs_code)

    title_box = code_tag.find_parent(class_="padding-default-2")
    name_tag = title_box.find("p") if title_box else None
    name_ru = _clean_text(name_tag.get_text(" ", strip=True)) if name_tag else ""
    if not name_ru:
        raise ParseError("未找到俄文品名")

    fieldsets = soup.find_all("fieldset")
    tnved_fieldset = None
    okpd_fieldset = None
    customs_fieldset = None
    for fieldset in fieldsets:
        legend = fieldset.find("legend")
        if not legend:
            continue
        legend_text = _clean_text(legend.get_text(" ", strip=True))
        if legend_text == "Позиция ТН ВЭД":
            tnved_fieldset = fieldset
        elif legend_text == "Позиция ОКПД 2":
            okpd_fieldset = fieldset
        elif legend_text == "Таможенные платежи":
            customs_fieldset = fieldset

    if tnved_fieldset is None or customs_fieldset is None:
        raise ParseError("详情页缺少关键结构")

    category_path_ru = _extract_category_items(tnved_fieldset)
    if not category_path_ru:
        raise ParseError("未找到分类路径")

    okpd_ru = None
    if okpd_fieldset is not None:
        okpd_items = _extract_category_items(okpd_fieldset)
        if okpd_items:
            okpd_ru = OkpdItem(code=okpd_items[0].code, name=okpd_items[0].name)

    nested_sections = customs_fieldset.find_all("fieldset", class_="pTnved_customs", recursive=False)
    import_section = TaxSection()
    export_section = TaxSection()
    for section in nested_sections:
        legend = section.find("legend")
        if not legend:
            continue
        legend_text = _clean_text(legend.get_text(" ", strip=True))
        if legend_text == "Импорт":
            import_section = _extract_tax_section(section)
        elif legend_text == "Экспорт":
            export_section = _extract_tax_section(section)

    timestamp = fetched_at or datetime.now(timezone.utc).isoformat()
    return LookupResult(
        hs_code=hs_code,
        display_code=display_code,
        name_ru=name_ru,
        name_zh="",
        category_path_ru=category_path_ru,
        category_path_zh=[],
        okpd_ru=okpd_ru,
        okpd_zh=None,
        taxes=Taxes(import_=import_section, export=export_section),
        source_url=source_url,
        fetched_at=timestamp,
    )


class AltaParser:
    def parse(self, html: str, source_url: str) -> LookupResult:
        return parse_detail_page(html=html, source_url=source_url)
