from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from openai import OpenAI

from tac.domain.models import EvaluationResult
from tac.infrastructure.db import store as db
from tac.settings import Settings


class EvaluationFailed(RuntimeError):
    def __init__(self, error: str, *, attempts: int, raw_response: str | None) -> None:
        super().__init__(error)
        self.attempts = attempts
        self.raw_response = raw_response


def load_prompt(settings: Settings) -> str:
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


def _completion_content(response: Any) -> str:
    content = response.choices[0].message.content
    if not content:
        raise ValueError("empty AI response content")
    return content


def build_evaluation_messages(
    *,
    prompt: str,
    user_content: str,
    previous_raw: str | None = None,
    previous_error: str | None = None,
) -> list[dict[str, str]]:
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_content},
    ]
    if previous_raw is not None:
        messages.append(
            {
                "role": "user",
                "content": (
                    "上一次输出无法解析或不符合 schema。\n"
                    "解析/校验错误：\n"
                    f"{previous_error or 'unknown error'}\n\n"
                    "上一次原始输出：\n"
                    f"{previous_raw or ''}\n\n"
                    "请基于原始文章内容重新输出一个合法 JSON 对象，"
                    "不要输出 Markdown 代码块或解释文字。"
                ),
            }
        )
    return messages


def evaluate_with_ai(
    settings: Settings, *, title: str, url: str, content_markdown: str
) -> tuple[EvaluationResult, str]:
    if settings.ai_response_path:
        raw = settings.ai_response_path.read_text(encoding="utf-8")
        raw_json = _extract_json(raw)
        return EvaluationResult.model_validate_json(raw_json), raw_json

    if not settings.api_key:
        raise RuntimeError("OPENAI_API_KEY is required unless TAC_AI_RESPONSE_PATH is set")

    prompt = load_prompt(settings)
    user_content = f"# Title\n{title}\n\n# URL\n{url}\n\n# Markdown\n{content_markdown[:24000]}"

    client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)
    attempts = max(1, settings.evaluation_max_attempts)
    last_raw: str | None = None
    last_error: str | None = None
    actual_attempts = 0
    for _ in range(attempts):
        actual_attempts += 1
        try:
            response = client.chat.completions.create(
                model=settings.model,
                messages=build_evaluation_messages(
                    prompt=prompt,
                    user_content=user_content,
                    previous_raw=last_raw,
                    previous_error=last_error,
                ),
                temperature=0,
                response_format={"type": "json_object"},
                timeout=settings.ai_timeout_seconds,
            )
            last_raw = _completion_content(response)
            raw_json = _extract_json(last_raw)
            return EvaluationResult.model_validate_json(raw_json), raw_json
        except Exception as exc:
            last_error = str(exc)
    raise EvaluationFailed(
        last_error or "AI evaluation failed",
        attempts=actual_attempts,
        raw_response=last_raw,
    )


def _articles_for_evaluation(
    conn: sqlite3.Connection,
    article_ids: list[int] | None,
    limit: int | None,
) -> list[sqlite3.Row]:
    if article_ids is None:
        articles = db.queued_article_items(conn, stage="evaluate", limit=limit)
        if articles:
            return articles
        for article in db.articles_ready_for_evaluation(conn):
            db.enqueue_article(conn, article_id=int(article["id"]), stage="evaluate")
        return db.queued_article_items(conn, stage="evaluate", limit=limit)
    if not article_ids:
        return []
    placeholders = ",".join("?" for _ in article_ids)
    return conn.execute(
        f"""
        SELECT NULL AS queue_id, articles.*
        FROM articles
        WHERE id IN ({placeholders})
        ORDER BY id ASC
        """,
        article_ids,
    ).fetchall()


def _row_value(row: sqlite3.Row, key: str) -> object | None:
    try:
        return row[key]
    except (IndexError, KeyError):
        return None


def _evaluate_article(
    settings: Settings,
    article: sqlite3.Row,
    content_markdown: str,
) -> tuple[int, EvaluationResult | None, str | None, EvaluationFailed | Exception | None]:
    try:
        result, raw_json = evaluate_with_ai(
            settings,
            title=article["title"],
            url=article["url"],
            content_markdown=content_markdown,
        )
        return int(article["id"]), result, raw_json, None
    except Exception as exc:
        return int(article["id"]), None, None, exc


def evaluate_pending(
    settings: Settings,
    conn: sqlite3.Connection,
    limit: int | None = None,
    article_ids: list[int] | None = None,
) -> dict[str, int]:
    accepted = 0
    rejected = 0
    low_confidence = 0
    failed = 0
    tasks: list[tuple[sqlite3.Row, str]] = []
    queue_by_article_id: dict[int, int] = {}
    for article in _articles_for_evaluation(conn, article_ids, limit):
        queue_id = _row_value(article, "queue_id")
        if isinstance(queue_id, int):
            if not db.mark_queue_running(conn, queue_id):
                continue
            queue_by_article_id[int(article["id"])] = queue_id
        fetch = db.latest_successful_fetch(conn, int(article["id"]))
        if not fetch:
            if isinstance(queue_id, int):
                db.finish_queue_item(
                    conn,
                    queue_id,
                    status="failed",
                    error="latest successful fetch not found",
                )
            continue
        tasks.append((article, fetch["content_markdown"]))
    if not tasks:
        return {
            "attempted": 0,
            "accepted": 0,
            "rejected": 0,
            "low_confidence": 0,
            "failed": 0,
        }

    max_workers = max(1, settings.evaluate_max_concurrency)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_evaluate_article, settings, article, content_markdown)
            for article, content_markdown in tasks
        ]
        for future in as_completed(futures):
            article_id, result, raw_json, error = future.result()
            if result is not None and raw_json is not None:
                db.record_evaluation(conn, article_id, result, settings.model, raw_json)
                queue_id = queue_by_article_id.get(article_id)
                if queue_id is not None:
                    db.finish_queue_item(conn, queue_id, status="succeeded")
                if result.decision.value == "accept":
                    accepted += 1
                elif result.decision.value == "reject":
                    rejected += 1
                else:
                    low_confidence += 1
                continue
            if isinstance(error, EvaluationFailed):
                db.record_evaluation_failure(
                    conn,
                    article_id,
                    error=str(error),
                    attempts=error.attempts,
                    raw_response=error.raw_response,
                )
            else:
                db.record_evaluation_failure(
                    conn,
                    article_id,
                    error=str(error or "AI evaluation failed"),
                    attempts=1,
                    raw_response=None,
                )
            queue_id = queue_by_article_id.get(article_id)
            if queue_id is not None:
                db.finish_queue_item(
                    conn,
                    queue_id,
                    status="failed",
                    error=str(error or "AI evaluation failed"),
                )
            failed += 1
    return {
        "attempted": len(tasks),
        "accepted": accepted,
        "rejected": rejected,
        "low_confidence": low_confidence,
        "failed": failed,
    }
