"""Тесты поиска BM25 (app/search.py). Спецификация: spec/tech/rag.md."""
import json
import math

import pytest

from app import search as s

PLAIN = s.Options(lemmatize=False, synonyms=False, stopwords=False)


def doc(doc_id, text, jurisdiction="ru", doc_title="", article="", **extra):
    return {"id": doc_id, "doc_title": doc_title, "jurisdiction": jurisdiction, "article": article,
            "text": text, "url": "https://example.org", "edition": "тест", **extra}


def index(docs, options=PLAIN, stopwords=(), synonyms=None):
    return s.Index(docs, s.Preprocessor(options, stopwords, synonyms))


# ---------- пример со слайдов занятия 3 ----------

SLIDE_DOCS = [
    doc("A", "Возврат оплаты на карту."),
    doc("B", "Статус оплаты в приложении."),
    doc("C", "Возврат билета через кассу."),
]
SLIDE_QUERY = "Как происходит возврат оплаты?"


def test_slide_example_scores():
    idx = index(SLIDE_DOCS)
    assert idx.n == 3 and idx.avgdl == 4
    assert idx.idf("возврат") == pytest.approx(math.log(1.6))       # ≈ 0,470
    scores = idx.scores(SLIDE_QUERY)
    assert scores["A"] == pytest.approx(0.940, abs=1e-3)
    assert scores["B"] == pytest.approx(0.470, abs=1e-3)
    assert scores["C"] == pytest.approx(0.470, abs=1e-3)


def test_slide_example_top2_ties_by_id():
    found = index(SLIDE_DOCS).search(SLIDE_QUERY, k=2)
    assert [f.id for f in found] == ["A", "B"]


# ---------- контракт для API ----------

def test_fragment_has_api_fields_and_sorted_by_score():
    found = index(SLIDE_DOCS).search(SLIDE_QUERY)
    assert [f.id for f in found] == ["A", "B", "C"]
    f = found[0]
    for field in ("id", "doc_title", "jurisdiction", "article", "text", "url", "edition", "score"):
        assert hasattr(f, field)
    assert isinstance(f.score, float)
    assert all(a.score >= b.score for a, b in zip(found, found[1:]))


def test_positional_call_like_server():
    idx = index(SLIDE_DOCS)
    assert [f.id for f in idx.search(SLIDE_QUERY, None, 1)] == ["A"]


def test_nothing_found_returns_empty_list():
    assert index(SLIDE_DOCS).search("расписание библиотеки") == []


def test_k_zero_returns_empty_list():
    assert index(SLIDE_DOCS).search(SLIDE_QUERY, k=0) == []


def test_jurisdiction_filter():
    docs = [doc("D01", "согласие субъекта", "ru"), doc("D02", "согласие субъекта данных", "eu")]
    idx = index(docs)
    assert [f.id for f in idx.search("согласие", "eu")] == ["D02"]
    assert [f.id for f in idx.search("согласие", "ru")] == ["D01"]
    assert {f.id for f in idx.search("согласие", None)} == {"D01", "D02"}


def test_repeated_query_words_counted_once():
    idx = index(SLIDE_DOCS)
    assert idx.scores("возврат возврат оплаты") == pytest.approx(idx.scores("возврат оплаты"))


def test_extra_fields_passed_through():
    docs = [doc("D01", "processor contract", "eu", text_original="processor", source="gdpr-text.com")]
    f = index(docs).search("processor")[0]
    assert f.text_original == "processor" and f.source == "gdpr-text.com"


# ---------- предобработка ----------

def test_tokens_numbers_hyphen_and_yo():
    pre = s.Preprocessor(PLAIN)
    assert pre.terms("Статья 18.1 Регламента 2016/679") == ["статья", "18.1", "регламента", "2016/679"]
    assert pre.terms("ИИ-системы") == ["ии", "системы"]
    assert pre.terms("Контролёр") == pre.terms("контролер")


def test_title_and_article_are_indexed():
    docs = [doc("D01", "договор с процессором", "eu", doc_title="GDPR", article="ст. 28"),
            doc("D02", "законность обработки", "eu", doc_title="GDPR", article="ст. 6")]
    found = index(docs).search("ст. 28 GDPR")
    assert found[0].id == "D01"


def test_synonyms_phrase_and_abbreviation():
    syn = {"процессор": ["лицо осуществляющее обработку по поручению"], "статья": ["ст"]}
    docs = [doc("D01", "Лицо, осуществляющее обработку по поручению, соблюдает принципы.", article="ст. 6"),
            doc("D02", "Оператор публикует политику.", article="ст. 18.1")]
    idx = index(docs, options=s.Options(lemmatize=False, stopwords=False), synonyms=syn)
    assert idx.search("процессор")[0].id == "D01"
    assert idx.search("статья 18.1")[0].id == "D02"


def test_stopwords_removed_but_not_negation():
    pre = s.Preprocessor(s.Options(lemmatize=False, synonyms=False), stopwords=["в", "и", "для"])
    assert pre.terms("в целях и для обработки не допускается") == ["целях", "обработки", "не", "допускается"]


def test_each_step_can_be_switched_off():
    pre = s.Preprocessor(PLAIN, stopwords=["и"], synonyms={"оператор": ["контролер"]})
    assert pre.terms("контролер и данные") == ["контролер", "и", "данные"]


# ---------- лемматизация (нужен pymorphy3) ----------

def test_lemmatization_matches_word_forms():
    pytest.importorskip("pymorphy3")
    docs = [doc("D01", "Обработка персональных данных допускается с согласия субъекта."),
            doc("D02", "Оператор публикует политику.")]
    idx = index(docs, options=s.Options(synonyms=False, stopwords=False))
    assert idx.search("персональные данные")[0].id == "D01"
    assert idx.search("согласие")[0].id == "D01"


def test_synonyms_after_lemmatization():
    pytest.importorskip("pymorphy3")
    syn = {"оператор": ["контролер"]}
    docs = [doc("D01", "Оператор обязан получить согласие."), doc("D02", "Статус оплаты.")]
    idx = index(docs, options=s.Options(stopwords=False), synonyms=syn)
    assert idx.search("обязанности контролёра")[0].id == "D01"


# ---------- загрузка корпуса ----------

def test_missing_corpus_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        s.load_docs(tmp_path / "docs.jsonl")


def test_load_docs_validates(tmp_path):
    path = tmp_path / "docs.jsonl"
    good = doc("D01", "текст", doc_title="152-ФЗ", article="ст. 6")
    path.write_text(json.dumps(good, ensure_ascii=False) + "\n" + json.dumps(good, ensure_ascii=False),
                    encoding="utf-8")
    with pytest.raises(ValueError, match="повторяется id"):
        s.load_docs(path)
    path.write_text(json.dumps({"id": "D01", "text": "x"}, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="нет полей"):
        s.load_docs(path)


def test_stopwords_and_synonyms_files_load():
    words = s.load_stopwords()
    assert "и" in words and "не" not in words
    syn = s.load_synonyms()
    assert "_comment" not in syn and "статья" in syn
