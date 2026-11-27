"""Тесты сборки корпуса (corpus/build.py) и готового corpus/docs.jsonl."""
from app.search import REQUIRED_FIELDS, load_docs
from corpus import build


def test_select_parts_with_subparts():
    lines = ["1. раз", "1) пункт", "1.1. подчасть", "2. два", "3. три", "3.1. три-один", "4. четыре"]
    assert build.select_parts(lines, "1", "2") == ["1. раз", "1) пункт", "1.1. подчасть", "2. два"]
    assert build.select_parts(lines, "3", "3") == ["3. три", "3.1. три-один"]


def test_editorial_lines_removed():
    lines = ["Статья 7. Конфиденциальность", "(в ред. Федерального закона от 25.07.2011 N 261-ФЗ)",
             "Операторы обязаны не раскрывать.", "КонсультантПлюс: примечание.", "Текст примечания.",
             "Ещё строка."]
    art = build.articles(lines)["7"]
    assert art["title"] == "Конфиденциальность"
    assert art["lines"] == ["Операторы обязаны не раскрывать.", "Ещё строка."]


def test_built_corpus_matches_docs_jsonl():
    docs = load_docs()
    assert [d["id"] for d in docs] == [d["id"] for d in build.build()]
    for d in docs:
        assert all(d[f] for f in REQUIRED_FIELDS)
        assert "в ред." not in d["text"] and "КонсультантПлюс" not in d["text"]
