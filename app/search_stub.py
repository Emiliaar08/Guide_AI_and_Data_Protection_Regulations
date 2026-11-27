"""ЗАГЛУШКА поиска. Настоящий поиск (BM25) пишет отдельная ветка в app/search.py.

Контракт, который обязан соблюдать и настоящий поиск:
    search(query: str, jurisdiction: str | None, k: int) -> list[фрагмент]
Фрагмент: объект с полями id, doc_title, jurisdiction ("ru" | "eu"), article, text, url, edition, score.
Список отсортирован по убыванию score. Если выбрана юрисдикция, ищем только в её документах.
"""
import re
from dataclasses import dataclass


@dataclass
class Fragment:
    id: str
    doc_title: str
    jurisdiction: str
    article: str
    text: str
    url: str
    edition: str
    score: float = 0.0


# Тексты тестовые, это НЕ цитаты законов. Статьи и ссылки взяты из rag.md и app.js.
_RU = "https://mintrud.gov.ru/docs/laws/130"
_GDPR = "https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng"
_AIACT = "https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng"
_CORPUS = [
    Fragment("D01", "152-ФЗ «О персональных данных»", "ru", "ст. 6", "[ТЕСТ] Оператор персональных данных обязан получить согласие субъекта на обработку.", _RU, "заглушка"),
    Fragment("D02", "152-ФЗ «О персональных данных»", "ru", "ст. 12", "[ТЕСТ] Трансграничная передача персональных данных допускается при соблюдении условий закона.", _RU, "заглушка"),
    Fragment("D03", "GDPR (Регламент ЕС 2016/679)", "eu", "ст. 28", "[ТЕСТ] Поставщик, обрабатывающий персональные данные по поручению, действует на основании договора.", _GDPR, "заглушка"),
    Fragment("D04", "AI Act (Регламент ЕС 2024/1689)", "eu", "ст. 14", "[ТЕСТ] Системы искусственного интеллекта высокого риска требуют человеческого надзора.", _AIACT, "заглушка"),
]


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", text.lower()) if len(w) >= 4}


def search(query: str, jurisdiction: str | None = None, k: int = 5) -> list[Fragment]:
    q = _tokens(query)
    found = []
    for frag in _CORPUS:
        if jurisdiction and frag.jurisdiction != jurisdiction:
            continue
        score = len(q & _tokens(frag.text))
        if score > 0:
            found.append(Fragment(**{**frag.__dict__, "score": float(score)}))
    found.sort(key=lambda f: (-f.score, f.id))
    return found[:k]
