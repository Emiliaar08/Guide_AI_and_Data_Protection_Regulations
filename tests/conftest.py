"""Тесты не зависят от рабочих переменных окружения.

Убираем настройки модели и поиска до импорта приложения: даже если в окне заданы
LLM_* и RAG_*, тесты идут на заглушки. DATABASE_URL и REDIS_URL не трогаем:
они нужны тестам аккаунтов и рабочего пространства.
"""
import os

for name in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY", "RAG_SEARCH", "RAG_MIN_SCORE"):
    os.environ.pop(name, None)
