"""
Braindump Processor — The intelligence behind the well.

Processes unprocessed drops: extracts keywords, groups into topics,
generates summaries. Uses Claude API when ANTHROPIC_API_KEY is set,
falls back to keyword-based grouping otherwise.
"""

import json
import logging
import os
import re
import sqlite3
from collections import Counter
from datetime import datetime

from . import database as db

log = logging.getLogger(__name__)

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Common English stopwords for keyword extraction
STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "not",
    "only", "own", "same", "so", "than", "too", "very", "just", "about",
    "and", "but", "or", "nor", "if", "while", "because", "until", "that",
    "which", "who", "whom", "this", "these", "those", "am", "it", "its",
    "i", "me", "my", "we", "our", "you", "your", "he", "him", "his",
    "she", "her", "they", "them", "their", "what", "get", "got", "like",
    "make", "made", "think", "thing", "things", "also", "want", "going",
}


def extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from text."""
    text = re.sub(r"https?://\S+", "", text)  # Remove URLs
    words = re.findall(r"[a-z]+", text.lower())
    keywords = [w for w in words if len(w) > 2 and w not in STOPWORDS]
    return keywords


def keyword_similarity(kw1: list[str], kw2: list[str]) -> float:
    """Jaccard similarity between two keyword lists."""
    if not kw1 or not kw2:
        return 0.0
    s1, s2 = set(kw1), set(kw2)
    intersection = s1 & s2
    union = s1 | s2
    return len(intersection) / len(union) if union else 0.0


def generate_topic_name(keywords: list[str], drops: list[dict]) -> str:
    """Generate a topic name from the most common keywords."""
    all_kw = []
    for d in drops:
        all_kw.extend(extract_keywords(d["content"]))
    counts = Counter(all_kw)
    top = [w for w, _ in counts.most_common(3)]
    return " + ".join(top) if top else "misc"


def generate_summary(drops: list[dict]) -> str:
    """Generate a simple summary from drops."""
    contents = [d["content"] for d in drops]
    if len(contents) == 1:
        return contents[0]
    # Combine first ~500 chars
    combined = []
    total = 0
    for c in contents:
        if total + len(c) > 500:
            remaining = 500 - total
            if remaining > 20:
                combined.append(c[:remaining] + "...")
            break
        combined.append(c)
        total += len(c)
    return " | ".join(combined)


def process_with_keywords():
    """Keyword-based categorization (no API key needed)."""
    conn = db.get_connection()

    # Get unprocessed drops
    unprocessed = conn.execute(
        "SELECT * FROM drops WHERE processed = 0 ORDER BY dropped_at"
    ).fetchall()
    unprocessed = [dict(r) for r in unprocessed]

    if not unprocessed:
        log.info("No unprocessed drops.")
        conn.close()
        return 0

    log.info("Processing %d drops with keyword method", len(unprocessed))

    # Get existing topics and their keywords
    existing_topics = conn.execute("SELECT * FROM topics").fetchall()
    existing_topics = [dict(t) for t in existing_topics]

    topic_keywords = {}
    for topic in existing_topics:
        # Get drops for this topic to build keyword profile
        topic_drops = conn.execute("""
            SELECT d.content FROM drops d
            JOIN drop_topics dt ON d.id = dt.drop_id
            WHERE dt.topic_id = ?
        """, (topic["id"],)).fetchall()
        kws = []
        for td in topic_drops:
            kws.extend(extract_keywords(td["content"]))
        topic_keywords[topic["id"]] = kws

    processed_count = 0
    for drop in unprocessed:
        drop_kws = extract_keywords(drop["content"])

        best_topic_id = None
        best_similarity = 0.0

        # Try to match with existing topics
        for topic_id, tkws in topic_keywords.items():
            sim = keyword_similarity(drop_kws, tkws)
            if sim > best_similarity:
                best_similarity = sim
                best_topic_id = topic_id

        if best_similarity >= 0.15 and best_topic_id is not None:
            # Assign to existing topic
            conn.execute(
                "INSERT OR IGNORE INTO drop_topics (drop_id, topic_id, relevance) VALUES (?, ?, ?)",
                (drop["id"], best_topic_id, round(best_similarity, 2)),
            )
            # Update topic keywords cache
            topic_keywords[best_topic_id].extend(drop_kws)
            # Regenerate summary
            topic_drops = conn.execute("""
                SELECT d.* FROM drops d
                JOIN drop_topics dt ON d.id = dt.drop_id
                WHERE dt.topic_id = ?
                ORDER BY d.dropped_at DESC
            """, (best_topic_id,)).fetchall()
            topic_drops = [dict(td) for td in topic_drops]
            summary = generate_summary(topic_drops)
            conn.execute(
                "UPDATE topics SET summary = ?, updated_at = datetime('now') WHERE id = ?",
                (summary, best_topic_id),
            )
        else:
            # Create new topic
            topic_name = generate_topic_name(drop_kws, [drop])
            cursor = conn.execute(
                "INSERT INTO topics (name, summary) VALUES (?, ?)",
                (topic_name, drop["content"]),
            )
            new_topic_id = cursor.lastrowid
            conn.execute(
                "INSERT INTO drop_topics (drop_id, topic_id, relevance) VALUES (?, ?, 1.0)",
                (drop["id"], new_topic_id),
            )
            topic_keywords[new_topic_id] = drop_kws

        # Mark as processed
        conn.execute("UPDATE drops SET processed = 1 WHERE id = ?", (drop["id"],))
        processed_count += 1

    conn.commit()
    conn.close()
    log.info("Processed %d drops (keyword mode)", processed_count)
    return processed_count


def process_with_llm():
    """Claude API categorization (requires ANTHROPIC_API_KEY)."""
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    conn = db.get_connection()

    # Get unprocessed drops
    unprocessed = conn.execute(
        "SELECT * FROM drops WHERE processed = 0 ORDER BY dropped_at"
    ).fetchall()
    unprocessed = [dict(r) for r in unprocessed]

    if not unprocessed:
        log.info("No unprocessed drops.")
        conn.close()
        return 0

    log.info("Processing %d drops with Claude API", len(unprocessed))

    # Get existing topics for context
    existing_topics = conn.execute("SELECT id, name, summary FROM topics").fetchall()
    existing_topics = [dict(t) for t in existing_topics]

    topic_list = "\n".join(
        f"- ID {t['id']}: {t['name']}" for t in existing_topics
    ) or "No existing topics yet."

    drops_text = "\n".join(
        f"- Drop #{d['id']} ({d['content_type']}): {d['content']}"
        for d in unprocessed
    )

    prompt = f"""You are organizing a user's brain dump. They drop thoughts, links, and ideas into a well.
