"""python -m benchmark — прогон бенчмарка. Параметры: python -m benchmark --help."""
import argparse
import sys
from pathlib import Path

from app.search import Options

from .runner import QUESTIONS_PATH, rescore, run, save


def fmt(value) -> str:
    return "—" if value is None else f"{value:.3f}"


def print_result(result: dict) -> None:
    m = result["metrics"]
    k = result["settings"]["k"]
    print(f"Recall@{k}: {fmt(m[f'recall@{k}'])}   MRR: {fmt(m['mrr'])}   "
          f"Accuracy: {fmt(m['accuracy'])} (размечено {m['accuracy_marked']})   "
          f"CRR: {fmt(m['correct_rejection_rate'])}")
    for row in result.get("questions", []):
        found = ", ".join(f["id"] for f in row["found"]) or "ничего"
        extra = f"  recall={row['recall']:.2f} rr={row['rr']:.2f}" if row["type"] == "normal" else ""
        status = f"  [{row['status']}]" if "status" in row else ""
        print(f"  {row['id']}: {found}{extra}{status}")
    for note in result.get("notes", []):
        print(f"  ! {note}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m benchmark", description="Бенчмарк поиска BM25 и ответов")
    p.add_argument("--questions", type=Path, default=QUESTIONS_PATH, help="файл с вопросами")
    p.add_argument("--k", type=int, default=5, help="глубина для Recall@k и MRR (по умолчанию 5)")
    p.add_argument("--k1", type=float, default=1.2)
    p.add_argument("--b", type=float, default=0.75)
    p.add_argument("--no-lemmatize", action="store_true", help="без лемматизации")
    p.add_argument("--no-synonyms", action="store_true", help="без словаря синонимов")
    p.add_argument("--no-stopwords", action="store_true", help="без удаления стоп-слов")
    p.add_argument("--answers", action="store_true",
                   help="прогнать вопросы через API (run_search): статусы, ответы, отказы")
    p.add_argument("--name", default="run", help="описание прогона в имени файла результата")
    p.add_argument("--no-save", action="store_true", help="не сохранять результат в benchmark/results/")
    p.add_argument("--rescore", type=Path, help="пересчитать метрики сохранённого прогона после ручной разметки")
    args = p.parse_args(argv)

    if args.rescore:
        print_result(rescore(args.rescore))
        return 0

    options = Options(lemmatize=not args.no_lemmatize, synonyms=not args.no_synonyms,
                      stopwords=not args.no_stopwords, k1=args.k1, b=args.b)
    result = run(options, args.k, args.answers, args.questions)
    print_result(result)
    if not args.no_save:
        print(f"Сохранено: {save(result, args.name)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
