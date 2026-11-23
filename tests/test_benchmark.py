"""Тесты бенчмарка: метрики, проверка набора вопросов, прогон и сохранение."""
import json

import pytest

from app.search import Options
from benchmark import runner
from benchmark.__main__ import main
from benchmark.metrics import mean, recall_at_k, reciprocal_rank

PLAIN = Options(lemmatize=False, synonyms=False, stopwords=False)


# ---------- метрики (примеры со слайдов занятия 3) ----------

def test_recall_slide_example():
    # правильные A, D, F; поиск вернул B, A, D → нашли 2 из 3
    assert recall_at_k(["A", "D", "F"], ["B", "A", "D"], 3) == pytest.approx(2 / 3)


def test_reciprocal_rank_and_mrr_slide_example():
    rr1 = reciprocal_rank(["A", "D"], ["B", "A", "D"], 3)   # первый полезный на № 2
    rr2 = reciprocal_rank(["X"], ["X", "Y"], 3)             # первый полезный на № 1
    assert (rr1, rr2) == (0.5, 1.0)
    assert mean([rr1, rr2]) == 0.75


def test_reciprocal_rank_zero_outside_top_k():
    assert reciprocal_rank(["C"], ["A", "B", "C"], 2) == 0.0


def test_recall_counts_only_top_k_and_unique_relevant():
    assert recall_at_k(["A", "B"], ["A", "X", "B"], 2) == 0.5
    assert recall_at_k(["A", "A", "B"], ["A"], 5) == 0.5


def test_recall_needs_relevant():
    with pytest.raises(ValueError):
        recall_at_k([], ["A"], 5)


# ---------- проверка набора вопросов ----------

def test_check_questions_reports_problems():
    questions = [
        {"id": "Q01", "type": "normal", "question": "q", "relevant": ["D01", "D02"]},
        {"id": "Q01", "type": "trap", "question": "q", "relevant": ["D01"]},
        {"id": "Q03", "type": "normal", "question": "q", "relevant": ["D01", "D02", "D99"]},
    ]
    notes = runner.check_questions(questions, {"D01", "D02", "D03"})
    text = "\n".join(notes)
    assert "10 обычных" in text
    assert "повторяется id" in text
    assert "меньше 3" in text
    assert "у ловушки" in text
    assert "D99" in text


# ---------- прогон на маленьком корпусе ----------

def doc(doc_id, text, jurisdiction="ru"):
    return {"id": doc_id, "doc_title": "Тест", "jurisdiction": jurisdiction, "article": "ст. 1",
            "text": text, "url": "https://example.org", "edition": "тест"}


DOCS = [
    doc("A", "Возврат оплаты на карту."),
    doc("B", "Статус оплаты в приложении."),
    doc("C", "Возврат билета через кассу."),
    doc("D", "Расписание работы кассы."),
]
QUESTIONS = [
    {"id": "Q01", "type": "normal", "question": "Как происходит возврат оплаты?",
     "relevant": ["A", "B", "C"], "reference": "На карту"},
    {"id": "T01", "type": "trap", "question": "Сколько стоит парковка?", "relevant": [],
     "reference": "NO_ANSWER"},
]


@pytest.fixture
def questions_file(tmp_path):
    path = tmp_path / "questions.json"
    path.write_text(json.dumps(QUESTIONS, ensure_ascii=False), encoding="utf-8")
    return path


def test_run_retrieval_metrics(questions_file):
    result = runner.run(PLAIN, k=2, questions_path=questions_file, docs=DOCS)
    q1 = result["questions"][0]
    assert [f["id"] for f in q1["found"]] == ["A", "B"]
    assert q1["recall"] == pytest.approx(2 / 3) and q1["rr"] == 1.0
    assert result["metrics"]["recall@2"] == pytest.approx(2 / 3)
    assert result["metrics"]["mrr"] == 1.0
    assert result["metrics"]["accuracy"] is None                  # без ответов
    assert result["settings"]["k"] == 2 and result["settings"]["lemmatize"] is False
    assert "recall" not in result["questions"][1]                 # ловушки не входят в метрики поиска


def test_missing_questions_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        runner.load_questions(tmp_path / "nope.json")


def test_save_and_rescore(questions_file, tmp_path):
    result = runner.run(PLAIN, k=5, questions_path=questions_file, docs=DOCS)
    result["questions"][0]["correct"] = True                     # ручная разметка
    path = runner.save(result, "test", tmp_path)
    assert path.name.endswith("_test.json")
    rescored = runner.rescore(path)
    assert rescored["metrics"]["accuracy"] == 1.0
    assert json.loads(path.read_text(encoding="utf-8"))["metrics"]["accuracy"] == 1.0


def test_answers_through_api(questions_file, monkeypatch):
    pytest.importorskip("fastapi")
    from app import server
    monkeypatch.setattr(server, "MIN_SCORE", 0.1)
    original = server.search
    result = runner.run(PLAIN, k=5, answers=True, questions_path=questions_file, docs=DOCS)
    q1, t1 = result["questions"]
    assert q1["status"] == "ok" and q1["correct"] is None
    assert t1["status"] == "insufficient" and t1["rejected"] is True
    assert result["metrics"]["correct_rejection_rate"] == 1.0
    assert result["settings"]["min_score"] == 0.1
    assert server.search is original                             # API вернули к исходному поиску


def test_cli_runs_without_saving(questions_file, monkeypatch, capsys):
    monkeypatch.setattr(runner, "load_docs", lambda: DOCS)
    assert main(["--questions", str(questions_file), "--no-save", "--no-lemmatize"]) == 0
    out = capsys.readouterr().out
    assert "Recall@5" in out and "Q01" in out


def test_sweep_and_threshold_table(questions_file):
    rows = runner.sweep(PLAIN, 2, [1.2, 2.0], [0.75], questions_file, DOCS)
    assert [(r["k1"], r["b"]) for r in rows] == [(1.2, 0.75), (2.0, 0.75)]
    assert all(r["recall@2"] == pytest.approx(2 / 3) for r in rows)
    result = runner.run(PLAIN, k=5, questions_path=questions_file, docs=DOCS)
    table = runner.threshold_table(result["questions"], [0.1, 100])
    assert table[0]["normal_kept"] == 1 and table[0]["traps_rejected"] == 1   # T01 ничего не нашёл
    assert table[1]["normal_kept"] == 0 and table[1]["traps_rejected"] == 1
