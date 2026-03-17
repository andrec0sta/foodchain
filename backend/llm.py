import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

from .parser import parse_plan
from .plan import normalize_plan


DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_TIMEOUT_SECONDS = 60

PLAN_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "summary": {"type": "STRING"},
        "warnings": {"type": "ARRAY", "items": {"type": "STRING"}},
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "mealLabel": {"type": "STRING"},
                    "originalFood": {"type": "STRING"},
                    "normalizedFood": {"type": "STRING"},
                    "quantity": {"type": "NUMBER"},
                    "unit": {"type": "STRING"},
                    "frequencyPerWeek": {"type": "NUMBER"},
                    "notes": {"type": "STRING"},
                    "confidence": {"type": "NUMBER"},
                    "ambiguityFlags": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
                "required": ["mealLabel", "originalFood", "normalizedFood", "quantity", "unit", "frequencyPerWeek"],
            },
        },
    },
    "required": ["items"],
}

SYSTEM_INSTRUCTION = " ".join(
    [
        "Voce interpreta planos alimentares em portugues do Brasil para gerar uma estrutura de itens de compra.",
        "Ignore metadados, suplementos, tabelas de frutas, dicas gerais e instrucoes nao compraveis.",
        "Mantenha apenas alimentos compraveis, com uma linha por item interpretado.",
        "Quando houver varias opcoes exclusivas, priorize a primeira opcao e registre isso em notes.",
        "Quando uma linha usar 'ou', priorize a primeira alternativa e registre isso em notes.",
        "Se o jantar disser que segue o almoco com mesmas opcoes e quantidades, replique os itens do almoco.",
        "Use apenas as unidades: g, kg, ml, l ou unit.",
        "Use frequencyPerWeek como numero inteiro entre 1 e 21; default 7.",
        "normalizedFood deve ser curto e util para compra, sem marcas e sem descricoes longas.",
        "confidence deve ficar entre 0 e 1.",
        "ambiguityFlags deve conter marcadores curtos quando houver ambiguidade relevante.",
    ]
)


def get_llm_status(env=None):
    env = env or os.environ
    return {
        "configured": bool(env.get("GEMINI_API_KEY")),
        "provider": "gemini",
        "model": env.get("LLM_MODEL") or DEFAULT_MODEL,
        "defaultMode": normalize_mode(env.get("LLM_PARSE_MODE")),
        "timeoutSeconds": get_timeout_seconds(env),
    }


def parse_plan_with_mode(plan_text, mode=None, env=None):
    env = env or os.environ
    normalized_mode = normalize_mode(mode or env.get("LLM_PARSE_MODE"))
    llm_status = get_llm_status(env)

    if normalized_mode == "heuristic":
        return build_heuristic_plan(plan_text)

    if not llm_status["configured"]:
        return build_heuristic_plan(plan_text, ["LLM nao configurado; parser local usado."])

    try:
        return parse_plan_with_gemini(
            plan_text=plan_text,
            api_key=env.get("GEMINI_API_KEY"),
            model=llm_status["model"],
        )
    except Exception as error:
        return build_heuristic_plan(plan_text, [f"LLM falhou e o parser local assumiu: {error}"])


def parse_plan_with_gemini(plan_text, api_key, model):
    timeout_seconds = get_timeout_seconds()
    llm_attempts = 1
    llm_started_at = time.monotonic()
    try:
        payload = call_gemini(
            api_key=api_key,
            model=model,
            system_instruction=SYSTEM_INSTRUCTION,
            user_prompt=build_user_prompt(plan_text),
            response_schema=PLAN_RESPONSE_SCHEMA,
            timeout_seconds=timeout_seconds,
        )
    except RuntimeError as error:
        if not should_retry_without_thinking(model, error):
            raise

        llm_attempts = 2
        payload = call_gemini(
            api_key=api_key,
            model=model,
            system_instruction=SYSTEM_INSTRUCTION,
            user_prompt=build_user_prompt(plan_text),
            response_schema=PLAN_RESPONSE_SCHEMA,
            timeout_seconds=timeout_seconds,
            thinking_budget=0,
        )

    normalized = normalize_llm_payload(payload)
    llm_duration_ms = round((time.monotonic() - llm_started_at) * 1000)
    return normalize_plan(
        {
            "originalText": plan_text,
            "status": "parsed",
            "parseStrategy": "llm:gemini",
            "parseWarnings": normalized["warnings"],
            "parseMetadata": {
                "llmDurationMs": llm_duration_ms,
                "llmAttempts": llm_attempts,
                "llmTimeoutSeconds": timeout_seconds,
            },
            "items": normalized["items"],
        },
        default_status="parsed",
        parse_strategy="llm:gemini",
    )


