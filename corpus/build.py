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
        "part_word": "ч.",
    },
    "gdpr": {
        "file": "gdpr_ru.txt",
        "doc_title": "GDPR (Регламент ЕС 2016/679)",
        "jurisdiction": "eu",
        "url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng",
        "source": "перевод Data Privacy Office, gdpr-text.com",
        "edition": "Регламент (ЕС) 2016/679 с исправлениями (Corrigendum, OJ L 127, 23.5.2018); неофициальный перевод",
        "part_word": "п.",
    },
}

# id, акт, номер статьи, части:
#   None — вся статья; ("1", "2") — части (параграфы) с номерами от 1 до 2;
#   ["1", "2", "7"] — только перечисленные пункты вида «(1)» (для статей-определений).
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
    ("D11", "gdpr", "4", ["1", "2", "7", "8", "11", "14"]),
    ("D12", "gdpr", "5", None),
    ("D13", "gdpr", "6", None),
    ("D14", "gdpr", "9", None),
    ("D15", "gdpr", "22", None),
    ("D16", "gdpr", "28", ("1", "3")),
    ("D17", "gdpr", "28", ("4", "10")),
    ("D18", "gdpr", "35", None),
    ("D19", "gdpr", "44", None),
    ("D20", "gdpr", "46", None),
]

ARTICLE_RE = re.compile(r"^Статья (\d+(?:\.\d+)?)(?: GDPR)?\. (.+)$")
CHAPTER_RE = re.compile(r"^Глава \d+\.")
PART_RE = re.compile(r"^(\d+(?:\.\d+)?)\. ")
NOTE_HEADER = "КонсультантПлюс: примечание."
POINT_RE = re.compile(r"^\((\d+)\)")
# Служебные строки сайтов, которые копируются вместе с текстом
SERVICE_LINES = {"Комментарий эксперта", "ISO 27701", "Руководство и прецедентное право", "Преамбулы",
                 "Связанные статьи", "Скачать в PDF"}
SERVICE_RE = re.compile(r"^\[(Комментарий эксперта|Связанные статьи)|^\[\d+\] |Болгарский \(bg\)")


def read_raw(name: str) -> list[str]:
    text = (RAW_DIR / name).read_text(encoding="utf-8")
    return [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]


def is_editorial(line: str) -> bool:
    """Строка-пометка, а не текст нормы: «(в ред. …)», «(введена …)», служебные ссылки сайта."""
    if line in SERVICE_LINES or SERVICE_RE.search(line):
        return True
    return line.startswith("(") and line.endswith(")") and not POINT_RE.match(line)


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


def select_points(lines: list[str], points: list[str]) -> list[str]:
    """Вводная строка статьи и пункты «(N)» из списка (со своими подпунктами)."""
    out, inside, started = [], False, False
    for line in lines:
        m = POINT_RE.match(line)
        if m:
            started = True
            inside = m.group(1) in points
        if inside or not started:
            out.append(line)
    return out


def article_label(number: str, parts, word: str) -> str:
    if parts is None:
        return f"ст. {number}"
    if isinstance(parts, list):
        return f"ст. {number} п. {', '.join(parts)}"
    first, last = parts
    return f"ст. {number} {word} {first}" if first == last else f"ст. {number} {word} {first}–{last}"


def build() -> list[dict]:
    parsed = {key: articles(read_raw(act["file"])) for key, act in ACTS.items()}
    docs = []
    for doc_id, act_key, number, parts in DOCS:
        act = ACTS[act_key]
        art = parsed[act_key].get(number)
        if art is None:
            raise ValueError(f"{doc_id}: в {act['file']} нет статьи {number}")
        if parts is None:
            body = art["lines"]
        elif isinstance(parts, list):
            body = select_points(art["lines"], parts)
        else:
            body = select_parts(art["lines"], *parts)
        if not body:
            raise ValueError(f"{doc_id}: пустой текст (статья {number}, части {parts})")
        docs.append({
            "id": doc_id,
            "doc_title": act["doc_title"],
            "jurisdiction": act["jurisdiction"],
            "article": article_label(number, parts, act["part_word"]),
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
