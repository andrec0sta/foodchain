#!/usr/bin/env python3
import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.llm import (  # noqa: E402
    DEFAULT_MODEL,
    FALLBACK_MODEL,
    build_heuristic_plan,
    call_gemini,
    parse_plan_with_gemini,
)


BUILTIN_CASES = {
    "small_complex": """
Cafe da manha:
2 ovos

Almoco:
Opcao 1:
- 5 colheres de sopa de arroz branco ou integral ou quinoa (120g)
- 1 concha pequena de feijao ou lentilha ou grao de bico
- 5 colheres de sopa cheia de carne moida ou bife de carne bovina (120g)
""".strip(),
    "medium_complex": """
CAFE DA MANHA
Opcao 1:
-1 iogurte natural (150ml)
- Meio medidor de whey protein (15g)

ALMOCO:
Carboidrato:
-5 colheres de sopa de arroz branco ou integral ou quinoa (120g)
-5 colheres de sopa de batata inglesa ou pure de batata ou batata doce (150 g)

Proteina:
-1 concha pequena de feijao ou lentilha ou grao de bico
- 5 colheres de sopa cheia de carne moida ou bife de carne bovina (120g)
- ou 1 file de frango (120g)

JANTAR:
Opcao 1:
Refeicao completa (verduras e legumes preenchendo metade do prato). Se baseando com as mesmas opcoes e quantidades de alimentos descritos no almoco.
""".strip(),
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Benchmark round-robin para comparar Gemini flash-lite vs flash sem fallback entre modelos."
    )
    parser.add_argument(
        "--model",
        dest="models",
        action="append",
        help="Modelo Gemini a medir. Pode repetir. Default: flash-lite e flash.",
    )
    parser.add_argument(
        "--case",
        dest="case_names",
        action="append",
        choices=sorted(BUILTIN_CASES),
        help="Caso builtin. Pode repetir.",
    )
    parser.add_argument(
        "--text-file",
        dest="text_files",
        action="append",
        help="Arquivo de texto puro para usar como caso extra. Pode repetir.",
    )
    parser.add_argument(
        "--pdf-file",
        dest="pdf_files",
        action="append",
        help="PDF para extrair texto e usar como caso extra. Pode repetir.",
    )
    parser.add_argument("--runs", type=int, default=3, help="Numero de execucoes medidas por caso/modelo.")
    parser.add_argument("--warmups", type=int, default=1, help="Numero de aquecimentos por caso/modelo.")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=90,
        help="Timeout de cada chamada LLM isolada. Default: 90.",
    )
    parser.add_argument(
        "--thinking-budget",
        type=int,
        default=0,
        help="thinkingBudget enviado ao Gemini. Default: 0.",
    )
    parser.add_argument(
        "--pause-ms",
        type=int,
        default=750,
        help="Pausa entre chamadas para reduzir jitter/rate limiting. Default: 750.",
    )
    parser.add_argument(
        "--api-key",
        help="Chave Gemini. Se omitida, usa GEMINI_API_KEY.",
    )
    parser.add_argument(
        "--output",
        help="Arquivo JSON para salvar o relatorio completo.",
    )
    return parser.parse_args()


def load_cases(args):
    cases = []
    for name in args.case_names or ["small_complex", "medium_complex"]:
        cases.append({"name": name, "source": "builtin", "text": BUILTIN_CASES[name]})

    for raw_path in args.text_files or []:
        path = Path(raw_path).expanduser().resolve()
        cases.append({"name": path.stem, "source": str(path), "text": path.read_text(encoding="utf-8")})

    for raw_path in args.pdf_files or []:
        path = Path(raw_path).expanduser().resolve()
        cases.append({"name": path.stem, "source": str(path), "text": extract_pdf_text(path)})

    if not cases:
        raise ValueError("Nenhum caso carregado.")

    return cases


