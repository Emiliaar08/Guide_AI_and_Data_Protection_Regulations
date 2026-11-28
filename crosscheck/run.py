"""Сверка чужого прогона: наш BM25 (app/search.py) на корпусе и вопросах другой команды.

Запуск из корня проекта:
    python -m crosscheck.run
    python -m crosscheck.run --fields ingredients --synonyms
    python -m crosscheck.run --no-lemmatize          # если нет pymorphy3

Документы и вопросы другой команды лежат в crosscheck/data/ и не меняются.
Код поиска тот же, что в нашем RAG: Preprocessor, Index, BM25 с k1 и b из Options.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from app.search import Index, Options, Preprocessor, load_stopwords

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
RESULTS = HERE / "results"
MIN_SCORE = 3.0   # тот же порог, что у нас в API; на чужом корпусе его нужно проверить

# Какие поля рецепта попадают в индекс.
FIELDS = {
    # всё текстовое: название, описание, ингредиенты, категории, теги, вкусы, шаги
    "full": ("title", "description", "ingredientNames", "categories", "tags", "tastes", "steps"),
    # только название и список ингредиентов
    "ingredients": ("title", "ingredientNames"),
}


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(_text(v) for v in value)
    return str(value)


def to_docs(recipes: list[dict], fields: tuple[str, ...]) -> list[dict]:
    """Рецепт → документ в формате нашего индекса (doc_title, article, text и служебные поля)."""
    docs = []
    for r in recipes:
        docs.append({
            "id": r["id"],
            "doc_title": r.get("title", ""),
            "jurisdiction": "recipes",
            "article": "",
            # название уже в doc_title, поэтому в text его не дублируем
            "text": " ".join(_text(r.get(f)) for f in fields if f != "title"),
            "url": r.get("sourceUrl", ""),
            "edition": r.get("sourceId", ""),
        })
    return docs


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate(index: Index, questions: list[dict], k: int) -> dict:
    rows, recalls, rrs, rejections = [], [], [], []
    for q in questions:
        found = index.search(q["query"], k=k)
        ids = [f.id for f in found]
        top = found[0].score if found else 0.0
        gold = q.get("goldDocIds", [])
        row = {
            "id": q["id"], "type": q["type"], "query": q["query"],
            "gold": gold, "found": [{"id": f.id, "score": round(f.score, 4)} for f in found],
            "top_score": round(top, 4),
        }
        if q["type"] == "trap":
            row["rejected"] = top < MIN_SCORE
            rejections.append(row["rejected"])
        else:
            hits = [i for i in ids if i in gold]
            ranks = [n for n, i in enumerate(ids, start=1) if i in gold]
            row["recall"] = len(hits) / len(gold) if gold else 0.0
            # потолок Recall@k, если нужных документов больше k
            row["recall_max"] = min(k, len(gold)) / len(gold) if gold else 0.0
            row["rr"] = 1 / ranks[0] if ranks else 0.0
            row["first_rank"] = ranks[0] if ranks else None
            recalls.append(row["recall"])
            rrs.append(row["rr"])
        rows.append(row)
    mean = lambda xs: round(sum(xs) / len(xs), 3) if xs else 0.0
    return {
        "metrics": {
            f"recall@{k}": mean(recalls),
            "mrr": mean(rrs),
            "trap_rejected_by_threshold": f"{sum(rejections)}/{len(rejections)}",
        },
        "questions": rows,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Наш BM25 на корпусе другой команды")
    p.add_argument("--docs", type=Path, default=DATA / "documents.json")
    p.add_argument("--questions", type=Path, default=DATA / "questions.json")
    p.add_argument("--fields", choices=FIELDS, default="full")
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--no-lemmatize", action="store_true")
    p.add_argument("--synonyms", action="store_true", help="crosscheck/synonyms.json (орехи → фундук, миндаль…)")
    p.add_argument("--name", default=None, help="имя файла результата")
    p.add_argument("--no-save", action="store_true")
    a = p.parse_args(argv)

    options = Options(lemmatize=not a.no_lemmatize, synonyms=a.synonyms)
    stopwords = load_stopwords() + load_stopwords(HERE / "stopwords.txt")
    synonyms = load_json(HERE / "synonyms.json") if a.synonyms else None
    if synonyms:
        synonyms = {k: v for k, v in synonyms.items() if not k.startswith("_")}
    index = Index(to_docs(load_json(a.docs), FIELDS[a.fields]), Preprocessor(options, stopwords, synonyms))

    result = evaluate(index, load_json(a.questions), a.k)
    result = {
        "date": date.today().isoformat(),
        "settings": {"fields": a.fields, "k": a.k, "lemmatize": options.lemmatize,
                     "synonyms": a.synonyms, "k1": options.k1, "b": options.b, "min_score": MIN_SCORE},
        **result,
    }

    print(json.dumps(result["settings"], ensure_ascii=False))
    print(json.dumps(result["metrics"], ensure_ascii=False))
    n_docs = len(index.docs)
    print(f"в индексе документов: {n_docs}; в выдаче берём первые {a.k}")
    print(f"{'вопрос':7} {'нужных в выдаче':>16} {'место 1-го нужного':>19} {'top балл':>9}  выдача (место: id)")
    for r in result["questions"]:
        found = " ".join(f"{n}:{f['id']}{'*' if f['id'] in r['gold'] else ''}"
                         for n, f in enumerate(r["found"], start=1))
        if r["type"] == "trap":
            mark = "отказ" if r["rejected"] else "НЕТ отказа"
            print(f"{r['id']:7} {'ловушка':>16} {mark:>19} {r['top_score']:9.2f}  {found}")
        else:
            hits = sum(1 for f in r["found"] if f["id"] in r["gold"])
            got = f"{hits} из {len(r['gold'])}"
            place = f"{r['first_rank']} из {a.k}" if r["first_rank"] else "нет"
            print(f"{r['id']:7} {got:>16} {place:>19} {r['top_score']:9.2f}  {found}")
    print("* — документ из эталона другой команды")

    if not a.no_save:
        RESULTS.mkdir(exist_ok=True)
        name = a.name or f"{a.fields}{'-syn' if a.synonyms else ''}{'-nolemma' if a.no_lemmatize else ''}"
        out = RESULTS / f"{result['date']}_{name}.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"сохранено: {out.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
