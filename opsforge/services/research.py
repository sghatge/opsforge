"""Bounded, application-managed retrieval for the OPSFORGE research agent.

NotebookLM is not queried here. Callers supply approved source records with
title, url, and text; retrieval returns excerpts and stable run-local IDs.
"""
from __future__ import annotations

import re


def retrieve(question: str, sources: list[dict], top_k: int = 5) -> dict:
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Research task requires a non-empty 'question'.")
    if not isinstance(sources, list) or not sources:
        raise ValueError("Research task requires a non-empty 'sources' list.")
    if len(sources) > 100:
        raise ValueError("At most 100 source records may be supplied per run.")
    if len(question) > 2000:
        raise ValueError("Research question must be 2,000 characters or fewer.")
    if not 1 <= int(top_k) <= 10:
        raise ValueError("'top_k' must be between 1 and 10.")

    query_terms = _terms(question)
    ranked = []
    for index, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            continue
        title = str(source.get("title", "")).strip()
        url = str(source.get("url", "")).strip()
        text = str(source.get("text", "")).strip()
        if not title or not text:
            continue
        text = text[:20000]
        terms = _terms(title + " " + text)
        overlap = sum(1 for term in query_terms if term in terms)
        score = overlap / max(1, len(query_terms))
        ranked.append((score, index, {
            "source_id": f"S{index}",
            "title": title,
            "url": url,
            "text": text[:6000],
            "relevance": round(score, 4),
        }))

    if not ranked:
        raise ValueError("No usable sources found; each source needs a title and text.")
    ranked.sort(key=lambda item: (-item[0], item[1]))
    selected = [item[2] for item in ranked[:int(top_k)]]
    return {
        "question": question.strip(),
        "retrieval_method": "lexical_overlap_v1",
        "sources_considered": len(ranked),
        "sources": selected,
        "notice": "Results are limited to source text supplied with this run; this is not a direct NotebookLM connection.",
    }


def _terms(value: str) -> set[str]:
    return {term for term in re.findall(r"[a-z0-9]{2,}", value.lower())}
