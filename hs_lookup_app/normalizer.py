from __future__ import annotations

import re

from hs_lookup_app.errors import ValidationError
from hs_lookup_app.models import NormalizedCode


def normalize_hs_code(raw_code: str) -> NormalizedCode:
    compact = re.sub(r"\s+", "", (raw_code or "").strip())
    if not compact:
        raise ValidationError("请输入10位HS编码")
    if not compact.isdigit():
        raise ValidationError("HS编码格式不正确，请输入10位数字")
    if len(compact) != 10:
        raise ValidationError("HS编码格式不正确，请输入10位数字")

    display = f"{compact[:4]} {compact[4:6]} {compact[6:9]} {compact[9:]}"
    return NormalizedCode(raw=raw_code, compact=compact, display=display)

