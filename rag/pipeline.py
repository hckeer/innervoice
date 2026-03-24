"""
rag/pipeline.py

End-to-end RAG pipeline that ties together:
  Retriever → prompt template → LLMClient → reply

Usage:
    from rag.pipeline import RAGPipeline
    pipeline = RAGPipeline()
    result = pipeline.suggest_reply("Hey, what's up?")
    print(result["reply"])
    print(result["context"])
"""

from typing import Generator
from config import GROQ_MODEL, TOP_K, MAX_TOKENS, TEMPERATURE
from rag.retriever import Retriever
from rag.llm_client import LLMClient
from rag.prompt_templates import (
    build_reply_prompt,
    build_tone_adjust_prompt,
    build_summarize_prompt,
)


class RAGPipeline:
    """
    Orchestrates the full RAG flow:
      1. Retrieve relevant examples from FAISS
      2. Build a prompt with retrieved context
      3. Generate a reply via Groq
    """

    def __init__(
        self,
        model: str | None = None,
        top_k: int | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> None:
        self.model = model or GROQ_MODEL
        self.top_k = top_k or TOP_K
        self.max_tokens = max_tokens or MAX_TOKENS
        self.temperature = temperature if temperature is not None else TEMPERATURE

        self.retriever = Retriever()
        self.llm = LLMClient()

    # ── Core: suggest reply ───────────────────────────────────────────────────

    def suggest_reply(
        self,
        user_message: str,
        history: str = "",
        k: int | None = None,
    ) -> dict:
        """
        Full RAG pipeline: retrieve → prompt → generate.

        Returns:
            {
                "reply":    suggested reply string,
                "context":  formatted context string shown in UI,
                "prompt":   full prompt sent to LLM,
                "sources":  list of {input, response, score} dicts,
            }
        """
        k = k or self.top_k

        # 1. Retrieve
        sources = self.retriever.search(user_message, k=k)
        context = self.retriever.get_context(user_message, k=k)

        # 2. Build prompt
        prompt = build_reply_prompt(
            user_message=user_message,
            context=context,
            history=history,
        )

        # 3. Generate
        reply = self.llm.generate(prompt)

        return {
            "reply": reply,
            "context": context,
            "prompt": prompt,
            "sources": sources,
        }

    def stream_reply(
        self,
        user_message: str,
        history: str = "",
        k: int | None = None,
    ) -> tuple[Generator, str, list[dict]]:
        """
        Returns (token_generator, context_string, sources) for streaming UIs.
        """
        k = k or self.top_k
        sources = self.retriever.search(user_message, k=k)
        context = self.retriever.get_context(user_message, k=k)
        prompt = build_reply_prompt(
            user_message=user_message,
            context=context,
            history=history,
        )
        reply = self.llm.generate(prompt)
        def mock_gen():
            yield reply
        gen = mock_gen()
        return gen, context, sources

    # ── Tone adjustment ───────────────────────────────────────────────────────

    def adjust_tone(self, message: str, tone: str) -> str:
        prompt = build_tone_adjust_prompt(message=message, tone=tone)
        return self.llm.generate(prompt)

    # ── Summarization ─────────────────────────────────────────────────────────

    def summarize(self, conversation: str) -> str:
        prompt = build_summarize_prompt(conversation=conversation)
        return self.llm.generate(prompt)

    # ── Stats ─────────────────────────────────────────────────────────────────

    @property
    def corpus_size(self) -> int:
        try:
            return self.retriever.corpus_size
        except Exception:
            return 0

    def reload_index(self) -> None:
        self.retriever.reload()
