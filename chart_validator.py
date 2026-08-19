# -*- coding: utf-8 -*-
"""Deterministic validation before an LLM call."""
from __future__ import annotations
PALACES={"Mệnh","Phụ Mẫu","Phúc Đức","Điền Trạch","Quan Lộc","Nô Bộc","Thiên Di","Tật Ách","Tài Bạch","Tử Tức","Phu Thê","Huynh Đệ"}
BRANCHES={"Tý","Sửu","Dần","Mão","Thìn","Tỵ","Ngọ","Mùi","Thân","Dậu","Tuất","Hợi"}

def validate_chart(data):
    errors=[];warnings=[]
    cungs=data.get("cungs",{}) if isinstance(data,dict) else {}
    if len(cungs)!=12:warnings.append(f"Nhận được {len(cungs)}/12 ô cung OCR.")
    seen=set()
    for key,p in cungs.items():
        name=p.get("cung") or key
        if name in seen:errors.append(f"Trùng cung: {name}")
        seen.add(name)
        if name not in PALACES:warnings.append(f"{key}: chưa xác định chắc tên cung.")
        if p.get("dia_chi") and p["dia_chi"] not in BRANCHES:warnings.append(f"{name}: địa chi không chuẩn.")
        if p.get("tuan") and p.get("triet"):warnings.append(f"{name}: đồng thời có Tuần và Triệt, cần kiểm tra ảnh.")
        if p.get("dai_van",{}).get("tuoi_bat_dau") is not None:
            age=p["dai_van"]["tuoi_bat_dau"]
            if not 1<=int(age)<=120:warnings.append(f"{name}: tuổi bắt đầu Đại vận {age} bất thường.")
        if p.get("luu_nguyet",{}).get("thang") is not None and not 1<=int(p["luu_nguyet"]["thang"])<=12:
            warnings.append(f"{name}: tháng Lưu nguyệt bất thường.")
    if isinstance(data,dict):
        for r in data.get("review",[]):warnings.append(f"{r.get('cung')}: OCR cần kiểm tra '{r.get('text')}'.")
    return {"valid":not errors,"errors":errors,"warnings":warnings,"needs_review":bool(warnings)}
