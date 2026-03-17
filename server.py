#!/usr/bin/env python3
import base64
import json
import mimetypes
import os
import subprocess
import tempfile
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from backend.catalog import BASE_PACKAGE_CATALOG
from backend.llm import get_llm_status, parse_plan_with_mode
from backend.packaging import generate_weekly_needs, resolve_packages
from backend.plan import normalize_plan
from backend.storage import load_state, save_package_overrides, save_plan


ROOT_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = ROOT_DIR / "public"
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "3000"))
STATE = load_state()


class AppHandler(BaseHTTPRequestHandler):
    server_version = "DietShoppingAssistantPython/0.1"

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/state":
            self.send_json(
                HTTPStatus.OK,
                {
                    **STATE,
                    "capabilities": {
                        "llm": get_llm_status(),
                    },
                },
            )
            return

        if parsed.path == "/api/catalog":
            self.send_json(
                HTTPStatus.OK,
                {
                    "catalog": BASE_PACKAGE_CATALOG,
                    "overrides": STATE.get("packageOverrides", {}),
                },
            )
            return

        self.serve_static(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)

        try:
            body = self.read_json_body()

            if parsed.path == "/api/plan/parse":
                plan_text = resolve_plan_text(body)
                started_at = time.monotonic()
                parsed_plan = parse_plan_with_mode(plan_text, mode=body.get("parserMode"))
                metadata = parsed_plan.setdefault("parseMetadata", {})
                metadata["totalDurationMs"] = round((time.monotonic() - started_at) * 1000)
                save_plan(parsed_plan)
                STATE["lastPlan"] = parsed_plan
                self.send_json(HTTPStatus.OK, {"plan": parsed_plan})
                return

            if parsed.path == "/api/plan/review":
                reviewed_plan = normalize_plan(body.get("plan"), default_status="reviewed", parse_strategy="reviewed")
                reviewed_plan["status"] = "reviewed"
                save_plan(reviewed_plan)
                STATE["lastPlan"] = reviewed_plan
                self.send_json(HTTPStatus.OK, {"plan": reviewed_plan})
                return

            if parsed.path == "/api/shopping-list":
                if body.get("packageOverrides"):
                    STATE["packageOverrides"] = body["packageOverrides"]
                    save_package_overrides(STATE["packageOverrides"])

                reviewed_plan = normalize_plan(body.get("plan"), default_status="reviewed", parse_strategy="reviewed")
                weekly_needs = generate_weekly_needs(reviewed_plan["items"])
                shopping_list = resolve_packages(weekly_needs, STATE.get("packageOverrides"))
                response = {
                    "plan": reviewed_plan,
                    "weeklyNeeds": weekly_needs,
                    "shoppingList": shopping_list,
                }
                save_plan(reviewed_plan)
                STATE["lastPlan"] = reviewed_plan
                self.send_json(HTTPStatus.OK, response)
                return

            self.send_error_json(HTTPStatus.NOT_FOUND, "Rota nao encontrada.")
        except Exception as error:
            self.send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(error) or "Erro interno.")

    def serve_static(self, raw_path):
        safe_path = "/index.html" if raw_path == "/" else unquote(raw_path)
        target = (PUBLIC_DIR / safe_path.lstrip("/")).resolve()

        if not str(target).startswith(str(PUBLIC_DIR.resolve())) or not target.exists() or target.is_dir():
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") or content_type.endswith("javascript") else content_type)
        self.end_headers()
        self.wfile.write(target.read_bytes())

    def read_json_body(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length > 5 * 1024 * 1024:
            raise ValueError("Payload muito grande.")

        raw = self.rfile.read(content_length) if content_length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("JSON invalido.") from error

    def send_json(self, status_code, payload):
        response = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def send_error_json(self, status_code, message):
        self.send_json(status_code, {"error": message})

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}")


def resolve_plan_text(body):
    text = str(body.get("text") or "").strip()
    if text:
        return text

    file_content = body.get("fileContentBase64")
    if not file_content:
        raise ValueError("Envie um texto ou arquivo.")

    buffer = base64.b64decode(file_content)
    mime_type = body.get("mimeType") or ""
    file_name = body.get("fileName") or "arquivo"

    if "pdf" in mime_type.lower() or file_name.lower().endswith(".pdf"):
        return extract_pdf_text(buffer)

    return buffer.decode("utf-8")


def extract_pdf_text(buffer):
    with tempfile.NamedTemporaryFile(prefix="diet-plan-", suffix=".pdf", delete=False) as handle:
        temp_path = Path(handle.name)
        handle.write(buffer)

    try:
        script_path = ROOT_DIR / "scripts" / "extract_pdf.py"
        python_result = subprocess.run(
            ["python3", str(script_path), str(temp_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        python_output = python_result.stdout.strip()

        if python_result.returncode == 0 and python_output:
            return python_output

        strings_result = subprocess.run(
            ["strings", str(temp_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        lines = [
            line.strip()
            for line in strings_result.stdout.splitlines()
            if len(line.strip()) > 2 and any(char.isalnum() for char in line)
        ]
        if not lines:
            raise RuntimeError("Nao foi possivel extrair texto util do PDF. Cole o texto manualmente.")

        return "\n".join(lines)
    finally:
        temp_path.unlink(missing_ok=True)


def main():
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"Diet Shopping Assistant running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