def extract_pdf_text(pdf_path):
    extract_script = ROOT_DIR / "scripts" / "extract_pdf.py"
    command = [sys.executable, str(extract_script), str(pdf_path)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    text = result.stdout.strip()
    if result.returncode != 0 or not text:
        stderr = result.stderr.strip()
        raise RuntimeError(f"Falha ao extrair texto de {pdf_path}: {stderr or 'sem saida util'}")
    return text


def build_signature(items):
    rows = []
    for item in items:
        rows.append(
            "|".join(
                [
                    str(item.get("mealLabel") or ""),
                    str(item.get("normalizedFood") or item.get("originalFood") or ""),
                    str(item.get("quantity") or ""),
                    str(item.get("unit") or ""),
                    str(item.get("frequencyPerWeek") or ""),
                ]
            )
        )
    return rows


def run_case(model, case, api_key, timeout_seconds, thinking_budget):
    local_plan = build_heuristic_plan(case["text"])
    started_at = time.monotonic()
    plan = parse_plan_with_gemini(
        plan_text=case["text"],
        api_key=api_key,
        model=model,
        fallback_model=model,
        local_plan=local_plan,
        timeout_seconds=timeout_seconds,
        thinking_budget=thinking_budget,
        llm_client=call_gemini,
    )
    total_duration_ms = round((time.monotonic() - started_at) * 1000)
    metadata = plan.get("parseMetadata") or {}

    return {
        "status": "ok",
        "model": model,
        "case": case["name"],
        "source": case["source"],
        "totalDurationMs": total_duration_ms,
        "llmDurationMs": metadata.get("llmDurationMs"),
        "llmAttempts": metadata.get("llmAttempts"),
        "llmUsed": metadata.get("llmUsed"),
        "llmSkipped": metadata.get("llmSkipped", False),
        "promptChars": metadata.get("promptChars"),
        "preprocessedChars": metadata.get("preprocessedChars"),
        "complexMealCount": metadata.get("complexMealCount"),
        "itemCount": len(plan.get("items") or []),
        "warnings": plan.get("parseWarnings") or [],
        "signature": build_signature(plan.get("items") or []),
    }


def summarize_results(results):
    grouped = defaultdict(list)
    for result in results:
        grouped[(result["case"], result["model"])].append(result)

    summary = []
    for (case_name, model), entries in sorted(grouped.items()):
        successes = [entry for entry in entries if entry["status"] == "ok"]
        failures = [entry for entry in entries if entry["status"] == "error"]
        skips = [entry for entry in successes if entry.get("llmSkipped")]
        measured = [entry for entry in successes if not entry.get("llmSkipped")]
        total_durations = [entry["totalDurationMs"] for entry in measured if entry.get("totalDurationMs") is not None]
        llm_durations = [entry["llmDurationMs"] for entry in measured if entry.get("llmDurationMs") is not None]
        distinct_signatures = {tuple(entry.get("signature") or []) for entry in measured}

        summary.append(
            {
                "case": case_name,
                "model": model,
                "runs": len(entries),
                "successes": len(successes),
                "failures": len(failures),
                "skipped": len(skips),
                "medianTotalDurationMs": round(statistics.median(total_durations)) if total_durations else None,
                "medianLlmDurationMs": round(statistics.median(llm_durations)) if llm_durations else None,
                "distinctOutputs": len(distinct_signatures) if measured else 0,
                "consistentOutput": len(distinct_signatures) <= 1 if measured else None,
                "errors": [entry["error"] for entry in failures],
            }
        )

    return summary


def print_summary(summary):
    for row in summary:
        duration = row["medianTotalDurationMs"]
        llm_duration = row["medianLlmDurationMs"]
        consistency = "estavel" if row["consistentOutput"] else "variavel"
        if row["consistentOutput"] is None:
            consistency = "sem-medicao"

        print(
            " | ".join(
                [
                    f"case={row['case']}",
                    f"model={row['model']}",
                    f"ok={row['successes']}/{row['runs']}",
                    f"skipped={row['skipped']}",
                    f"median_total_ms={duration if duration is not None else 'n/a'}",
                    f"median_llm_ms={llm_duration if llm_duration is not None else 'n/a'}",
                    f"outputs={row['distinctOutputs']}",
                    f"consistency={consistency}",
                ]
            )
        )

        for error in row["errors"]:
            print(f"  error={error}")


def main():
    args = parse_args()
    api_key = args.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("Defina GEMINI_API_KEY ou use --api-key.")

    models = args.models or [DEFAULT_MODEL, FALLBACK_MODEL]
    cases = load_cases(args)
    results = []

    for case in cases:
        for _ in range(max(0, args.warmups)):
            for model in models:
                try:
                    run_case(model, case, api_key, args.timeout_seconds, args.thinking_budget)
                except Exception:
                    pass
                time.sleep(max(0, args.pause_ms) / 1000)

        for iteration in range(1, args.runs + 1):
            for model in models:
                try:
                    result = run_case(model, case, api_key, args.timeout_seconds, args.thinking_budget)
                except Exception as error:
                    result = {
                        "status": "error",
                        "model": model,
                        "case": case["name"],
                        "source": case["source"],
                        "iteration": iteration,
                        "error": str(error),
                    }
                else:
                    result["iteration"] = iteration

                results.append(result)
                time.sleep(max(0, args.pause_ms) / 1000)

    summary = summarize_results(results)
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "models": models,
        "runs": args.runs,
        "warmups": args.warmups,
        "timeoutSeconds": args.timeout_seconds,
        "thinkingBudget": args.thinking_budget,
        "cases": [{"name": case["name"], "source": case["source"]} for case in cases],
        "summary": summary,
        "results": results,
    }

    print_summary(summary)

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"saved={output_path}")


if __name__ == "__main__":
    main()
