import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

from .normalization import strip_accents
from .parser import parse_plan, prepare_llm_meal_blocks
from .plan import normalize_plan


DEFAULT_MODEL = "gemini-2.5-flash-lite"
FALLBACK_MODEL = "gemini-2.5-flash"
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_THINKING_BUDGET = 0

PLAN_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "warnings": {"type": "ARRAY", "items": {"type": "STRING"}},
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "mealLabel": {"type": "STRING"},
                    "originalFood": {"type": "STRING"},
                    "quantity": {"type": "NUMBER"},
                    "unit": {"type": "STRING", "enum": ["g", "kg", "ml", "l", "unit"]},
                    "frequencyPerWeek": {"type": "NUMBER"},
                    "notes": {"type": "STRING"},
                },
                "required": ["mealLabel", "originalFood", "quantity", "unit", "frequencyPerWeek"],
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
        "Nao devolva normalizedFood, confidence ou ambiguityFlags.",
        "Devolva apenas os itens das refeicoes informadas.",
    ]
)


def get_llm_status(env=None):
    env = env or os.environ
    return {
        "configured": bool(env.get("GEMINI_API_KEY")),
        "provider": "gemini",
        "model": env.get("LLM_MODEL") or DEFAULT_MODEL,
        "fallbackModel": env.get("LLM_FALLBACK_MODEL") or FALLBACK_MODEL,
        "defaultMode": normalize_mode(env.get("LLM_PARSE_MODE")),
        "timeoutSeconds": get_timeout_seconds(env),
        "thinkingBudget": get_thinking_budget(env),
    }


def parse_plan_with_mode(plan_text, mode=None, env=None, llm_client=None):
    env = env or os.environ
    normalized_mode = normalize_mode(mode or env.get("LLM_PARSE_MODE"))
    llm_status = get_llm_status(env)
    local_plan = build_heuristic_plan(plan_text)
    local_plan["parseMetadata"].update(
        {
            "sourceChars": len(str(plan_text or "").strip()),
            "llmModel": llm_status["model"],
            "thinkingBudget": llm_status["thinkingBudget"],
        }
    )

    if normalized_mode == "heuristic":
        return local_plan

    if not llm_status["configured"]:
        local_plan["parseWarnings"] = ["LLM nao configurado; parser local usado."]
        return local_plan

    try:
        return parse_plan_with_gemini(
            plan_text=plan_text,
            api_key=env.get("GEMINI_API_KEY"),
            model=llm_status["model"],
            fallback_model=llm_status["fallbackModel"],
            local_plan=local_plan,
            thinking_budget=llm_status["thinkingBudget"],
            llm_client=llm_client or call_gemini,
        )
    except Exception as error:
        local_plan["parseWarnings"] = [f"LLM falhou e o parser local assumiu: {error}"]
        return local_plan


def parse_plan_with_gemini(plan_text, api_key, model, fallback_model, local_plan, thinking_budget, llm_client):
    timeout_seconds = get_timeout_seconds()
    prepared = prepare_llm_meal_blocks(plan_text, local_plan["items"])

    if not prepared["complexMeals"]:
        local_plan["parseMetadata"].update(
            {
                "llmUsed": False,
                "llmSkipped": True,
                "preprocessedChars": prepared["preprocessedChars"],
                "promptChars": 0,
            }
        )
        return local_plan

    llm_attempts = 1
    llm_started_at = time.monotonic()
    used_fallback_model = False
    active_model = model
    prompt = build_user_prompt(prepared["preprocessedText"])
    try:
        payload = llm_client(
            api_key=api_key,
            model=active_model,
            system_instruction=SYSTEM_INSTRUCTION,
            user_prompt=prompt,
            response_schema=PLAN_RESPONSE_SCHEMA,
            timeout_seconds=timeout_seconds,
            thinking_budget=thinking_budget,
        )
        normalized = normalize_llm_payload(payload)
        if should_retry_with_fallback(normalized, prepared) and active_model != fallback_model:
            llm_attempts = 2
            used_fallback_model = True
            active_model = fallback_model
            payload = llm_client(
                api_key=api_key,
                model=active_model,
                system_instruction=SYSTEM_INSTRUCTION,
                user_prompt=prompt,
                response_schema=PLAN_RESPONSE_SCHEMA,
                timeout_seconds=timeout_seconds,
                thinking_budget=thinking_budget,
            )
            normalized = normalize_llm_payload(payload)
    except RuntimeError as error:
        if not should_retry_without_thinking(model, error, thinking_budget):
            raise

        llm_attempts = 2
        payload = llm_client(
            api_key=api_key,
            model=active_model,
            system_instruction=SYSTEM_INSTRUCTION,
            user_prompt=prompt,
            response_schema=PLAN_RESPONSE_SCHEMA,
            timeout_seconds=timeout_seconds,
            thinking_budget=0,
        )
        normalized = normalize_llm_payload(payload)
    llm_duration_ms = round((time.monotonic() - llm_started_at) * 1000)
    merged_items = merge_local_and_llm_items(local_plan["items"], normalized["items"], prepared["complexMealKeys"])
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
                "llmModel": active_model,
                "thinkingBudget": thinking_budget,
                "promptChars": len(prompt),
                "sourceChars": prepared["sourceChars"],
                "preprocessedChars": prepared["preprocessedChars"],
                "usedFallbackModel": used_fallback_model,
                "llmUsed": True,
                "complexMealCount": len(prepared["complexMeals"]),
            },
            "items": merged_items,
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
                "originalFood": item.get("originalFood"),
                "quantity": sanitize_number(item.get("quantity"), 1),
                "unit": item.get("unit") or "unit",
                "frequencyPerWeek": sanitize_integer(item.get("frequencyPerWeek"), 7),
                "notes": item.get("notes") or "",
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
            "Interprete apenas as refeicoes e linhas abaixo e devolva somente JSON valido conforme o schema.",
            "Priorize sempre a primeira opcao e a primeira alternativa quando houver exclusividade.",
            "Nao invente alimentos ausentes.",
            "Trecho relevante do plano:",
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


def get_thinking_budget(env=None):
    env = env or os.environ
    try:
        return int(env.get("LLM_THINKING_BUDGET") or DEFAULT_THINKING_BUDGET)
    except (TypeError, ValueError):
        return DEFAULT_THINKING_BUDGET


def should_retry_without_thinking(model, error, thinking_budget):
    return model.startswith("gemini-2.5-flash") and thinking_budget != 0 and "Timeout ao chamar Gemini" in str(error)


def should_retry_with_fallback(normalized_payload, prepared):
    if not normalized_payload["items"]:
        return True

    expected_meals = set(prepared["complexMealKeys"])
    returned_meals = {strip_accents(item.get("mealLabel")) for item in normalized_payload["items"]}
    return not expected_meals.issubset(returned_meals)


def merge_local_and_llm_items(local_items, llm_items, complex_meal_keys):
    if not complex_meal_keys:
        return local_items

    llm_by_meal = {}
    for item in llm_items:
        key = strip_accents(item.get("mealLabel"))
        llm_by_meal.setdefault(key, []).append(item)

    merged = []
    local_grouped = {}
    for item in local_items:
        key = strip_accents(item.get("mealLabel"))
        local_grouped.setdefault(key, []).append(item)

    for key, items in local_grouped.items():
        if key in complex_meal_keys:
            merged.extend(llm_by_meal.get(key) or items)
        else:
            merged.extend(items)

    for key in complex_meal_keys:
        if key not in local_grouped and key in llm_by_meal:
            merged.extend(llm_by_meal[key])

    return merged


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
