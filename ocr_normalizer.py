# -*- coding: utf-8 -*-
"""Convert OCR fragments into structured Tử Vi terms. Raw OCR is never sent to AI."""
from __future__ import annotations
import json, re, unicodedata
from pathlib import Path
BASE=Path(__file__).resolve().parent

def dictionary(): return json.loads((BASE/"tu_vi_dictionary.json").read_text(encoding="utf-8"))
def strip_accents(s): return "".join(c for c in unicodedata.normalize("NFD",s) if unicodedata.category(c)!="Mn")
def clean(s):
    s=re.sub(r"\[conf=[0-9.]+\]","",str(s)); s=re.sub(r"[|\[\]{}<>]"," ",s)
    s=re.sub(r"\b(?:ĐV|LN|LĐV|Th)\.?\s*[A-Za-zÀ-ỹ0-9]+(?:\s+[A-Za-zÀ-ỹ0-9]+)*$","",s,flags=re.I)
    s=re.sub(r"\s+"," ",s).strip(" +-~()'\"")
    return s

def norm_key(s): return strip_accents(clean(s)).lower().replace(" ","")
def build_indexes(d):
    groups={"chinh_tinh":set(d.get("major_stars",[])),"phu_tinh":set(d.get("supporting_stars",[])),"hoa_tinh":set(d.get("transformations",[])),"sat_tinh":set(d.get("malefics",[]))}
    aliases={norm_key(k):v for k,v in d.get("aliases",{}).items()}
    canonical={norm_key(x):x for g in groups.values() for x in g}
    return groups,aliases,canonical

def match_star(raw):
    d=dictionary(); groups,aliases,canonical=build_indexes(d); text=clean(raw); key=norm_key(text)
    if not key or key.isdigit() or len(key)<2: return None
    name=aliases.get(key) or canonical.get(key)
    if not name:
        # OCR often adds trạng thái (M/V/Đ/H), dấu +/- hoặc ký hiệu L.
        stripped=re.sub(r"^(?:l|ln|dv|ldv|[+-])?","",key)
        stripped=re.sub(r"(?:m|v|đ|d|h|ths?)$","",stripped)
        for k,n in {**aliases,**canonical}.items():
            if len(k)>=4 and (stripped==k or stripped in k or k in stripped): name=n; break
    if not name:return None
    typ=next((g for g,s in groups.items() if name in s),"phu_tinh")
    return {"name":name,"type":typ}

def normalize_processed_data(data):
    """Produce only recognized palace terms, stars and special markers."""
    d=dictionary(); branches=set(d.get("earthly_branches",[])); aliases=d.get("aliases",{})
    result={"schema_version":"3.0","source":"python_ocr","image_sent_to_llm":False,"cungs":{}}
    for cung,values in (data or {}).get("cungs",{}).items():
        stars=[]; seen=set(); branch=None; tuan=False; triet=False
        for value in values:
            raw=clean(value)
            key=norm_key(raw)
            if key in {norm_key(x) for x in branches}: branch=next(x for x in branches if norm_key(x)==key); continue
            if "tuần" in raw.lower() or key=="tuan": tuan=True; continue
            if "triệt" in raw.lower() or key=="triet": triet=True; continue
            star=match_star(raw)
            if star and star["name"] not in seen:
                seen.add(star["name"]); stars.append(star)
        result["cungs"][cung]={"dia_chi":branch,"tuan":tuan,"triet":triet,"stars":stars}
    return result
