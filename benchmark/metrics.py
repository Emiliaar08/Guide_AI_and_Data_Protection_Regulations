"""Метрики качества поиска и ответа. Формулы — в benchmark/README.md и методичке (раздел 1.5)."""
from __future__ import annotations


def recall_at_k(relevant: list[str], ranked: list[str], k: int) -> float:
    """Доля релевантных документов среди первых k: |R ∩ Top_k| / |R|."""
    if not relevant:
        raise ValueError("У обычного вопроса должен быть хотя бы один релевантный документ")
    return len(set(relevant) & set(ranked[:k])) / len(set(relevant))


def reciprocal_rank(relevant: list[str], ranked: list[str], k: int) -> float:
    """1 / позиция первого релевантного документа в первых k; 0, если его там нет."""
    wanted = set(relevant)
    for position, doc_id in enumerate(ranked[:k], start=1):
        if doc_id in wanted:
            return 1 / position
    return 0.0


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None
