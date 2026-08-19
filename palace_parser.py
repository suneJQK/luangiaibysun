# -*- coding: utf-8 -*-
"""Position-aware parser for one Tử Vi palace.
OCR is treated as evidence; only structured fields leave this layer for the LLM.
"""
from __future__ import annotations
import re
from typing import Any, Dict, Iterable, List, Optional

CAN_MAP = {
    "G": "Giáp", "A": "Ất", "B": "Bính", "Đ": "Đinh", "D": "Đinh",
    "M": "Mậu", "K": "Kỷ", "C": "Canh", "T": "Tân", "N": "Nhâm", "Q": "Quý",
    "GI": "Giáp", "AT": "Ất", "BINH": "Bính", "DINH": "Đinh", "MAU": "Mậu",
    "KY": "Kỷ", "CANH": "Canh", "TAN": "Tân", "NHAM": "Nhâm", "QUI": "Quý", "QUY": "Quý",
}
BRANCHES = ["Tý","Sửu","Dần","Mão","Thìn","Tỵ","Ngọ","Mùi","Thân","Dậu","Tuất","Hợi"]
ELEMENTS = {"kim":"Kim","moc":"Mộc","thuy":"Thủy","hoa":"Hỏa","tho":"Thổ"}
LIFE_STAGES = ["Trường Sinh","Mộc Dục","Quan Đới","Lâm Quan","Đế Vượng","Suy","Bệnh","Tử","Mộ","Tuyệt","Thai","Dưỡng"]
PALACES = ["Mệnh","Phụ Mẫu","Phúc Đức","Điền Trạch","Quan Lộc","Nô Bộc","Thiên Di","Tật Ách","Tài Bạch","Tử Tức","Phu Thê","Huynh Đệ"]


def norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def bbox_center(item: Dict[str, Any]):
    b = item.get("bbox") or []
    if len(b) < 4: return 0.5, 0.5
    try:
        xs=[float(p[0]) for p in b]; ys=[float(p[1]) for p in b]
        return (min(xs)+max(xs))/2, (min(ys)+max(ys))/2
    except Exception:
        return 0.5, 0.5


def can_chi(text: str):
    s=str(text).strip().replace(" ", "")
    for branch in sorted(BRANCHES, key=len, reverse=True):
        if norm(branch) in norm(s):
            prefix=re.sub(r"[^A-Za-zÀ-ỹĐđ]", "", s[:max(0, s.lower().find(branch.lower()))])
            p=norm(prefix).upper().strip(".")
            can=CAN_MAP.get(p) or next((v for k,v in CAN_MAP.items() if p.startswith(k)), None)
            return can, branch
    return None, None


def parse_element(text: str):
    s=str(text)
    n=norm(s)
    element=next((v for k,v in ELEMENTS.items() if k in n), None)
    if not element: return None, None
    if s.lstrip().startswith("+"): yin_yang="Dương"
    elif s.lstrip().startswith("-"): yin_yang="Âm"
    else: yin_yang=None
    return element, yin_yang


def parse_period(text: str):
    s=str(text).strip()
    n=norm(s)
    age=re.search(r"\b(\d{1,3})\b", s)
    if age: return {"kind":"age", "value":int(age.group(1))}
    m=re.search(r"(?:Th|T|Thang)\.?\s*(\d{1,2})\b", s, re.I)
    if m: return {"kind":"luu_nguyet", "thang":int(m.group(1))}
    if n.startswith("dv"):
        return {"kind":"dai_van", "cung":re.sub(r"^dv[.]?", "", s, flags=re.I).strip(" .")}
    if n.startswith("ln"):
        return {"kind":"luu_nien", "cung":re.sub(r"^ln[.]?", "", s, flags=re.I).strip(" .")}
    if n.startswith("tv") or n.startswith("tieu han") or n.startswith("tieuhan"):
        return {"kind":"tieu_van", "cung":re.sub(r"^(?:tv|tieu\s*han)[.]?", "", s, flags=re.I).strip(" .")}
    if re.match(r"(?:luu\s*)?nhat", s, re.I):
        m2=re.search(r"(\d{1,2})", s)
        return {"kind":"luu_nhat", "ngay":int(m2.group(1)) if m2 else None}
    return None


