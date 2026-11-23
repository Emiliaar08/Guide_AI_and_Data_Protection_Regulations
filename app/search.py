"""Поиск BM25 по корпусу нормативных актов.

Спецификация: spec/tech/rag.md (разделы «Предобработка» и «Поиск»).
Контракт для API (architecture.md, «Правила API»):

    search(query: str, jurisdiction: str | None = None, k: int = 5) -> list[Fragment]

Индекс BM25 написан самостоятельно: готовые поисковые индексы методичка запрещает.
Из сторонних библиотек используется только pymorphy3 для лемматизации.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = ROOT / "corpus"
DOCS_PATH = CORPUS_DIR / "docs.jsonl"
STOPWORDS_PATH = CORPUS_DIR / "stopwords.txt"
SYNONYMS_PATH = CORPUS_DIR / "synonyms.json"

REQUIRED_FIELDS = ("id", "doc_title", "jurisdiction", "article", "text", "url", "edition")
INDEXED_FIELDS = ("doc_title", "article", "text")

# Токен: число (в том числе «18.1» и «2016/679») или слово из русских либо латинских букв.
# Дефис в регулярку не входит, поэтому «ИИ-системы» делится на «ИИ» и «системы».
TOKEN_RE = re.compile(r"\d+(?:[./]\d+)*|[a-zA-Zа-яА-ЯёЁ]+")
CYRILLIC_RE = re.compile(r"[а-яё]", re.IGNORECASE)


@dataclass
class Fragment:
    """Найденный документ. Поля совпадают с заглушкой app/search_stub.py."""
    id: str
    doc_title: str
    jurisdiction: str
    article: str
    text: str
    url: str
    edition: str
    score: float = 0.0
    text_original: str = ""
    source: str = ""


@dataclass(frozen=True)
class Options:
    """Настройки предобработки и BM25. Каждый шаг выключается отдельно для экспериментов бенчмарка."""
    lowercase: bool = True      # нижний регистр и «ё» → «е»
    lemmatize: bool = True      # pymorphy3, первый разбор
    synonyms: bool = True       # corpus/synonyms.json
    stopwords: bool = True      # corpus/stopwords.txt
    k1: float = 1.2
    b: float = 0.75


# ---------- предобработка ----------

@lru_cache(maxsize=1)
def _morph():
    try:
        import pymorphy3
    except ImportError as exc:
        raise ImportError(
            "Для лемматизации нужен pymorphy3: pip install -r requirements.txt "
            "(или Options(lemmatize=False))"
        ) from exc
    return pymorphy3.MorphAnalyzer()


@lru_cache(maxsize=100_000)
def _lemma(word: str) -> str:
    """Начальная форма самого вероятного разбора. Латиница и числа не лемматизируются."""
    if not CYRILLIC_RE.search(word):
        return word
    return _morph().parse(word)[0].normal_form.replace("ё", "е")


class Preprocessor:
    """Превращает текст в список термов. Документы и запросы проходят одну и ту же обработку."""

    def __init__(self, options: Options = Options(), stopwords=(), synonyms=None):
        self.options = options
        self.stopwords = {self._normalize_word(w) for w in stopwords} if options.stopwords else set()
        self.phrases: dict[tuple[str, ...], str] = {}
        if options.synonyms and synonyms:
            for canonical, variants in synonyms.items():
                term = "_".join(self._base_terms(canonical))
                for variant in [canonical, *variants]:
                    key = tuple(self._base_terms(variant))
                    if key:
                        self.phrases[key] = term
        self.max_phrase = max((len(p) for p in self.phrases), default=0)

    def _normalize_word(self, word: str) -> str:
        terms = self._base_terms(word)
        return terms[0] if terms else ""

    def _base_terms(self, text: str) -> list[str]:
        """Регистр, токенизация и лемматизация — без синонимов и стоп-слов."""
        if self.options.lowercase:
            text = text.lower().replace("ё", "е")
        words = TOKEN_RE.findall(text)
        if self.options.lemmatize:
            words = [_lemma(w) for w in words]   # pymorphy3 возвращает начальную форму в нижнем регистре
        return words

    def _apply_synonyms(self, terms: list[str]) -> list[str]:
        if not self.phrases:
            return terms
        out, i = [], 0
        while i < len(terms):
            for size in range(min(self.max_phrase, len(terms) - i), 0, -1):
                term = self.phrases.get(tuple(terms[i:i + size]))
                if term:
                    # Слово заменяется общим термом. Фраза остаётся как есть, а общий терм
                    # добавляется после неё: иначе её слова («поручение») пропали бы из индекса.
                    if size > 1:
                        out.extend(terms[i:i + size])
                    out.append(term)
                    i += size
                    break
            else:
                out.append(terms[i])
                i += 1
        return out

    def terms(self, text: str) -> list[str]:
        terms = self._apply_synonyms(self._base_terms(text))
        if self.stopwords:
            terms = [t for t in terms if t not in self.stopwords]
        return terms


# ---------- индекс и поиск ----------

class Index:
    """Обратный индекс «терм → документ → число вхождений» и оценка BM25."""

    def __init__(self, docs: list[dict], preprocessor: Preprocessor | None = None):
        self.pre = preprocessor or Preprocessor()
        self.docs = {d["id"]: d for d in docs}
        self.postings: dict[str, dict[str, int]] = defaultdict(dict)
        self.lengths: dict[str, int] = {}
        for doc_id, doc in self.docs.items():
            text = " ".join(str(doc.get(f, "")) for f in INDEXED_FIELDS)
            terms = self.pre.terms(text)
            self.lengths[doc_id] = len(terms)
            for term, tf in Counter(terms).items():
                self.postings[term][doc_id] = tf
        self.n = len(self.docs)
        self.avgdl = (sum(self.lengths.values()) / self.n) if self.n else 0.0

    def idf(self, term: str) -> float:
        df = len(self.postings.get(term, {}))
        return math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    def scores(self, query: str) -> dict[str, float]:
        k1, b = self.pre.options.k1, self.pre.options.b
        result: dict[str, float] = defaultdict(float)
        for term in dict.fromkeys(self.pre.terms(query)):   # повторы слов запроса — один раз
            postings = self.postings.get(term)
            if not postings:
                continue
            idf = self.idf(term)
            for doc_id, tf in postings.items():
                norm = k1 * (1 - b + b * self.lengths[doc_id] / self.avgdl)
                result[doc_id] += idf * tf * (k1 + 1) / (tf + norm)
        return result

    def search(self, query: str, jurisdiction: str | None = None, k: int = 5) -> list[Fragment]:
        if k <= 0:
            return []
        scored = [
            (doc_id, score) for doc_id, score in self.scores(query).items()
            if jurisdiction is None or self.docs[doc_id]["jurisdiction"] == jurisdiction
        ]
        scored.sort(key=lambda item: (-item[1], item[0]))   # при равенстве — по id
        return [self._fragment(doc_id, score) for doc_id, score in scored[:k]]

    def _fragment(self, doc_id: str, score: float) -> Fragment:
        doc = self.docs[doc_id]
        return Fragment(
            **{f: doc[f] for f in REQUIRED_FIELDS},
            score=score,
            text_original=doc.get("text_original", ""),
            source=doc.get("source", ""),
        )


# ---------- загрузка корпуса ----------

def load_docs(path: Path = DOCS_PATH) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Корпус не найден: {path}. Соберите corpus/docs.jsonl (см. corpus/README.md).")
    docs, seen = [], set()
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        doc = json.loads(line)
        missing = [f for f in REQUIRED_FIELDS if not doc.get(f)]
        if missing:
            raise ValueError(f"{path.name}, строка {line_no}: нет полей {', '.join(missing)}")
        if doc["id"] in seen:
            raise ValueError(f"{path.name}, строка {line_no}: повторяется id {doc['id']}")
        seen.add(doc["id"])
        docs.append(doc)
    return docs


def load_stopwords(path: Path = STOPWORDS_PATH) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [w.strip() for w in lines if w.strip() and not w.lstrip().startswith("#")]


def load_synonyms(path: Path = SYNONYMS_PATH) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def build_index(options: Options = Options(), docs: list[dict] | None = None) -> Index:
    """Индекс по корпусу с заданными настройками. Бенчмарк вызывает её для экспериментов."""
    pre = Preprocessor(options, load_stopwords(), load_synonyms())
    return Index(load_docs() if docs is None else docs, pre)


@lru_cache(maxsize=1)
def default_index() -> Index:
    return build_index()


def search(query: str, jurisdiction: str | None = None, k: int = 5) -> list[Fragment]:
    """Контракт для API: до k фрагментов по убыванию score. Порог MIN_SCORE проверяет API."""
    return default_index().search(query, jurisdiction, k)
