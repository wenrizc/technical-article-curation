from __future__ import annotations

import json

from openai import OpenAI

from . import db
from .models import EvaluationResult


def load_prompt(settings) -> str:
    prompt = settings.prompt_path.read_text(encoding="utf-8")
    examples = []
    if settings.few_shot_dir.exists():
        for path in sorted(settings.few_shot_dir.glob("*.json")):
            examples.append(path.read_text(encoding="utf-8").strip())
    if examples:
        prompt += "\n\n## Few-shot JSON examples\n\n" + "\n\n".join(examples)
    return prompt


def _extract_json(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    json.loads(stripped)
    return stripped


def _completion_content(response) -> str:
    content = response.choices[0].message.content
    if not content:
        raise ValueError("empty AI response content")
    return content


def evaluate_with_ai(settings, *, title: str, url: str, content_markdown: str) -> tuple[EvaluationResult, str]:
    if settings.ai_response_path:
        raw = settings.ai_response_path.read_text(encoding="utf-8")
        raw_json = _extract_json(raw)
        return EvaluationResult.model_validate_json(raw_json), raw_json

    if not settings.api_key:
        raise RuntimeError("OPENAI_API_KEY is required unless TAC_AI_RESPONSE_PATH is set")

    prompt = load_prompt(settings)
    user_content = f"# Title\n{title}\n\n# URL\n{url}\n\n# Markdown\n{content_markdown[:24000]}"

    client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)
    response = client.chat.completions.create(
        model=settings.model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0,
        response_format={"type": "json_object"},
        timeout=90,
    )
    content = _completion_content(response)
    raw_json = _extract_json(content)
    return EvaluationResult.model_validate_json(raw_json), raw_json


def evaluate_pending(settings, conn, limit: int | None = None) -> dict[str, int]:
    attempted = 0
    accepted = 0
    rejected = 0
    low_confidence = 0
    failed = 0
    for article in db.articles_ready_for_evaluation(conn):
        if limit is not None and attempted >= limit:
            break
        fetch = db.latest_successful_fetch(conn, int(article["id"]))
        if not fetch:
            continue
        attempted += 1
        try:
            result, raw_json = evaluate_with_ai(
                settings,
                title=article["title"],
                url=article["url"],
                content_markdown=fetch["content_markdown"],
            )
            db.record_evaluation(conn, int(article["id"]), result, settings.model, raw_json)
            if result.decision.value == "accept" and result.confidence.value == "high":
                accepted += 1
            elif result.decision.value == "reject":
                rejected += 1
            else:
                low_confidence += 1
        except Exception as exc:
            db.record_failure(conn, int(article["id"]), f"evaluation failed: {exc}")
            failed += 1
    return {
        "attempted": attempted,
        "accepted": accepted,
        "rejected": rejected,
        "low_confidence": low_confidence,
        "failed": failed,
    }