def classify_position(item: Dict[str, Any], width: float=1.0, height: float=1.0):
    text=str(item.get("text", "")).strip(); x,y=bbox_center(item)
    xn=x/width if width else x; yn=y/height if height else y
    low=norm(text)
    if low in {norm(x) for x in PALACES}: return "palace_name"
    if "tuan" in low: return "tuan"
    if "triet" in low: return "triet"
    if any(norm(x)==low for x in LIFE_STAGES): return "life_stage"
    if yn < .20 and xn < .34 and can_chi(text)[1]: return "can_chi"
    if yn < .28 and xn < .34 and parse_element(text)[0]: return "element"
    if yn < .22 and xn > .68 and re.fullmatch(r"\d{1,3}", text.strip()): return "dai_van_age"
    if yn < .28 and xn > .68 and parse_period(text): return "period"
    if yn > .78 and xn < .36 and low.startswith("dv"): return "dai_van_cung"
    if yn > .78 and xn > .64 and low.startswith("ln"): return "luu_nien_cung"
    if yn > .78 and .35 <= xn <= .65 and (low.startswith("tv") or "tieu" in low): return "tieu_van_cung"
    if "th." in low or re.fullmatch(r"th\d{1,2}", low): return "luu_nguyet"
    return "star"


def parse_palace_items(items: Iterable[Dict[str, Any]], match_star):
    meta={"cung":None,"can":None,"dia_chi":None,"ngu_hanh":None,"am_duong":None,"vong_truong_sinh":None,"tuan":False,"triet":False,"dai_van":{},"tieu_van":{},"luu_nien":{},"luu_nguyet":{},"luu_nhat":{}}
    stars=[]
    for item in items or []:
        text=str(item.get("text", "")).strip()
        if not text: continue
        kind=classify_position(item)
        if kind=="palace_name": meta["cung"]=next((p for p in PALACES if norm(p)==norm(text)), meta["cung"]); continue
        if kind=="can_chi":
            can,branch=can_chi(text); meta["can"]=can or meta["can"]; meta["dia_chi"]=branch or meta["dia_chi"]; continue
        if kind=="element":
            e,ay=parse_element(text); meta["ngu_hanh"]=e; meta["am_duong"]=ay; continue
        if kind=="tuan": meta["tuan"]=True; continue
        if kind=="triet": meta["triet"]=True; continue
        if kind=="life_stage": meta["vong_truong_sinh"]=next((x for x in LIFE_STAGES if norm(x)==norm(text)), text); continue
        if kind in {"dai_van_age","dai_van_cung","tieu_van_cung","luu_nien_cung","period","luu_nguyet"}:
            p=parse_period(text)
            if kind=="dai_van_age" or (p and p.get("kind")=="age"): meta["dai_van"]["tuoi_bat_dau"]=int(p["value"])
            elif kind=="dai_van_cung": meta["dai_van"]["cung"]=re.sub(r"^ĐV\.?", "", text, flags=re.I).strip()
            elif kind=="tieu_van_cung": meta["tieu_van"]["cung"]=re.sub(r"^(?:TV|Tiểu hạn)\.?", "", text, flags=re.I).strip()
            elif kind=="luu_nien_cung": meta["luu_nien"]["cung"]=re.sub(r"^LN\.?", "", text, flags=re.I).strip()
            elif p and p.get("kind")=="luu_nguyet": meta["luu_nguyet"]["thang"]=p["thang"]
            elif p and p.get("kind")=="luu_nhat": meta["luu_nhat"]["ngay"]=p.get("ngay")
            continue
        found=match_star(text)
        if found:
            found["source_text"]=text
            stars.append(found)
    # Deduplicate by canonical name + lưu flag + type.
    seen=set(); unique=[]
    for s in stars:
        key=(s.get("name"),s.get("type"),bool(s.get("luu")))
        if key not in seen: seen.add(key); unique.append(s)
    meta["stars"]=unique
    return meta
