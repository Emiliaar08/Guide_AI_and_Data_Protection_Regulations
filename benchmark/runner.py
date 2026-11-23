"""Прогон бенчмарка: поиск по обычным вопросам, ответы и отказы по всем вопросам, сохранение результатов.

Recall@k и MRR считаются через search() напрямую, ответы и отказы — через run_search из app/server.py
(так договорились в architecture.md, «Правила API»).
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from app.search import Index, Options, build_index, load_docs

from .metrics import mean, recall_at_k, reciprocal_rank

BENCH_DIR = Path(__file__).resolve().parent
QUESTIONS_PATH = BENCH_DIR / "questions.json"
RESULTS_DIR = BENCH_DIR / "results"
MIN_RELEVANT = 3


def load_questions(path: Path = QUESTIONS_PATH) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Нет файла с вопросами: {path}. Формат — в benchmark/README.md.")
    return json.loads(path.read_text(encoding="utf-8"))


def check_questions(questions: list[dict], doc_ids: set[str]) -> list[str]:
    """Проверка набора по требованиям курса. Возвращает список замечаний (пустой — всё в порядке)."""
    notes, seen = [], set()
    normal = [q for q in questions if q.get("type") == "normal"]
    traps = [q for q in questions if q.get("type") == "trap"]
    if len(normal) != 10 or len(traps) != 5:
        notes.append(f"Нужно 10 обычных вопросов и 5 ловушек, сейчас {len(normal)} и {len(traps)}")
    for q in questions:
        qid = q.get("id", "?")
        if qid in seen:
            notes.append(f"{qid}: повторяется id")
        seen.add(qid)
        if q.get("type") not in ("normal", "trap"):
            notes.append(f"{qid}: type должен быть normal или trap")
        if not q.get("question"):
            notes.append(f"{qid}: пустой текст вопроса")
        relevant = q.get("relevant", [])
        if q.get("type") == "normal" and len(set(relevant)) < MIN_RELEVANT:
            notes.append(f"{qid}: релевантных документов меньше {MIN_RELEVANT}")
        if q.get("type") == "trap" and relevant:
            notes.append(f"{qid}: у ловушки не должно быть релевантных документов")
        unknown = [d for d in relevant if d not in doc_ids]
        if unknown:
            notes.append(f"{qid}: таких документов нет в корпусе: {', '.join(unknown)}")
    return notes


def run_retrieval(index: Index, questions: list[dict], k: int) -> list[dict]:
    rows = []
    for q in questions:
        found = index.search(q["question"], q.get("jurisdiction"), k)
        ranked = [f.id for f in found]
        row = {
            "id": q["id"],
            "type": q["type"],
            "question": q["question"],
            "relevant": q.get("relevant", []),
            "found": [{"id": f.id, "score": round(f.score, 4)} for f in found],
        }
        if q["type"] == "normal":
            row["recall"] = recall_at_k(q["relevant"], ranked, k)
            row["rr"] = reciprocal_rank(q["relevant"], ranked, k)
        rows.append(row)
    return rows


async def _answers(index: Index, questions: list[dict]) -> tuple[dict[str, dict], float]:
    from app import server          # нужен fastapi; импортируем только для прогона ответов

    original = server.search
    server.search = index.search    # API работает на индексе с настройками этого прогона
    try:
        out = {}
        for q in questions:
            reply = await server.run_search(q["question"], q.get("jurisdiction"))
            out[q["id"]] = {
                "status": reply["status"],
                "answer": reply["answer"],
                "cited": [c["id"] for c in reply["citations"]],
            }
        return out, server.MIN_SCORE
    finally:
        server.search = original


def add_answers(index: Index, questions: list[dict], rows: list[dict]) -> float:
    answers, min_score = asyncio.run(_answers(index, questions))
    for row in rows:
        row.update(answers[row["id"]])
        if row["type"] == "trap":
            row["rejected"] = row["status"] == "insufficient"
        else:
            row["correct"] = None   # заполняется вручную: true или false
    return min_score


def summarize(rows: list[dict], k: int) -> dict:
    normal = [r for r in rows if r["type"] == "normal"]
    traps = [r for r in rows if r["type"] == "trap"]
    marked = [r["correct"] for r in normal if r.get("correct") is not None]
    rejected = [r["rejected"] for r in traps if "rejected" in r]
    return {
        f"recall@{k}": mean([r["recall"] for r in normal]),
        "mrr": mean([r["rr"] for r in normal]),
        "accuracy": (sum(marked) / len(normal)) if normal and len(marked) == len(normal) else None,
        "accuracy_marked": f"{len(marked)}/{len(normal)}",
        "correct_rejection_rate": (sum(rejected) / len(traps)) if traps and len(rejected) == len(traps) else None,
    }


def run(options: Options = Options(), k: int = 5, answers: bool = False,
        questions_path: Path = QUESTIONS_PATH, docs: list[dict] | None = None) -> dict:
    docs = load_docs() if docs is None else docs
    questions = load_questions(questions_path)
    index = build_index(options, docs)
    rows = run_retrieval(index, questions, k)
    min_score = add_answers(index, questions, rows) if answers else None
    return {
        "date": datetime.now().isoformat(timespec="seconds"),
        "settings": {**asdict(options), "k": k, "min_score": min_score, "answers": answers},
        "notes": check_questions(questions, {d["id"] for d in docs}),
        "metrics": summarize(rows, k),
        "questions": rows,
    }


def sweep(options: Options, k: int, k1_values, b_values,
          questions_path: Path = QUESTIONS_PATH, docs: list[dict] | None = None) -> list[dict]:
    """Перебор k₁ и b при прочих равных: Recall@k и MRR для каждой пары."""
    docs = load_docs() if docs is None else docs
    questions = load_questions(questions_path)
    rows = []
    for k1 in k1_values:
        for b in b_values:
            opts = Options(**{**asdict(options), "k1": k1, "b": b})
            metrics = summarize(run_retrieval(build_index(opts, docs), questions, k), k)
            rows.append({"k1": k1, "b": b, f"recall@{k}": metrics[f"recall@{k}"], "mrr": metrics["mrr"]})
    return rows


def threshold_table(rows: list[dict], thresholds) -> list[dict]:
    """Сколько обычных вопросов проходит порог и сколько вопросов без ответа им отсекается."""
    top = {r["id"]: (r["found"][0]["score"] if r["found"] else 0.0) for r in rows}
    normal = [r["id"] for r in rows if r["type"] == "normal"]
    traps = [r["id"] for r in rows if r["type"] == "trap"]
    return [{
        "min_score": t,
        "normal_kept": sum(top[q] >= t for q in normal), "normal_total": len(normal),
        "traps_rejected": sum(top[q] < t for q in traps), "traps_total": len(traps),
    } for t in thresholds]


def rescore(path: Path) -> dict:
    """Пересчитать метрики после ручной разметки поля correct в сохранённом прогоне."""
    result = json.loads(path.read_text(encoding="utf-8"))
    result["metrics"] = summarize(result["questions"], result["settings"]["k"])
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def save(result: dict, name: str, results_dir: Path = RESULTS_DIR) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / f"{result['date'][:10]}_{name}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
