"""Tools that let the agent save and forget long-term facts about you."""

from agent.memory import get_memory
from agent.tooling import tool


@tool()
def remember(fact: str) -> dict:
    """Save a lasting fact or preference about the user for future conversations,
    e.g. "My project folder is D:\\Work\\Projects" or "Prefers replies in Korean".

    Args:
      fact: One short, self-contained sentence.
    """
    entry = get_memory().add(fact)
    return {"saved": entry}


@tool()
def forget(fact_id: int) -> dict:
    """Delete a saved fact by its number (shown as [n] in the memory list).

    Args:
      fact_id: The number of the fact to delete.
    """
    removed = get_memory().remove(int(fact_id))
    return {"removed": removed} if removed else {"error": f"No saved fact with number {fact_id}"}
