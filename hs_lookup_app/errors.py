class HsLookupError(Exception):
    """基础业务错误。"""


class ValidationError(HsLookupError):
    """输入校验失败。"""


class NotFoundError(HsLookupError):
    """上游未找到对应编码。"""


class UpstreamError(HsLookupError):
    """上游请求失败。"""


class ParseError(HsLookupError):
    """详情页解析失败。"""

