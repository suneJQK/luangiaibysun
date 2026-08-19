# -*- coding: utf-8 -*-
"""Normalize EasyOCR output into canonical Tử Vi terms."""
from __future__ import annotations
import json, re, unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent

def _load_dictionary():
    return json.loads((BASE / "tu_vi_dictionary.json").read_text(encoding="utf-8"))

def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")

def norm_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def normalize_term(raw: str):
    d = _load_dictionary(); raw = norm_space(raw)
    conf_match = re.search(r"\[conf=([0-9.]+)\]$", raw)
    confidence = float(conf_match.group(1)) if conf_match else 1.0
    term = re.sub(r"\s*\[conf=[0-9.]+\]$", "", raw).strip()
    aliases = d.get("aliases", {})
    canonical = aliases.get(term, term)
    if canonical not in sum([d.get("major_stars", []), d.get("common_stars", []), d.get("earthly_branches", []), d.get("palaces", [])], []):
        folded = strip_accents(term).lower()
        candidates = d.get("major_stars", []) + d.get("common_stars", []) + d.get("earthly_branches", []) + d.get("palaces", [])
        for c in candidates:
            if strip_accents(c).lower() == folded:
                canonical = c; break
    status = "accepted" if confidence >= .75 else "review" if confidence >= .55 else "low_confidence"
    return {"raw": term, "canonical": canonical, "confidence": round(confidence, 3), "status": status}

def normalize_processed_data(data):
    result = dict(data or {})
    result["schema_version"] = "1.0"
    result["header_text"] = [normalize_term(x) for x in result.get("header_text", [])]
    normalized = {}
    for cung, values in result.get("cungs", {}).items():
        normalized[cung] = [normalize_term(x) for x in values]
    result["cungs"] = normalized
    result["normalization"] = {"dictionary": "tu_vi_dictionary.json", "image_sent_to_llm": False}
    return result