def normalize_llm_payload(payload):
    source_items = payload.get("items") if isinstance(payload, dict) else payload if isinstance(payload, list) else []
    source_items = source_items if isinstance(source_items, list) else []
    warnings = payload.get("warnings") if isinstance(payload, dict) and isinstance(payload.get("warnings"), list) else []

    items = []
    for item in source_items:
        if not isinstance(item, dict):
            continue
        if not (item.get("originalFood") or item.get("normalizedFood")):
            continue

        items.append(
            {
                "mealLabel": item.get("mealLabel") or "Plano",
                "originalFood": item.get("originalFood") or item.get("normalizedFood"),
                "normalizedFood": item.get("normalizedFood") or item.get("originalFood"),
                "quantity": sanitize_number(item.get("quantity"), 1),
                "unit": item.get("unit") or "unit",
                "frequencyPerWeek": sanitize_integer(item.get("frequencyPerWeek"), 7),
                "notes": item.get("notes") or "",
                "confidence": sanitize_confidence(item.get("confidence")),
                "ambiguityFlags": [str(flag).strip() for flag in item.get("ambiguityFlags", []) if str(flag).strip()]
                if isinstance(item.get("ambiguityFlags"), list)
                else [],
            }
        )

    return {"warnings": [str(entry).strip() for entry in warnings if entry is not None and str(entry).strip()], "items": items}


def build_heuristic_plan(plan_text, warnings=None):
    plan = parse_plan(plan_text)
    plan["originalText"] = plan_text
    plan["status"] = "parsed"
    plan["parseStrategy"] = "heuristic"
    plan["parseWarnings"] = warnings or []
    plan["parseMetadata"] = {"llmUsed": False}
    return normalize_plan(plan, default_status="parsed", parse_strategy="heuristic")


def call_gemini(api_key, model, system_instruction, user_prompt, response_schema, timeout_seconds, thinking_budget=None):
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{urllib.parse.quote(model)}:generateContent?key={urllib.parse.quote(api_key)}"
    )
    generation_config = {
        "responseMimeType": "application/json",
        "responseSchema": response_schema,
    }
    if thinking_budget is not None:
        generation_config["thinkingConfig"] = {"thinkingBudget": thinking_budget}

    body = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": generation_config,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        message = error.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Erro HTTP no Gemini: {message or error.reason}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Falha de rede ao chamar Gemini: {error.reason}") from error
    except socket.timeout as error:
        raise RuntimeError(f"Timeout ao chamar Gemini apos {timeout_seconds}s.") from error
    except TimeoutError as error:
        raise RuntimeError(f"Timeout ao chamar Gemini apos {timeout_seconds}s.") from error

    text = extract_candidate_text(payload)
    return json.loads(extract_json_text(text))


def extract_candidate_text(payload):
    candidates = payload.get("candidates") or []
    if candidates:
        parts = ((candidates[0].get("content") or {}).get("parts") or [])
        text = "".join(part.get("text", "") for part in parts).strip()
        if text:
            return text

    prompt_feedback = payload.get("promptFeedback") or {}
    reason = prompt_feedback.get("blockReason") or (candidates[0].get("finishReason") if candidates else None)
    if reason:
        raise RuntimeError(f"Gemini nao retornou conteudo util ({reason}).")

    raise RuntimeError("Gemini nao retornou conteudo util.")


def extract_json_text(text):
    trimmed = str(text or "").strip()
    if not trimmed:
        raise RuntimeError("Resposta vazia do Gemini.")

    if trimmed.startswith("{") or trimmed.startswith("["):
        return trimmed

    fenced = re.search(r"```(?:json)?\s*([\s\S]+?)```", trimmed, re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()

    object_start = trimmed.find("{")
    array_start = trimmed.find("[")
    starts = [index for index in (object_start, array_start) if index >= 0]
    if starts:
        return trimmed[min(starts):]

    raise RuntimeError("Nao foi possivel localizar JSON valido na resposta do Gemini.")


def build_user_prompt(plan_text):
    return "\n\n".join(
        [
            "Interprete o plano alimentar abaixo e devolva apenas JSON valido conforme o schema.",
            "Nao invente alimentos ausentes.",
            "Plano:",
            plan_text,
        ]
    )


def normalize_mode(value):
    return value if value in {"heuristic", "llm"} else "auto"


def get_timeout_seconds(env=None):
    env = env or os.environ
    try:
        numeric = int(env.get("LLM_TIMEOUT_SECONDS") or DEFAULT_TIMEOUT_SECONDS)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SECONDS

    return max(10, numeric)


def should_retry_without_thinking(model, error):
    return model.startswith("gemini-2.5-flash") and "Timeout ao chamar Gemini" in str(error)


def sanitize_number(value, fallback):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return fallback

    return numeric if numeric > 0 else fallback


def sanitize_integer(value, fallback):
    try:
        numeric = int(round(float(value)))
    except (TypeError, ValueError):
        return fallback

    return max(1, min(21, numeric))


def sanitize_confidence(value):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None

    return max(0.0, min(1.0, numeric))
