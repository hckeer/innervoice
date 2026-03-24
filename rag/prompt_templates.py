"""
rag/prompt_templates.py

Prompt templates used by the RAG pipeline.
Each template uses Python .format() placeholder style.
"""

# ── Reply Suggestion ──────────────────────────────────────────────────────────

REPLY_SUGGESTION_TEMPLATE = """\
You are a helpful, empathetic, and friendly conversation assistant.
Your task is to suggest a natural, thoughtful reply to the latest message in\
 a conversation.

Here are some similar conversation examples for context:
{context}

Now, suggest a reply for the following conversation.
Keep your reply concise (1-3 sentences), conversational, and appropriate\
 for the tone of the message.

Conversation History:
{history}

Latest Message: {user_message}

Suggested Reply:"""

# ── Tone Adjustment ───────────────────────────────────────────────────────────

TONE_ADJUST_TEMPLATE = """\
Rewrite the following message in a {tone} tone.
Keep the core meaning intact but adjust the style accordingly.

Original message:
{message}

Rewritten ({tone} tone):"""

# ── Conversation Summarizer ───────────────────────────────────────────────────

SUMMARIZE_TEMPLATE = """\
Summarise the following conversation in 2-3 sentences.
Capture the main topics discussed and the overall tone.

Conversation:
{conversation}

Summary:"""

# ── Tone options ──────────────────────────────────────────────────────────────

TONE_OPTIONS = [
    "formal",
    "casual",
    "empathetic",
    "humorous",
    "professional",
    "supportive",
    "concise",
]


def build_reply_prompt(
    user_message: str,
    context: str,
    history: str = "",
) -> str:
    """Fill the reply suggestion template."""
    return REPLY_SUGGESTION_TEMPLATE.format(
        context=context,
        history=history or "(no prior history)",
        user_message=user_message,
    )


def build_tone_adjust_prompt(message: str, tone: str) -> str:
    return TONE_ADJUST_TEMPLATE.format(message=message, tone=tone)


def build_summarize_prompt(conversation: str) -> str:
    return SUMMARIZE_TEMPLATE.format(conversation=conversation)
