from __future__ import annotations

import json

from flask import Flask, Response, render_template, request

from hs_lookup_app.errors import HsLookupError, NotFoundError, UpstreamError, ValidationError
from hs_lookup_app.service import HsLookupService


def _error_message(exc: Exception) -> str:
    if isinstance(exc, (ValidationError, NotFoundError, UpstreamError)):
        return str(exc)
    if isinstance(exc, HsLookupError):
        return str(exc)
    return "查询失败，请稍后重试"


def create_app(service: HsLookupService | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates")
    hs_service = service or HsLookupService()

    @app.get("/")
    def index():
        return render_template("index.html", error=None, code="")

    @app.post("/lookup")
    def lookup():
        code = request.form.get("code", "")
        try:
            result = hs_service.lookup(code)
            return render_template("result.html", result=result, error=None)
        except Exception as exc:  # noqa: BLE001
            return render_template("index.html", error=_error_message(exc), code=code), 400

    @app.get("/api/hs-lookup")
    def api_lookup():
        code = request.args.get("code", "")
        try:
            result = hs_service.lookup(code)
            payload = {"success": True, "data": result.to_dict(), "message": ""}
            return Response(
                json.dumps(payload, ensure_ascii=True),
                mimetype="application/json",
            )
        except Exception as exc:  # noqa: BLE001
            payload = {"success": False, "message": _error_message(exc)}
            status = 400 if isinstance(exc, HsLookupError) else 500
            return Response(
                json.dumps(payload, ensure_ascii=True),
                status=status,
                mimetype="application/json",
            )

    return app

