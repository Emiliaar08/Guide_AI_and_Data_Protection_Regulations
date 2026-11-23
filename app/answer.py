"""Ответ: вызов LLM по найденным фрагментам и проверка цитат."""
import re
import os
import httpx

NO_ANSWER = "NO_ANSWER"   # маркер отказа: по нему API и benchmark отличают отказ модели от ответа

SYSTEM_PROMPT = (
    "Отвечай только по приведённым фрагментам. К каждому утверждению указывай id фрагмента "
    "в квадратных скобках, например [D01]. Если в фрагментах нет ответа на вопрос, "
    f"верни ровно {NO_ANSWER} и ничего больше."
)


def build_context(fragments) -> str:
    return "\n".join(f"[{f.id}] {f.doc_title}, {f.article}: {f.text}" for f in fragments)


def build_messages(query: str, fragments) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Вопрос: {query}\n\nФрагменты:\n{build_context(fragments)}"},
    ]


async def call_llm(messages: list[dict]) -> str:
    base = os.getenv("LLM_BASE_URL")
    if not base:   # провайдер не задан: старая заглушка
        ids = re.findall(r"^\[([^\]]+)\]", messages[-1]["content"], flags=re.M)
        if not ids:
            return NO_ANSWER
        return f"(заглушка LLM) Ответ собран по найденному тексту. [{ids[0]}]"
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(
            base.rstrip("/") + "/chat/completions",
            headers={"Authorization": "Bearer " + os.getenv("LLM_API_KEY", "none")},
            json={"model": os.environ["LLM_MODEL"], "messages": messages, "temperature": 0},
        )
        r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    text = msg.get("content") or ""     # у модели с рассуждениями content может прийти пустым
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def needs_clarification(query: str
, jurisdiction: str | None, fragments) -> str | None:
    """Вернуть уточняющий вопрос или None. ПРАВИЛО НЕ ОПРЕДЕЛЕНО (открытый вопрос в rag.md), пока всегда None."""
    return None


async def generate(query: str, fragments):
    """Вернуть (текст ответа, фрагменты, на которые он реально сослался).

    Цитаты берём из найденных фрагментов, а не из текста модели: id, которых нет среди найденных, отбрасываются.
    """
    reply = await call_llm(build_messages(query, fragments))
    if NO_ANSWER in reply:      # отказ модели; даже если она при этом упомянула [id], ответа нет
        return NO_ANSWER, []
    by_id = {f.id: f for f in fragments}
    cited = []
    for frag_id in re.findall(r"\[([^\]]+)\]", reply):
        if frag_id in by_id and by_id[frag_id] not in cited:
            cited.append(by_id[frag_id])
    return reply, cited
