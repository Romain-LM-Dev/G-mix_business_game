"""Estimation rapide du nombre de tokens, sans tokenizer, pour faire respecter les budgets.

~3,5 caractères par token en français pour les tokenizers BPE récents : volontairement pessimiste,
car Ollama tronque SILENCIEUSEMENT le début du contexte (donc le prompt système) quand num_ctx est dépassé.
"""

CHARS_PER_TOKEN = 3.5
MESSAGE_OVERHEAD = 4  # balises de rôle du template de chat


def estimate_tokens(text: str) -> int:
    return int(len(text) / CHARS_PER_TOKEN) + 1


def estimate_messages(messages: list[dict[str, str]]) -> int:
    return sum(estimate_tokens(m.get("content", "")) + MESSAGE_OVERHEAD for m in messages)


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    limit = int(max_tokens * CHARS_PER_TOKEN)
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + " …"
