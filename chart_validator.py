# -*- coding: utf-8 -*-
"""Deterministic validation of OCR chart data before any LLM call."""
from __future__ import annotations

def validate_chart(data):
    errors=[]; warnings=[]
    cungs=data.get("cungs", {}) if isinstance(data, dict) else {}
    if len(cungs) != 12: warnings.append(f"Nhận được {len(cungs)}/12 cung OCR.")
    seen=[]
    for cung, items in cungs.items():
        if cung in seen: errors.append(f"Trùng cung: {cung}")
        seen.append(cung)
        for item in items:
            if item.get("status") == "low_confidence": warnings.append(f"{cung}: OCR thấp '{item.get('raw')}' ({item.get('confidence')})")
    return {"valid": not errors, "errors": errors, "warnings": warnings, "needs_review": bool(warnings)}
