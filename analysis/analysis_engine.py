from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from .models import Conversation, Message, ConversationAnalysis
from django.conf import settings
from django.db import transaction
import datetime
import math
import re

analyzer = SentimentIntensityAnalyzer()

# configurable weights (can also be moved to settings.py)
WEIGHTS = {
    "clarity": 0.18,
    "relevance": 0.18,
    "empathy": 0.12,
    "completeness": 0.15,
    "accuracy": 0.15,
    "sentiment": 0.10,
    "fallback": 0.06,
    "response_time": 0.06,
}

def _normalize_0_10(x, minv=0.0, maxv=1.0):
    """Normalize x in [minv, maxv] to 0..10 safely."""
    if maxv == minv:
        return 0.0
    val = (x - minv) / (maxv - minv)
    return round(max(0.0, min(1.0, val)) * 10, 2)

def _label_sentiment(compound_score):
    if compound_score > 0.2:
        return "positive"
    if compound_score < -0.2:
        return "negative"
    return "neutral"

def analyze_conversation(conversation: Conversation) -> ConversationAnalysis:
    """
    Improved analysis:
    - per-message sentiment, aggregated
    - response time computation using Message.created_at if available
    - normalized 0-10 scores and weighted overall_score
    - more robust fallback/empathy detection
    """
    messages_qs = conversation.messages.order_by('id')  # assume insertion order or created_at
    messages = list(messages_qs)

    # If there are zero messages, create a minimal analysis
    if not messages:
        analysis, _ = ConversationAnalysis.objects.update_or_create(
            conversation=conversation,
            defaults=dict(
                clarity_score=0.0,
                relevance_score=0.0,
                empathy_score=0.0,
                resolution=False,
                escalation_needed=False,
                fallback_count=0,
                avg_response_time=0.0,
                overall_score=0.0,
                sentiment="neutral",
            ),
        )
        return analysis

    user_msgs = [m for m in messages if m.sender.lower() == "user"]
    ai_msgs = [m for m in messages if m.sender.lower() == "ai"]

    # ---------- Sentiment (per user message) ----------
    user_compounds = []
    for m in user_msgs:
        try:
            s = analyzer.polarity_scores(m.text or "")["compound"]
        except Exception:
            s = 0.0
        user_compounds.append(s)
    avg_user_sentiment = sum(user_compounds) / len(user_compounds) if user_compounds else 0.0
    sentiment_label = _label_sentiment(avg_user_sentiment)

    # ---------- Clarity ----------
    # heuristic: shorter AI messages with normal punctuation -> higher clarity
    def _sentence_score(txt):
        txt = (txt or "").strip()
        if not txt:
            return 0.0
        words = txt.split()
        avg_word_len = sum(len(w) for w in words) / len(words) if words else 0
        # penalize long messages (>40 words)
        length_penalty = max(0.0, (len(words) - 20) / 40)  # 0..~0.5
        # reward presence of punctuation (.,?!) indicating sentence boundaries
        punct_score = 1.0 if re.search(r'[.!?]', txt) else 0.6
        base = max(0.0, 1.0 - length_penalty) * punct_score
        return base

    ai_sentence_scores = [_sentence_score(m.text) for m in ai_msgs] if ai_msgs else [0.5]
    clarity_raw = sum(ai_sentence_scores) / len(ai_sentence_scores)
    clarity_score = _normalize_0_10(clarity_raw, 0.0, 1.0)

    # ---------- Relevance ----------
    # simple token-overlap across conversation: proportion of AI messages that share tokens with any user message
    def _token_set(s):
        return set(re.findall(r"\w+", (s or "").lower()))
    user_token_union = set()
    for m in user_msgs:
        user_token_union |= _token_set(m.text)
    if ai_msgs and user_token_union:
        relevance_hits = 0
        for m in ai_msgs:
            if len(_token_set(m.text) & user_token_union) > 0:
                relevance_hits += 1
        relevance_raw = relevance_hits / len(ai_msgs)
    else:
        relevance_raw = 0.5  # unknown
    relevance_score = _normalize_0_10(relevance_raw, 0.0, 1.0)

    # ---------- Empathy ----------
    empathy_keywords = [
        "sorry", "apologize", "i understand", "i'm sorry", "that must be",
        "i can imagine", "thank you for", "i'm glad", "glad i could", "i'm here to help"
    ]
    empathy_count = 0
    for m in ai_msgs:
        low = (m.text or "").lower()
        if any(kw in low for kw in empathy_keywords):
            empathy_count += 1
    # normalized by number of ai messages
    empathy_raw = (empathy_count / len(ai_msgs)) if ai_msgs else 0.0
    empathy_score = _normalize_0_10(empathy_raw, 0.0, 1.0)

    # ---------- Fallback detection ----------
    fallback_phrases = [
        "don't know", "do not know", "can't help", "cannot help", "not sure",
        "i'm not sure", "unable to", "i can't", "i cannot", "transfer to agent",
        "escalate", "let me connect you", "human agent"
    ]
    fallback_count = 0
    fallback_examples = []
    for m in ai_msgs:
        low = (m.text or "").lower()
        for ph in fallback_phrases:
            if ph in low:
                fallback_count += 1
                fallback_examples.append(m.text)
                break

    # ---------- Completeness & Accuracy (heuristics) ----------
    # For now, a heuristic: if AI provides actionable resolution words and user says thanks -> higher
    resolution_indicators = ["resolved", "done", "shipped", "refunded", "fixed", "arrive", "delivered"]
    resolution = any(any(k in (m.text or "").lower() for k in resolution_indicators) for m in ai_msgs) \
                 or any("thank" in (m.text or "").lower() for m in user_msgs)

    # completeness: proportion of ai messages that include next-step or closure tokens
    completeness_tokens = ["please", "you can", "next", "follow", "order", "tracking", "refund", "confirmation", "reference"]
    comp_hits = 0
    for m in ai_msgs:
        if any(tok in (m.text or "").lower() for tok in completeness_tokens):
            comp_hits += 1
    completeness_raw = comp_hits / len(ai_msgs) if ai_msgs else 0.0
    completeness_score = _normalize_0_10(completeness_raw, 0.0, 1.0)

    # accuracy: placeholder heuristic — if AI references factual tokens like order ids or dates (very rough)
    accuracy_raw = 0.5
    for m in ai_msgs:
        text = (m.text or "").lower()
        # if it contains a numeric token like an order id, assume higher accuracy
        if re.search(r'\b\d{3,}\b', text):
            accuracy_raw = min(1.0, accuracy_raw + 0.25)
    accuracy_score = _normalize_0_10(accuracy_raw, 0.0, 1.0)

    # ---------- Response time (use timestamps if present) ----------
    # We compute average AI response time in seconds: for each ai message, find previous user message timestamp
    response_deltas = []
    for ai_m in ai_msgs:
        # find index of ai_m in messages and search backwards for user message
        try:
            idx = messages.index(ai_m)
            # search previous user message
            prev_user = None
            for j in range(idx - 1, -1, -1):
                if messages[j].sender.lower() == "user":
                    prev_user = messages[j]
                    break
            if prev_user and getattr(prev_user, "created_at", None) and getattr(ai_m, "created_at", None):
                delta = (ai_m.created_at - prev_user.created_at).total_seconds()
                # ignore negative or wildly large deltas
                if 0 <= delta < 60 * 60 * 24:  # less than a day
                    response_deltas.append(delta)
        except ValueError:
            continue

    if response_deltas:
        avg_response_time_seconds = sum(response_deltas) / len(response_deltas)
    else:
        # fallback to an empirical default
        avg_response_time_seconds = 12.0

    # Normalize response time: faster responses -> higher score
    # Map 0s -> 10, 60s -> 0 (clip)
    rt_raw = max(0.0, min(60.0, 60.0 - avg_response_time_seconds)) / 60.0
    response_time_score = _normalize_0_10(rt_raw, 0.0, 1.0)

    # ---------- Overall weighted score ----------
    component_scores = {
        "clarity": clarity_score,
        "relevance": relevance_score,
        "empathy": empathy_score,
        "completeness": completeness_score,
        "accuracy": accuracy_score,
        "sentiment": _normalize_0_10((avg_user_sentiment + 1) / 2, 0.0, 1.0),  # map -1..1 to 0..1 then to 0..10
        "fallback": _normalize_0_10(max(0.0, 1.0 - min(1.0, fallback_count / max(1, len(ai_msgs)))), 0.0, 1.0),
        "response_time": response_time_score,
    }

    overall = 0.0
    for k, w in WEIGHTS.items():
        overall += component_scores.get(k, 0.0) * w
    # overall is currently on 0..10 scale already because components 0..10 and weights sum to 1
    overall_score = round(overall, 2)

    # Escalation heuristic
    escalation_needed = (avg_user_sentiment < -0.4) or (fallback_count > 1 and not resolution) or (overall_score < 3.5)

    # Save results in DB (atomic)
    with transaction.atomic():
        analysis, _ = ConversationAnalysis.objects.update_or_create(
            conversation=conversation,
            defaults=dict(
                clarity_score=clarity_score,
                relevance_score=relevance_score,
                empathy_score=empathy_score,
                resolution=resolution,
                escalation_needed=escalation_needed,
                fallback_count=fallback_count,
                avg_response_time=round(avg_response_time_seconds, 2),
                overall_score=overall_score,
                sentiment=sentiment_label,
            )
        )

    return analysis
