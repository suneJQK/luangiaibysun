# -*- coding: utf-8 -*-
"""Turn EasyOCR text into canonical Tử Vi terms while retaining only useful fields."""
from __future__ import annotations
import json, re, unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent
BRANCHES = {"Tý","Sửu","Dần","Mão","Thìn","Tỵ","Ngọ","Mùi","Thân","Dậu","Tuất","Hợi"}
PALACES = {"Mệnh","Phụ Mẫu","Phúc Đức","Điền Trạch","Quan Lộc","Nô Bộc","Thiên Di","Tật Ách","Tài Bạch","Tử Tức","Phu Thê","Huynh Đệ"}

def _load_dictionary():
    return json.loads((BASE / "tu_vi_dictionary.json").read_text(encoding="utf-8"))

def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")

def norm_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def normalize_term(raw: str):
    d = _load_dictionary(); raw = norm_space(str(raw))
    conf_match = re.search(r"\[conf=([0-9.]+)\]$", raw)
    confidence = float(conf_match.group(1)) if conf_match else 1.0
    term = re.sub(r"\s*\[conf=[0-9.]+\]$", "", raw).strip()
    aliases = d.get("aliases", {})
    canonical = aliases.get(term, term)
    candidates = d.get("major_stars", []) + d.get("common_stars", []) + list(BRANCHES) + list(PALACES)
    if canonical not in candidates:
        folded = strip_accents(term).lower()
        for c in candidates:
            if strip_accents(c).lower() == folded:
                canonical = c
                break
    status = "accepted" if confidence >= .75 else "review" if confidence >= .55 else "low_confidence"
    return {"canonical": canonical, "confidence": round(confidence, 3), "status": status}

def normalize_processed_data(data):
    """Return only canonical terms and confidence; discard raw OCR strings."""
    result = {"schema_version": "2.0", "source": "python_ocr", "image_sent_to_llm": False, "cungs": {}}
    for cung, values in (data or {}).get("cungs", {}).items():
        clean=[]
        seen=set()
        for value in values:
            item=normalize_term(value)
            if not item["canonical"] or item["canonical"] in seen:
                continue
            seen.add(item["canonical"]); clean.append(item)
        result["cungs"][cung]=clean
    return result
