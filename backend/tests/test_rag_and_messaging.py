import re

from gmix.llm.tokens import estimate_tokens
from gmix.messaging.envelope import Envelope
from gmix.messaging.topics import ALL_TOPICS
from gmix.rag.chunking import split_into_chunks
from gmix.rag.retrieval import Hit, build_context


def test_chunks_respect_budget_and_overlap() -> None:
    text = "\n\n".join(f"Paragraphe {i}. La trésorerie nette vaut FR moins BFR." for i in range(40))
    chunks = split_into_chunks(text, max_tokens=120, overlap_tokens=30)
    assert len(chunks) > 1
    assert all(estimate_tokens(chunk) <= 120 for chunk in chunks)
    first, second = chunks[0].split("\n\n"), chunks[1].split("\n\n")
    shared = [unit for unit in second if unit in first]
    assert shared and shared == first[-len(shared) :]  # le passage suivant reprend la fin du précédent
    assert estimate_tokens("".join(shared)) <= 30


def test_long_paragraph_is_split_by_sentences() -> None:
    paragraph = " ".join(f"Phrase numéro {i} sur le besoin en fonds de roulement." for i in range(80))
    chunks = split_into_chunks(paragraph, max_tokens=100, overlap_tokens=0)
    assert len(chunks) > 1
    assert all(estimate_tokens(chunk) <= 100 for chunk in chunks)


def test_empty_text_gives_no_chunk() -> None:
    assert split_into_chunks("  \n\n ") == []


def test_context_is_numbered_and_fits_budget() -> None:
    hits = [Hit(i, "doc", f"Titre {i}", "contenu " * 60, {"page": i}, 1.0) for i in range(1, 6)]
    context, sources = build_context(hits, max_tokens=300)
    assert context.startswith("[S1] Titre 1, p. 1")
    assert estimate_tokens(context) <= 300 + len(sources)
    assert [s["ref"] for s in sources] == [f"S{i}" for i in range(1, len(sources) + 1)]


async def test_presigned_urls_target_the_public_endpoint(monkeypatch) -> None:
    """Jeu en réseau : l'URL donnée au joueur doit viser l'adresse qu'il peut joindre (S3_PUBLIC_ENDPOINT)."""
    from gmix import storage
    from gmix.settings import Settings

    monkeypatch.setattr(storage, "get_settings", lambda: Settings(s3_public_endpoint="http://192.168.1.20:9000"))
    storage.s3_client.cache_clear()
    try:
        url = await storage.presigned_get_url("gmix-assets", "buildings/bld_office_small.glb")
    finally:
        storage.s3_client.cache_clear()
    assert url.startswith("http://192.168.1.20:9000/gmix-assets/buildings/bld_office_small.glb?")


def test_topics_are_unique_and_follow_naming_convention() -> None:
    names = [topic.name for topic in ALL_TOPICS]
    assert len(names) == len(set(names))
    assert all(re.fullmatch(r"gmix(\.[a-z_]+)+", name) for name in names)


def test_envelope_roundtrip_and_reply_keep_correlation() -> None:
    event = Envelope(type="system.ping", source="test", client_id="godot-1", payload={"message": "ping"})
    assert Envelope.from_bytes(event.to_bytes()) == event
    reply = event.reply("system.pong", "worker", {"ok": True})
    assert reply.correlation_id == event.id
    assert reply.causation_id == event.id
    assert reply.client_id == "godot-1"
    assert set(reply.to_client()) == {"type", "payload", "meta"}
