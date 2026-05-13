from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
import re

import pymysql

from hs_lookup_app.errors import UpstreamError
from hs_lookup_app.models import CategoryItem, LookupResult, TaxSection, Taxes


@dataclass(frozen=True)
class DbCandidate:
    code: str
    display_code: str
    name_ru: str
    name_zh: str


def _compact_digits(value: str | None) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _display_code(compact_code: str) -> str:
    if len(compact_code) == 10:
        return f"{compact_code[:4]} {compact_code[4:6]} {compact_code[6:9]} {compact_code[9:]}"
    return compact_code


def _parse_timestamp(raw_value: str | None) -> str:
    value = (raw_value or "").strip()
    if value.isdigit():
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


class TnvedRepository:
    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
        connect_timeout: int = 5,
    ) -> None:
        self.host = host or os.getenv("MYSQL_HOST")
        self.port = port or int(os.getenv("MYSQL_PORT", "3306"))
        self.user = user or os.getenv("MYSQL_USER")
        self.password = password or os.getenv("MYSQL_PASSWORD")
        self.database = database or os.getenv("MYSQL_DATABASE")
        self.connect_timeout = connect_timeout

    def _is_configured(self) -> bool:
        return all([self.host, self.port, self.user, self.password, self.database])

    def _connect(self):
        if not self._is_configured():
            return None
        try:
            return pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=self.connect_timeout,
                autocommit=True,
            )
        except pymysql.MySQLError as exc:
            raise UpstreamError("数据库连接失败，请稍后重试") from exc

    def find_detail_by_code(self, code: str) -> LookupResult | None:
        connection = self._connect()
        if connection is None:
            return None

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, code, category, category_cn, ICDR, IVAT, ECDR, EET, `update`
                    FROM tnved
                    WHERE REPLACE(REPLACE(REPLACE(code, ' ', ''), '.', ''), '-', '') REGEXP %s
                    ORDER BY LENGTH(REPLACE(REPLACE(REPLACE(code, ' ', ''), '.', ''), '-', '')) DESC, id DESC
                    LIMIT 1
                    """,
                    (f"^{re.escape(code)}$",),
                )
                detail = cursor.fetchone()
                if not detail:
                    return None

                cursor.execute(
                    """
                    SELECT code, category, category_cn, level
                    FROM tnved
                    WHERE code IS NOT NULL
                    ORDER BY level ASC, id ASC
                    """
                )
                rows = cursor.fetchall()
        except pymysql.MySQLError as exc:
            raise UpstreamError("数据库查询失败，请稍后重试") from exc
        finally:
            connection.close()

        path_ru: list[CategoryItem] = []
        path_zh: list[CategoryItem] = []
        for row in rows:
            compact = _compact_digits(row.get("code"))
            if not compact or not code.startswith(compact):
                continue
            code_label = (row.get("code") or "").strip()
            path_ru.append(CategoryItem(code=code_label, name=(row.get("category") or "").strip()))
            path_zh.append(CategoryItem(code=code_label, name=(row.get("category_cn") or "").strip()))

        return LookupResult(
            hs_code=code,
            display_code=_display_code(code),
            name_ru=(detail.get("category") or "").strip(),
            name_zh=(detail.get("category_cn") or "").strip(),
            category_path_ru=path_ru,
            category_path_zh=path_zh,
            okpd_ru=None,
            okpd_zh=None,
            taxes=Taxes(
                import_=TaxSection(
                    duty=(detail.get("ICDR") or "").strip() or None,
                    vat=(detail.get("IVAT") or "").strip() or None,
                    excise=None,
                ),
                export=TaxSection(
                    duty=(detail.get("ECDR") or "").strip() or None,
                    vat=None,
                    excise=(detail.get("EET") or "").strip() or None,
                ),
            ),
            source_url=f"https://www.alta.ru/tnved/code/{code}/",
            fetched_at=_parse_timestamp(detail.get("update")),
        )

    def search_candidates_by_keyword(self, keyword: str) -> list[DbCandidate]:
        query = (keyword or "").strip()
        if not query:
            return []

        connection = self._connect()
        if connection is None:
            return []

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT code, category, category_cn
                    FROM tnved
                    WHERE level IS NOT NULL
                      AND (
                        category_cn LIKE %s
                        OR category LIKE %s
                      )
                    ORDER BY LENGTH(REPLACE(REPLACE(code, ' ', ''), '.', '')) DESC, id ASC
                    LIMIT 20
                    """,
                    (f"%{query}%", f"%{query}%"),
                )
                rows = cursor.fetchall()
        except pymysql.MySQLError as exc:
            raise UpstreamError("数据库查询失败，请稍后重试") from exc
        finally:
            connection.close()

        results: list[DbCandidate] = []
        seen_codes: set[str] = set()
        for row in rows:
            compact = _compact_digits(row.get("code"))
            if len(compact) != 10 or compact in seen_codes:
                continue
            seen_codes.add(compact)
            results.append(
                DbCandidate(
                    code=compact,
                    display_code=_display_code(compact),
                    name_ru=(row.get("category") or "").strip(),
                    name_zh=(row.get("category_cn") or "").strip(),
                )
            )
        return results

    def upsert_lookup_result(self, result: LookupResult) -> None:
        connection = self._connect()
        if connection is None:
            return

        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, category_cn, ICDR, IVAT, ECDR, EET
                    FROM tnved
                    WHERE REPLACE(REPLACE(REPLACE(code, ' ', ''), '.', ''), '-', '') REGEXP %s
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (f"^{re.escape(result.hs_code)}$",),
                )
                existing = cursor.fetchone()
                if existing:
                    cursor.execute(
                        """
                        UPDATE tnved
                        SET category_cn = COALESCE(NULLIF(category_cn, ''), %s),
                            ICDR = COALESCE(NULLIF(ICDR, ''), %s),
                            IVAT = COALESCE(NULLIF(IVAT, ''), %s),
                            ECDR = COALESCE(NULLIF(ECDR, ''), %s),
                            EET = COALESCE(NULLIF(EET, ''), %s),
                            `update` = %s
                        WHERE id = %s
                        """,
                        (
                            result.name_zh,
                            result.taxes.import_.duty,
                            result.taxes.import_.vat,
                            result.taxes.export.duty,
                            result.taxes.export.excise,
                            timestamp,
                            existing["id"],
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO tnved (`code`, `category`, `level`, `category_cn`, `ICDR`, `IVAT`, `ECDR`, `EET`, `update`)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            result.display_code,
                            result.name_ru,
                            len(result.category_path_ru),
                            result.name_zh,
                            result.taxes.import_.duty,
                            result.taxes.import_.vat,
                            result.taxes.export.duty,
                            result.taxes.export.excise,
                            timestamp,
                        ),
                    )
        except pymysql.MySQLError as exc:
            raise UpstreamError("数据库写入失败，请稍后重试") from exc
        finally:
            connection.close()
