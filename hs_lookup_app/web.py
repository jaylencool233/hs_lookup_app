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
        tab = request.args.get("tab", "lookup").strip().lower()
        if tab not in {"lookup", "certification"}:
            tab = "lookup"
        return render_template(
            "index.html",
            error=None,
            query="",
            cert_query="",
            active_tab=tab,
            candidate_result=None,
            open_candidate_modal=False,
        )

    @app.post("/lookup")
    def lookup():
        code = request.form.get("code", "")
        try:
            result = hs_service.lookup(code)
            return render_template("result.html", result=result, error=None, active_tab="lookup")
        except Exception as exc:  # noqa: BLE001
            return render_template(
                "index.html",
                error=_error_message(exc),
                query=code,
                cert_query="",
                active_tab="lookup",
                candidate_result=None,
                open_candidate_modal=False,
            ), 400

    @app.get("/lookup")
    def lookup_get():
        code = request.args.get("code", "")
        try:
            result = hs_service.lookup(code)
            return render_template("result.html", result=result, error=None, active_tab="lookup")
        except Exception as exc:  # noqa: BLE001
            return render_template(
                "index.html",
                error=_error_message(exc),
                query=code,
                cert_query="",
                active_tab="lookup",
                candidate_result=None,
                open_candidate_modal=False,
            ), 400

    @app.post("/lookup-unified")
    def lookup_unified():
        query = request.form.get("query", "")
        try:
            payload = hs_service.lookup_unified(query)
            if payload["mode"] == "detail":
                return render_template("result.html", result=payload["result"], error=None, active_tab="lookup")
            return render_template(
                "index.html",
                error=None,
                query=query,
                cert_query="",
                active_tab="lookup",
                candidate_result=payload["result"],
                open_candidate_modal=True,
            )
        except Exception as exc:  # noqa: BLE001
            return render_template(
                "index.html",
                error=_error_message(exc),
                query=query,
                cert_query="",
                active_tab="lookup",
                candidate_result=None,
                open_candidate_modal=False,
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
                query="",
                cert_query=query,
                active_tab="certification",
                candidate_result=None,
                open_candidate_modal=False,
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

    @app.get("/api/hs-search")
    def api_hs_search():
        query = request.args.get("query", "")
        try:
            result = hs_service.lookup_unified(query)
            data = result["result"].to_dict() if hasattr(result["result"], "to_dict") else result["result"]
            payload = {"success": True, "mode": result["mode"], "data": data, "message": ""}
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
