import os
import re
from typing import Optional

# Try to import OpenAI and Gemini SDKs if available
try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

try:
    import google.generativeai as genai  # type: ignore
except Exception:  # pragma: no cover
    genai = None  # type: ignore


SYSTEM_PROMPT = (
    "You are an assistant that writes clear, student-friendly, and fairly detailed summaries of academic notes. "
    "Write 6-10 strong bullet points that capture: key concepts, definitions, formulas (inline), step-by-step methods, and practical examples or use-cases where helpful. "
    "Use crisp language, avoid fluff, and prefer informative content over generic advice. Aim for roughly 150-250 words."
)


def _summarize_with_openai(text: str) -> Optional[str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return None
    try:
        client = OpenAI(api_key=api_key)
        # Use the responses API (preferred newer SDK) if available
        try:
            resp = client.responses.create(
                model=os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4o-mini"),
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Summarize the following notes as detailed bullet points.\n\n{text}"},
                ],
                temperature=0.3,
                max_output_tokens=500,
            )
            content = resp.output_text  # type: ignore[attr-defined]
            return content.strip() if content else None
        except Exception:
            # Fallback to chat.completions if older SDK style
            chat = client.chat.completions.create(
                model=os.getenv("OPENAI_SUMMARY_MODEL", "gpt-3.5-turbo"),
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Summarize the following notes as detailed bullet points.\n\n{text}"},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            content = chat.choices[0].message.content
            return content.strip() if content else None
    except Exception as e:
        print(f"OpenAI summarization failed: {e}")
        return None


def _summarize_with_gemini(text: str) -> Optional[str]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or genai is None:
        return None
    try:
        genai.configure(api_key=api_key)
        model_name = os.getenv("GEMINI_SUMMARY_MODEL", "gemini-1.5-flash")
        model = genai.GenerativeModel(model_name)
        prompt = f"{SYSTEM_PROMPT}\n\nSummarize the following notes as detailed bullet points.\n\n{text}"
        resp = model.generate_content(prompt)
        content = getattr(resp, "text", None)
        return content.strip() if content else None
    except Exception as e:
        print(f"Gemini summarization failed: {e}")
        return None


def _simple_extract(text: str, limit: int = 240) -> str:
    """Legacy one-line fallback (kept for completeness)."""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    m = re.search(r"(.{120,240}?[.!?])\s", text)
    if m:
        return m.group(1).strip()
    return text[:limit].rsplit(" ", 1)[0].strip() + "…"


def _simple_bulleted_summary(text: str, min_bullets: int = 5, max_bullets: int = 9) -> str:
    """Produce a more detailed, multi-bullet local summary without external APIs.
    Heuristic approach: split into sentences/clauses and format as bullets.
    """
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return ""
    # Split by sentence endings; if too few, split on semicolons/commas
    parts = re.split(r"(?<=[.!?])\s+", clean)
    if len(parts) < min_bullets:
        parts = re.split(r"[;•\-]\s+|,\s+", clean)
    # Deduplicate and keep informative chunks
    seen = set()
    bullets: list[str] = []
    for p in parts:
        p = p.strip(" -•:\t\n\r")
        if len(p) < 5:
            continue
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        bullets.append(p)
        if len(bullets) >= max_bullets:
            break
    # If still too short, backfill with the longest remaining fragments
    if len(bullets) < min_bullets:
        leftovers = [x for x in parts if x.strip() and x.strip().lower() not in seen]
        leftovers.sort(key=len, reverse=True)
        for x in leftovers:
            bullets.append(x.strip())
            if len(bullets) >= min_bullets:
                break
    # Format as dash bullets
    if not bullets:
        return _simple_extract(clean, limit=240)
    return "\n".join(f"- {b}" for b in bullets)


def _interpret_with_openai(query: str) -> Optional[str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return None
    try:
        client = OpenAI(api_key=api_key)
        # Use the responses API if available
        try:
            resp = client.responses.create(
                model=os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4o-mini"),
                input=[
                    {"role": "system", "content": "You are an assistant that interprets natural language search queries for academic notes. Extract key terms, topics, and concepts from the query. Return a comma-separated list of relevant keywords or phrases that can be used for searching notes. Focus on academic subjects, exams, and study materials. Keep it concise."},
                    {"role": "user", "content": f"Interpret this search query: '{query}'"},
                ],
                temperature=0.2,
                max_output_tokens=100,
            )
            content = resp.output_text  # type: ignore[attr-defined]
            return content.strip() if content else None
        except Exception:
            # Fallback to chat.completions
            chat = client.chat.completions.create(
                model=os.getenv("OPENAI_SUMMARY_MODEL", "gpt-3.5-turbo"),
                messages=[
                    {"role": "system", "content": "You are an assistant that interprets natural language search queries for academic notes. Extract key terms, topics, and concepts from the query. Return a comma-separated list of relevant keywords or phrases that can be used for searching notes. Focus on academic subjects, exams, and study materials. Keep it concise."},
                    {"role": "user", "content": f"Interpret this search query: '{query}'"},
                ],
                temperature=0.2,
                max_tokens=100,
            )
            content = chat.choices[0].message.content
            return content.strip() if content else None
    except Exception as e:
        print(f"OpenAI interpretation failed: {e}")
        return None


def _interpret_with_gemini(query: str) -> Optional[str]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or genai is None:
        return None
    try:
        genai.configure(api_key=api_key)
        model_name = os.getenv("GEMINI_SUMMARY_MODEL", "gemini-1.5-flash")
        model = genai.GenerativeModel(model_name)
        prompt = f"You are an assistant that interprets natural language search queries for academic notes. Extract key terms, topics, and concepts from the query. Return a comma-separated list of relevant keywords or phrases that can be used for searching notes. Focus on academic subjects, exams, and study materials. Keep it concise.\n\nInterpret this search query: '{query}'"
        resp = model.generate_content(prompt)
        content = getattr(resp, "text", None)
        return content.strip() if content else None
    except Exception as e:
        print(f"Gemini interpretation failed: {e}")
        return None


def interpret_query(query: str) -> str:
    """Interpret a natural language query and return keywords for searching notes. Prefers OpenAI, falls back to Gemini, then to simple keyword extraction."""
    query = (query or "").strip()
    if not query:
        return ""

    # Try OpenAI first
    keywords = _interpret_with_openai(query)
    if keywords:
        return keywords

    # Then Gemini
    keywords = _interpret_with_gemini(query)
    if keywords:
        return keywords

    # Fallback: simple keyword extraction
    return _simple_keyword_extract(query)


def _simple_keyword_extract(query: str) -> str:
    """Simple fallback: extract words from query, filter common stop words."""
    import re
    words = re.findall(r'\b\w+\b', query.lower())
    stop_words = {'the', 'a', 'an', 'and', 'or', 'is', 'are', 'to', 'in', 'of', 'for', 'on', 'with', 'by', 'as', 'at', 'from', 'this', 'that', 'it', 'show', 'notes', 'on', 'for', 'final', 'exam'}
    keywords = [word for word in words if word not in stop_words and len(word) > 2]
    return ', '.join(keywords)


def summarize_text(text: str) -> str:
    """Return a fairly detailed, bulleted summary.
    Prefers OpenAI, falls back to Gemini, then to a local multi-bullet heuristic.
    """
    text = (text or "").strip()
    if not text:
        return ""

    # Clamp extremely long inputs (~8k chars) to keep API requests fast and cheap
    if len(text) > 8000:
        text = text[:8000]

    # Try OpenAI first
    summary = _summarize_with_openai(text)
    if summary:
        return summary

    # Then Gemini
    summary = _summarize_with_gemini(text)
    if summary:
        return summary

    # Fallback to local bulleted summary (more detailed than one-liners)
    return _simple_bulleted_summary(text)