Your job: categorize each drop into topics and generate summaries.

EXISTING TOPICS:
{topic_list}

NEW DROPS TO PROCESS:
{drops_text}

For each drop, respond with JSON (no other text):
{{
  "assignments": [
    {{
      "drop_id": <int>,
      "topic_id": <int or null if new topic>,
      "new_topic_name": <string or null if existing>,
      "relevance": <float 0-1>
    }}
  ],
  "topic_summaries": [
    {{
      "topic_id": <int or "new:topic_name">,
      "summary": "<2-3 sentence summary of everything in this topic>"
    }}
  ]
}}

Rules:
- Group related drops together (same project, same theme, same domain)
- Create new topics only when a drop doesn't fit existing ones
- Topic names should be short (2-4 words), descriptive, lowercase
- Summaries should synthesize, not just list
- A drop can belong to multiple topics if relevant"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        result_text = response.content[0].text.strip()

        # Parse JSON from response (handle markdown code blocks)
        if result_text.startswith("```"):
            result_text = re.sub(r"```(?:json)?\n?", "", result_text).strip()

        result = json.loads(result_text)
    except Exception as e:
        log.error("LLM processing failed: %s — falling back to keywords", e)
        conn.close()
        return process_with_keywords()

    # Apply assignments
    processed_count = 0
    new_topic_map = {}  # "new:name" -> actual ID

    for assignment in result.get("assignments", []):
        drop_id = assignment["drop_id"]
        topic_id = assignment.get("topic_id")
        new_name = assignment.get("new_topic_name")
        relevance = assignment.get("relevance", 0.8)

        if topic_id is None and new_name:
            # Create new topic if not already created in this batch
            map_key = new_name.lower().strip()
            if map_key in new_topic_map:
                topic_id = new_topic_map[map_key]
            else:
                cursor = conn.execute(
                    "INSERT INTO topics (name, summary) VALUES (?, '')",
                    (new_name,),
                )
                topic_id = cursor.lastrowid
                new_topic_map[map_key] = topic_id

        if topic_id:
            conn.execute(
                "INSERT OR IGNORE INTO drop_topics (drop_id, topic_id, relevance) VALUES (?, ?, ?)",
                (drop_id, topic_id, relevance),
            )

        conn.execute("UPDATE drops SET processed = 1 WHERE id = ?", (drop_id,))
        processed_count += 1

    # Apply summaries
    for summary_item in result.get("topic_summaries", []):
        tid = summary_item.get("topic_id")
        summary = summary_item.get("summary", "")

        if isinstance(tid, str) and tid.startswith("new:"):
            name = tid[4:].lower().strip()
            tid = new_topic_map.get(name)

        if tid and summary:
            conn.execute(
                "UPDATE topics SET summary = ?, updated_at = datetime('now') WHERE id = ?",
                (summary, tid),
            )

    conn.commit()
    conn.close()
    log.info("Processed %d drops (LLM mode)", processed_count)
    return processed_count


def process_drops() -> int:
    """Process unprocessed drops. Uses LLM if key available, else keywords."""
    if ANTHROPIC_KEY:
        return process_with_llm()
    return process_with_keywords()
