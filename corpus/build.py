"""Сборка corpus/docs.jsonl из исходных текстов в corpus/raw/.

Запуск из корня проекта:  python -m corpus.build   (или python corpus/build.py)

Какие статьи и части становятся документами, задано в списке DOCS ниже.
Исходные тексты не правятся: справочные пометки («в ред.», «введена», примечания
КонсультантПлюс) убираются при сборке, в raw/ остаются как были.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parent
RAW_DIR = CORPUS_DIR / "raw"
OUT_PATH = CORPUS_DIR / "docs.jsonl"

ACTS = {
    "152fz": {
        "file": "152fz.txt",
        "doc_title": "152-ФЗ «О персональных данных»",
        "jurisdiction": "ru",
        "url": "https://mintrud.gov.ru/docs/laws/130",
        "source": "КонсультантПлюс",
        "edition": "ред. от 26.07.2026 (последние изменения — ФЗ от 26.07.2026 N 265-ФЗ)",
    },
}

# id, акт, номер статьи, части (None — вся статья; иначе (первая, последняя) по номерам частей)
DOCS = [
    ("D01", "152fz", "3", None),
    ("D02", "152fz", "5", None),
    ("D03", "152fz", "6", ("1", "2")),
    ("D04", "152fz", "6", ("3", "6")),
    ("D05", "152fz", "9", None),
    ("D06", "152fz", "10", None),
    ("D07", "152fz", "11", None),
    ("D08", "152fz", "12", None),
    ("D09", "152fz", "16", None),
    ("D10", "152fz", "18.1", None),
]

ARTICLE_RE = re.compile(r"^Статья (\d+(?:\.\d+)?)\. (.+)$")
CHAPTER_RE = re.compile(r"^Глава \d+\.")
PART_RE = re.compile(r"^(\d+(?:\.\d+)?)\. ")
NOTE_HEADER = "КонсультантПлюс: примечание."


def read_raw(name: str) -> list[str]:
    text = (RAW_DIR / name).read_text(encoding="utf-8")
    return [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]


def is_editorial(line: str) -> bool:
    """Строка-пометка целиком в скобках: «(в ред. …)», «(введена …)», «(часть 3 в ред. …)»."""
    return line.startswith("(") and line.endswith(")")


def articles(lines: list[str]) -> dict[str, dict]:
    """Номер статьи → {"title", "lines"} с очищенным текстом."""
    result, current, skip_next = {}, None, False
    for line in lines:
        line = line.strip()
        if skip_next:                      # строка после «КонсультантПлюс: примечание.»
            skip_next = False
            continue
        if line == NOTE_HEADER:
            skip_next = True
            continue
        m = ARTICLE_RE.match(line)
        if m:
            current = {"title": m.group(2), "lines": []}
            result[m.group(1)] = current
            continue
        if CHAPTER_RE.match(line) or line.startswith("---") or line.startswith("Президент"):
            current = None
            continue
        if current is not None and line and not is_editorial(line):
            current["lines"].append(line)
    return result


def part_key(number: str) -> tuple[int, ...]:
    return tuple(int(x) for x in number.split("."))


def select_parts(lines: list[str], first: str, last: str) -> list[str]:
    """Строки частей с номерами от first до last включительно (пункты «1)» идут со своей частью)."""
    out, inside = [], False
    lo, hi = part_key(first), part_key(last)
    for line in lines:
        m = PART_RE.match(line)
        if m:
            key = part_key(m.group(1))
            inside = lo <= key and key[:len(hi)] <= hi     # «3.1» входит в диапазон до «3»
        if inside:
            out.append(line)
    return out


def article_label(number: str, parts) -> str:
    if parts is None:
        return f"ст. {number}"
    first, last = parts
    return f"ст. {number} ч. {first}" if first == last else f"ст. {number} ч. {first}–{last}"


def build() -> list[dict]:
    parsed = {key: articles(read_raw(act["file"])) for key, act in ACTS.items()}
    docs = []
    for doc_id, act_key, number, parts in DOCS:
        act = ACTS[act_key]
        art = parsed[act_key].get(number)
        if art is None:
            raise ValueError(f"{doc_id}: в {act['file']} нет статьи {number}")
        body = art["lines"] if parts is None else select_parts(art["lines"], *parts)
        if not body:
            raise ValueError(f"{doc_id}: пустой текст (статья {number}, части {parts})")
        docs.append({
            "id": doc_id,
            "doc_title": act["doc_title"],
            "jurisdiction": act["jurisdiction"],
            "article": article_label(number, parts),
            "text": f"Статья {number}. {art['title']}\n" + "\n".join(body),
            "url": act["url"],
            "source": act["source"],
            "edition": act["edition"],
        })
    return docs


def main() -> None:
    docs = build()
    with OUT_PATH.open("w", encoding="utf-8", newline="\n") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    print(f"{OUT_PATH.name}: {len(docs)} документов")
    for doc in docs:
        print(f"  {doc['id']}  {doc['doc_title']}, {doc['article']}: {len(doc['text'])} символов")


if __name__ == "__main__":
    main()
