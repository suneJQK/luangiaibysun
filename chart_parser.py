# -*- coding: utf-8 -*-
"""Build the minimal clean chart payload sent to the LLM."""
from __future__ import annotations


def build_chart_json(processed):
    """Keep only palace/branch/star information; raw OCR never leaves this layer."""
    cungs = {}
    for name, items in (processed or {}).get("cungs", {}).items():
        stars = []
        review = []
        branch = None
        for item in items:
            canonical = (item.get("canonical") or "").strip()
            if not canonical:
                continue
            if canonical in {"Tý","Sửu","Dần","Mão","Thìn","Tỵ","Ngọ","Mùi","Thân","Dậu","Tuất","Hợi"}:
                branch = canonical
                continue
            if canonical in {"Mệnh","Phụ Mẫu","Phúc Đức","Điền Trạch","Quan Lộc","Nô Bộc","Thiên Di","Tật Ách","Tài Bạch","Tử Tức","Phu Thê","Huynh Đệ"}:
                continue
            if item.get("status") == "low_confidence":
                review.append(canonical)
                continue
            if canonical not in stars:
                stars.append(canonical)
            if item.get("status") != "accepted" and canonical not in review:
                review.append(canonical)
        entry = {"sao": stars}
        if branch:
            entry["dia_chi"] = branch
        if review:
            entry["can_xac_nhan"] = review
        cungs[name] = entry
    return {
        "schema_version": "2.0",
        "source": "python_ocr",
        "image_sent_to_llm": False,
        "12_cung": cungs,
    }
