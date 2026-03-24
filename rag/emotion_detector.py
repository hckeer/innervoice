"""
rag/emotion_detector.py

Lightweight emotion detection for conversation context.
Maps user input to emotional categories for better retrieval.
"""

import re
from typing import Dict, List
from enum import Enum


class Emotion(Enum):
    """Emotional categories for conversations."""
    ROMANTIC = "romantic"
    FLIRTY = "flirty"
    PLAYFUL = "playful"
    SAD = "sad"
    SERIOUS = "serious"
    CURIOUS = "curious"
    SUPPORTIVE = "supportive"
    NEUTRAL = "neutral"


class EmotionDetector:
    """Rule-based emotion detection for conversational context."""
    
    # Keyword patterns for each emotion
    PATTERNS: Dict[Emotion, List[str]] = {
        Emotion.ROMANTIC: [
            r'\b(love|adore|cherish|darling|sweetheart|beautiful|gorgeous)\b',
            r'\b(miss you|thinking of you|can\'t stop thinking|dream about)\b',
            r'\b(heart|soul|forever|always|together)\b',
        ],
        Emotion.FLIRTY: [
            r'\b(cute|hot|sexy|attractive|like you|into you)\b',
            r'\b(smile|eyes|laugh|voice)\b.*\b(love|like|beautiful)\b',
            r'\b(date|dinner|coffee|drinks|hang out)\b.*\b(sometime|tonight|weekend)\b',
            r'[😘😍🥰😏😉]',
        ],
        Emotion.PLAYFUL: [
            r'\b(haha|lol|funny|silly|tease|joking|kidding)\b',
            r'\b(game|play|fun|adventure|crazy|wild)\b',
            r'[😂🤣😄😆]',
        ],
        Emotion.SAD: [
            r'\b(sad|depressed|down|lonely|hurt|pain|crying|tears)\b',
            r'\b(miss|lost|gone|left|alone|empty)\b',
            r'\b(sorry|regret|mistake|wish)\b',
            r'[😢😭😔😞]',
        ],
        Emotion.SERIOUS: [
            r'\b(important|serious|need to talk|we should|have to)\b',
            r'\b(think about|consider|decision|future|relationship)\b',
            r'\b(truth|honest|real talk|no joke)\b',
        ],
        Emotion.CURIOUS: [
            r'\b(what|why|how|when|where|who|wonder|curious)\b',
            r'\b(tell me|explain|understand|know more)\b',
            r'\?',
        ],
        Emotion.SUPPORTIVE: [
            r'\b(here for you|support|help|listen|care|worry)\b',
            r'\b(be okay|get through|proud of you|believe in)\b',
            r'\b(hugs?|comfort|shoulder)\b',
        ],
    }
    
    def detect(self, text: str) -> Emotion:
        """
        Detect primary emotion from text.
        
        Args:
            text: User input text
            
        Returns:
            Primary emotion category
        """
        text_lower = text.lower()
        scores: Dict[Emotion, int] = {emotion: 0 for emotion in Emotion}
        
        # Score each emotion based on pattern matches
        for emotion, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    scores[emotion] += 1
        
        # Get emotion with highest score
        max_score = max(scores.values())
        if max_score == 0:
            return Emotion.NEUTRAL
        
        # Return highest scoring emotion (romantic/flirty prioritized)
        priority = [Emotion.ROMANTIC, Emotion.FLIRTY, Emotion.SAD, Emotion.SERIOUS]
        for emotion in priority:
            if scores[emotion] == max_score:
                return emotion
        
        # Return any max scoring emotion
        return max(scores, key=scores.get)
    
    def get_boost_factor(self, query_emotion: Emotion, doc_emotion: Emotion) -> float:
        """
        Calculate retrieval boost factor based on emotion matching.
        
        Args:
            query_emotion: Detected emotion from user query
            doc_emotion: Emotion tag of retrieved document
            
        Returns:
            Boost factor (1.0 = no boost, 1.5 = 50% boost)
        """
        if query_emotion == doc_emotion:
            return 1.5
        
        # Compatible emotions (romantic ↔ flirty)
        compatible_pairs = [
            (Emotion.ROMANTIC, Emotion.FLIRTY),
            (Emotion.SAD, Emotion.SUPPORTIVE),
            (Emotion.PLAYFUL, Emotion.FLIRTY),
        ]
        
        for e1, e2 in compatible_pairs:
            if (query_emotion == e1 and doc_emotion == e2) or \
               (query_emotion == e2 and doc_emotion == e1):
                return 1.2
        
        return 1.0
