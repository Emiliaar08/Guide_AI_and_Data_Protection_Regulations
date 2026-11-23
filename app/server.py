"""API и раздача интерфейса.

Запуск из корня проекта:  uvicorn app.server:app --reload --port 4173
"""
import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import answer

if os.getenv("RAG_SEARCH", "stub") == "real":
    from .search import search          # настоящий BM25
else:
    from .search_stub import search     # заглушка

K = int(os.getenv("RAG_K", "5"))                       # сколько фрагментов берём из поиска
MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "3.0"))   # ниже этого балла лучшего фрагмента: insufficient
EXCERPT_LEN = 300
APP_DIR = Path(__file__).resolve().parent


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    jurisdiction: Literal["ru", "eu"] | None = None


def _response(status: str, answer_text=None, question=None, citations=None) -> dict:
    return {
        "status": status,
        "answer": answer_text,
        "clarification_question": question,
        "citations": citations or [],
    }

def _excerpt(text: str, limit: int = EXCERPT_LEN) -> str:
    """Начало текста не длиннее limit, обрезка по границе слова, с многоточием."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:—-")
    return cut + "…"

def _citation(f) -> dict:
    return {
        "id": f.id,
        "doc_title": f.doc_title,
        "article": f.article,
        "excerpt": _excerpt(f.text),
        "jurisdiction": f.jurisdiction,
        "edition": f.edition,
        "url": f.url,
    }


async def run_search(query: str, jurisdiction: str | None = None) -> dict:
    """Весь путь запроса. Этой же функцией будет пользоваться benchmark."""
    fragments = search(query, jurisdiction, K)
    if not fragments or fragments[0].score < MIN_SCORE:
        return _response("insufficient")

    question = answer.needs_clarification(query, jurisdiction, fragments)
    if question:
        return _response("need_clarification", question=question)

    reply, cited = await answer.generate(query, fragments)
    if not cited:
        return _response("insufficient")
    return _response("ok", answer_text=reply, citations=[_citation(f) for f in cited])


app = FastAPI(title="Навигатор по нормативке")


@app.post("/api/search")
async def api_search(req: SearchRequest) -> dict:
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Запрос пустой")
    try:
        return await run_search(query, req.jurisdiction)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Не удалось получить ответ, попробуйте позже") from exc


class FrontendFiles(StaticFiles):
    """Раздаёт интерфейс, но не исходники сервера (.py) и прочие служебные файлы."""
    ALLOWED = {".html", ".css", ".js", ".svg", ".png", ".jpg", ".ico", ".woff2"}

    async def get_response(self, path, scope):
        suffix = Path(path).suffix.lower()
        if suffix and suffix not in self.ALLOWED:
            raise HTTPException(status_code=404)
        return await super().get_response(path, scope)


# Интерфейс подключаем после маршрутов, иначе он перехватит /api/search
app.mount("/", FrontendFiles(directory=APP_DIR, html=True), name="frontend")
