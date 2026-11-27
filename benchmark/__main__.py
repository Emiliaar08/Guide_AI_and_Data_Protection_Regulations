"""python -m benchmark — прогон бенчмарка. Параметры: python -m benchmark --help."""
import argparse
import sys
from pathlib import Path

from app.search import Options

from .runner import QUESTIONS_PATH, rescore, run, save, sweep, threshold_table


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
        top = f"  max={row['found'][0]['score']:.2f}" if row["found"] else ""
        print(f"  {row['id']}: {found}{extra}{top}{status}")
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
    p.add_argument("--sweep", action="store_true", help="перебрать k1 и b и вывести таблицу Recall@k и MRR")
    p.add_argument("--thresholds", action="store_true",
                   help="таблица порогов MIN_SCORE: сколько обычных вопросов проходит и сколько без ответа отсекается")
    args = p.parse_args(argv)

    if args.rescore:
        print_result(rescore(args.rescore))
        return 0

    options = Options(lemmatize=not args.no_lemmatize, synonyms=not args.no_synonyms,
                      stopwords=not args.no_stopwords, k1=args.k1, b=args.b)
    if args.sweep:
        rows = sweep(options, args.k, [1.2, 1.5, 1.8, 2.0], [0.5, 0.75, 1.0], args.questions)
        print(f"  k1    b     Recall@{args.k}  MRR")
        for r in rows:
            print(f"  {r['k1']:<5} {r['b']:<5} {fmt(r[f'recall@{args.k}'])}     {fmt(r['mrr'])}")
        best = max(rows, key=lambda r: (r[f"recall@{args.k}"], r["mrr"]))
        print(f"Лучшее: k1={best['k1']}, b={best['b']}")
        return 0
    result = run(options, args.k, args.answers, args.questions)
    print_result(result)
    if args.thresholds:
        print("  MIN_SCORE  обычные проходят  без ответа отсекаются")
        for t in threshold_table(result["questions"], [1, 2, 3, 4, 5, 6, 7, 8, 10]):
            print(f"  {t['min_score']:<9}  {t['normal_kept']}/{t['normal_total']}"
                  f"               {t['traps_rejected']}/{t['traps_total']}")
    if not args.no_save:
        print(f"Сохранено: {save(result, args.name)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
