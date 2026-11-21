from fastapi.testclient import TestClient

from app import answer
from app.server import app

client = TestClient(app)
GOOD = "Нужно ли согласие на обработку персональных данных?"
TRAP = "Во сколько библиотека открыта в воскресенье?"
CITATION_FIELDS = {"doc_title", "article", "excerpt", "jurisdiction", "edition", "url"}


def post(query, jurisdiction=None):
    return client.post("/api/search", json={"query": query, "jurisdiction": jurisdiction})


def test_ok_has_answer_and_citations():
    r = post(GOOD)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"status", "answer", "clarification_question", "citations"}
    assert body["status"] == "ok" and body["answer"] and body["clarification_question"] is None
    assert body["citations"] and CITATION_FIELDS <= set(body["citations"][0])


def test_citations_only_for_cited_fragments(monkeypatch):
    async def llm(messages):
        return "Нужно согласие. [D01]"
    monkeypatch.setattr(answer, "call_llm", llm)
    body = post(GOOD).json()
    assert [c["id"] for c in body["citations"]] == ["D01"]


def test_insufficient_when_nothing_found_and_llm_not_called(monkeypatch):
    async def boom(messages):
        raise AssertionError("LLM не должен вызываться")
    monkeypatch.setattr(answer, "call_llm", boom)
    body = post(TRAP).json()
    assert body["status"] == "insufficient"
    assert body["answer"] is None and body["citations"] == []


def test_insufficient_when_score_below_threshold(monkeypatch):
    monkeypatch.setattr("app.server.MIN_SCORE", 99.0)
    assert post(GOOD).json()["status"] == "insufficient"


def test_insufficient_when_llm_cites_nothing(monkeypatch):
    async def llm(messages):
        return "Во фрагментах нет ответа."
    monkeypatch.setattr(answer, "call_llm", llm)
    assert post(GOOD).json()["status"] == "insufficient"

def test_insufficient_when_llm_cites_nothing(monkeypatch):
    async def llm(messages):
        return "Ответ без ссылок на фрагменты."
    monkeypatch.setattr(answer, "call_llm", llm)
    assert post(GOOD).json()["status"] == "insufficient"

def test_no_answer_marker_gives_insufficient(monkeypatch):
    async def llm(messages):
        return answer.NO_ANSWER
    monkeypatch.setattr(answer, "call_llm", llm)
    body = post(GOOD).json()
    assert body["status"] == "insufficient" and body["citations"] == []


def test_no_answer_marker_wins_over_citation(monkeypatch):
    async def llm(messages):
        return "NO_ANSWER, хотя тема близка к [D01]"
    monkeypatch.setattr(answer, "call_llm", llm)
    assert post(GOOD).json()["status"] == "insufficient"

def test_insufficient_when_llm_cites_unknown_id(monkeypatch):
    async def llm(messages):
        return "Выдуманный ответ. [D99]"
    monkeypatch.setattr(answer, "call_llm", llm)
    body = post(GOOD).json()
    assert body["status"] == "insufficient" and body["citations"] == []

def test_need_clarification_skips_llm(monkeypatch):
    async def boom(messages):
        raise AssertionError("LLM не должен вызываться")
    monkeypatch.setattr(answer, "call_llm", boom)
    monkeypatch.setattr(answer, "needs_clarification", lambda q, j, f: "Для какой юрисдикции?")
    body = post(GOOD).json()
    assert body["status"] == "need_clarification"
    assert body["clarification_question"] == "Для какой юрисдикции?"
    assert body["answer"] is None


def test_jurisdiction_filter():
    body = post("поставщик персональных данных обработка", "eu").json()
    assert body["status"] == "ok"
    assert {c["jurisdiction"] for c in body["citations"]} == {"eu"}
    body = post("персональных данных обработка согласие", "ru").json()
    assert {c["jurisdiction"] for c in body["citations"]} == {"ru"}


def test_validation():
    assert client.post("/api/search", json={"query": ""}).status_code == 422
    assert client.post("/api/search", json={"query": "   "}).status_code == 422
    assert client.post("/api/search", json={}).status_code == 422
    assert post(GOOD, "us").status_code == 422


def test_llm_failure_gives_502(monkeypatch):
    async def fail(messages):
        raise RuntimeError("api down")
    monkeypatch.setattr(answer, "call_llm", fail)
    assert post(GOOD).status_code == 502


def test_messages_contain_instruction_and_ids():
    class F:  # минимальный фрагмент
        id, doc_title, article, text = "D01", "Док", "ст. 1", "текст"
    msgs = answer.build_messages("вопрос", [F()])
    assert msgs[0]["role"] == "system" and "id фрагмента" in msgs[0]["content"]
    assert "[D01]" in msgs[1]["content"] and "вопрос" in msgs[1]["content"]


def test_frontend_served_but_not_server_sources():
    assert client.get("/").status_code == 200
    assert client.get("/app.js").status_code == 200
    assert client.get("/server.py").status_code == 404
    assert client.get("/answer.py").status_code == 404

def test_excerpt_cut_on_word_boundary():
    from app.server import _excerpt
    ex = _excerpt("слово " * 100, 50)
    assert ex.endswith("…") and len(ex) <= 51
    assert ex[:-1].split(" ")[-1] == "слово"
    assert _excerpt("короткий текст", 50) == "короткий текст"


def test_prompt_demands_no_answer_marker():
    assert answer.NO_ANSWER in answer.build_messages("q", [])[0]["content"]
