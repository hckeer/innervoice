"""
rag/personality_engine.py

Personality-driven prompt construction for romantic, emotionally intelligent responses.
"""

from typing import List, Dict
from rag.emotion_detector import Emotion


class PersonalityEngine:
    """
    Builds prompts that enforce consistent romantic personality.
    """
    
    SYSTEM_PERSONA = """You are a warm, charming conversation partner with a romantic soul. Your style:

• Natural and human - you don't sound like an AI or assistant
• Emotionally intelligent - you read between the lines and respond to subtext  
• Playfully romantic - subtle flirtation, not over the top
• Authentic - you have slight imperfections, moments of hesitation, very human phrasing
• Present and engaged - you reference what was said, build on the conversation
• Concise but meaningful - 1-2 sentences, every word counts

You are NOT:
- A helpful assistant or chatbot
- Overly formal or robotic
- Generic or predictable
- Long-winded or preachy"""

    GROUNDING_RULES = """IMPORTANT CONSTRAINTS:

• Base your response on the conversation examples below - mirror their emotional tone and naturalness
• If the examples are romantic/flirty, your response should match that energy
• Keep responses SHORT (1-2 sentences max) - brevity creates intimacy
• Use contractions, casual phrasing, even fragments - sound human
• NO generic phrases like "I'm here to help" or "How can I assist"
• If you don't have good context, respond authentically but vaguely (like a real person would)"""

    EMOTION_GUIDANCE = {
        Emotion.ROMANTIC: "The conversation has romantic undertones. Respond with warmth and subtle affection, but keep it natural - no cheesy lines.",
        Emotion.FLIRTY: "There's playful energy here. Match the flirtation - be charming but not over the top. A little tease, a little warmth.",
        Emotion.PLAYFUL: "Keep it light and fun. Banter a bit, maybe throw in some humor. Enjoy the moment.",
        Emotion.SAD: "They're hurting. Be gentle and present. Don't try to fix it - just be there. Softness matters here.",
        Emotion.SERIOUS: "This is important to them. Be thoughtful and genuine. Give them your full attention.",
        Emotion.CURIOUS: "They want to know more. Be engaging and give them something real to hold onto.",
        Emotion.SUPPORTIVE: "Be their anchor. Steady, warm, believing in them.",
        Emotion.NEUTRAL: "Read the energy and respond naturally. Build connection."
    }

    def build_messages(
        self,
        user_message: str,
        context_examples: List[Dict],
        conversation_history: List[Dict],
        detected_emotion: Emotion
    ) -> List[Dict[str, str]]:
        """
        Build message list for LLM with personality enforcement.
        
        Args:
            user_message: Current user input
            context_examples: Retrieved similar conversations
            conversation_history: Recent message history
            detected_emotion: Detected emotional tone
            
        Returns:
            List of {role, content} message dicts
        """
        messages = []
        
        # 1. System message with persona
        system_content = f"{self.SYSTEM_PERSONA}\n\n{self.GROUNDING_RULES}"
        
        # Add emotion-specific guidance
        if detected_emotion in self.EMOTION_GUIDANCE:
            system_content += f"\n\nEMOTIONAL CONTEXT: {self.EMOTION_GUIDANCE[detected_emotion]}"
        
        messages.append({"role": "system", "content": system_content})
        
        # 2. Context from retrieval (as user message showing examples)
        if context_examples:
            context_text = self._format_context(context_examples)
            messages.append({
                "role": "user",
                "content": f"Here are some relevant conversation examples to learn from:\n\n{context_text}"
            })
            messages.append({
                "role": "assistant",
                "content": "I see the tone and style in these examples. I'll match that energy naturally."
            })
        
        # 3. Recent conversation history (last 3 exchanges max)
        if conversation_history:
            history_text = self._format_history(conversation_history[-6:])  # Last 3 turns
            messages.append({
                "role": "user",
                "content": f"Here's our recent conversation:\n{history_text}"
            })
            messages.append({
                "role": "assistant",
                "content": "Got it, I remember where we are."
            })
        
        # 4. Current user message
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        return messages
    
    def _format_context(self, examples: List[Dict]) -> str:
        """Format retrieved examples naturally."""
        lines = []
        for i, ex in enumerate(examples[:3], 1):  # Top 3 only
            score = ex.get("score", 0) * 100
            lines.append(f"Example {i} (relevance: {score:.0f}%):")
            lines.append(f"  Them: {ex['input']}")
            lines.append(f"  Response: {ex['response']}\n")
        
        return "\n".join(lines)
    
    def _format_history(self, history: List[Dict]) -> str:
        """Format conversation history."""
        lines = []
        for msg in history:
            role = "Them" if msg["role"] == "user" else "You"
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)
    
    def create_fallback_prompt(self, user_message: str, emotion: Emotion) -> List[Dict[str, str]]:
        """
        Create minimal prompt when retrieval fails.
        Forces personality-based response without factual grounding.
        """
        return [
            {"role": "system", "content": self.SYSTEM_PERSONA},
            {"role": "user", "content": f"Context: {self.EMOTION_GUIDANCE.get(emotion, 'Respond naturally and authentically.')}"},
            {"role": "user", "content": user_message}
        ]
    
    def get_fallback_response(self, emotion: str = "neutral") -> str:
        """
        Get a simple fallback response when pipeline fails.
        
        Args:
            emotion: Detected emotion (string format)
            
        Returns:
            A personality-appropriate fallback message
        """
        fallback_responses = {
            "romantic": "I'm here... just having a moment. Tell me more?",
            "flirty": "You've got my attention... what's on your mind?",
            "playful": "Caught me off guard there! Say that again?",
            "sad": "I'm listening. I'm here with you.",
            "serious": "I hear you. Give me a moment to gather my thoughts...",
            "curious": "That's an interesting question... let me think on that.",
            "supportive": "I'm right here. What do you need?",
            "neutral": "I'm here. What would you like to talk about?"
        }
        
        return fallback_responses.get(emotion, "I'm here. What's on your mind?")
