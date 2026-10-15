"""Tools that let the agent save and forget long-term facts about you."""

from agent.memory import get_memory
from agent.texts import say
from agent.tooling import tool

MAX_FACT_CHARS = 300


@tool(risk=lambda a: say(f"이 내용을 계속 기억해요 (앞으로 모든 대화에 쓰여요):\n{a.get('fact', '')}",
                         f"Remembers this permanently (used in all future conversations):\n{a.get('fact', '')}"))
def remember(fact: str) -> dict:
    """Save a lasting fact or preference about the user for future conversations,
    e.g. "My project folder is D:\\Work\\Projects" or "Prefers replies in Korean".

    Args:
      fact: One short, self-contained sentence.
    """
    fact = " ".join(fact.split())
    if len(fact) > MAX_FACT_CHARS:
        return {"error": f"Too long. Save one short fact (max {MAX_FACT_CHARS} characters)."}
    entry = get_memory().add(fact)
    return {"saved": entry}


@tool(risk=lambda a: say(f"기억 [{a.get('fact_id')}]번을 지워요.", f"Forgets memory [{a.get('fact_id')}]."))
def forget(fact_id: int) -> dict:
    """Delete a saved fact by its number (shown as [n] in the memory list).

    Args:
      fact_id: The number of the fact to delete.
    """
    removed = get_memory().remove(int(fact_id))
    return {"removed": removed} if removed else {"error": f"No saved fact with number {fact_id}"}
