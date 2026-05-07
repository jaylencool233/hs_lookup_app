from __future__ import annotations

import json

from flask import Flask, Response, render_template, request

from hs_lookup_app.certification import RCTestCertificationService
from hs_lookup_app.errors import HsLookupError, NotFoundError, UpstreamError, ValidationError
from hs_lookup_app.service import HsLookupService


def _error_message(exc: Exception) -> str:
    if isinstance(exc, (ValidationError, NotFoundError, UpstreamError)):
        return str(exc)
    if isinstance(exc, HsLookupError):
        return str(exc)
    return "查询失败，请稍后重试"


def create_app(
    service: HsLookupService | None = None,
    certification_service: RCTestCertificationService | None = None,
) -> Flask:
    app = Flask(__name__, template_folder="templates")
    hs_service = service or HsLookupService()
    cert_service = certification_service or RCTestCertificationService()

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            error=None,
            code="",
            product_name="",
            cert_query="",
            active_tab="hs",
        )

    @app.post("/lookup")
    def lookup():
        code = request.form.get("code", "")
        try:
            result = hs_service.lookup(code)
            return render_template("result.html", result=result, error=None, active_tab="hs")
        except Exception as exc:  # noqa: BLE001
            return render_template(
                "index.html",
                error=_error_message(exc),
                code=code,
                product_name="",
                cert_query="",
                active_tab="hs",
            ), 400

    @app.get("/lookup")
    def lookup_get():
        code = request.args.get("code", "")
        try:
            result = hs_service.lookup(code)
            return render_template("result.html", result=result, error=None, active_tab="hs")
        except Exception as exc:  # noqa: BLE001
            return render_template(
                "index.html",
                error=_error_message(exc),
                code=code,
                product_name="",
                cert_query="",
                active_tab="hs",
            ), 400

    @app.post("/lookup-by-name")
    def lookup_by_name():
        product_name = request.form.get("product_name", "")
        try:
            result = hs_service.lookup_by_product_name(product_name)
            return render_template("name_search_result.html", result=result, error=None, active_tab="name")
        except Exception as exc:  # noqa: BLE001
            return render_template(
                "index.html",
                error=_error_message(exc),
                code="",
                product_name=product_name,
                cert_query="",
                active_tab="name",
            ), 400

    @app.post("/lookup-certification")
    def lookup_certification():
        query = request.form.get("query", "")
        try:
            result = cert_service.lookup(query)
            return render_template("certification_result.html", result=result, error=None, active_tab="certification")
        except Exception as exc:  # noqa: BLE001
            return render_template(
                "index.html",
                error=_error_message(exc),
                code="",
                product_name="",
                cert_query=query,
                active_tab="certification",
            ), 400

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

    @app.get("/api/certification-lookup")
    def api_certification_lookup():
        query = request.args.get("query", "")
        try:
            result = cert_service.lookup(query)
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

    @app.get("/api/hs-name-lookup")
    def api_hs_name_lookup():
        product_name = request.args.get("product_name", "")
        try:
            result = hs_service.lookup_by_product_name(product_name)
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
