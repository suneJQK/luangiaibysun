# -*- coding: utf-8 -*-
"""OCR -> structured Tử Vi data.
The module deliberately removes OCR noise before anything is sent to the LLM.
"""
from __future__ import annotations
import json, re, unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional
from palace_parser import parse_palace_items, norm

BASE=Path(__file__).resolve().parent

def dictionary():
    return json.loads((BASE/"tu_vi_dictionary.json").read_text(encoding="utf-8"))

def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD",str(s)) if unicodedata.category(c)!="Mn")

def clean(s):
    s=re.sub(r"\[conf=[0-9.]+\]","",str(s))
    s=re.sub(r"[|\[\]{}<>]"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def _star_index():
    d=dictionary(); groups={
        "chinh_tinh":set(d.get("major_stars",[])),
        "phu_tinh":set(d.get("supporting_stars",[])),
        "hoa_tinh":set(d.get("transformations",[])),
        "sat_tinh":set(d.get("malefics",[])),
    }
    canonical={norm(x):x for group in groups.values() for x in group}
    aliases={norm(k):v for k,v in d.get("aliases",{}).items()}
    all_names={**canonical,**aliases}
    return groups, all_names

def _strip_metadata(text: str):
    """Return (core, luu, status, am_duong). OCR often adds + - ~ L [ ] and M/V/Đ/H."""
    s=clean(text)
    luu=bool(re.search(r"(?:^|\s|\.)L\.?\s*(?=[A-Za-zÀ-ỹĐđ])",s,re.I))
    s=re.sub(r"^\s*L\.?\s*", "", s, flags=re.I)
    s=re.sub(r"^\s*(?:LN|ĐV|DV)\.?\s*", "", s, flags=re.I)
    am_duong="Dương" if re.match(r"^\s*\+",s) else "Âm" if re.match(r"^\s*-",s) else None
    s=re.sub(r"^[+\-~]+\s*", "", s)
    status=None
    m=re.search(r"\((M|V|Đ|D|H)\)\s*$",s,re.I)
    if m:
        raw=m.group(1).upper(); status={"D":"Đ"}.get(raw,raw); s=s[:m.start()].strip()
    s=re.sub(r"\bTh\.?\s*\d{1,2}\b.*$","",s,flags=re.I).strip()
    s=re.sub(r"\s+"," ",s).strip(" .,:;\"'")
    return s,luu,status,am_duong

def _best_name(text: str) -> Optional[str]:
    groups,names=_star_index(); key=norm(text)
    if not key: return None
    if key in names: return names[key]
    # Prefer longest canonical/alias contained in the OCR fragment.
    candidates=sorted(names.items(),key=lambda kv:len(kv[0]),reverse=True)
    for k,name in candidates:
        if len(k)>=4 and (k in key or key in k): return name
    # OCR character substitutions: fuzzy match only against reasonably long names.
    best=None; score=0.0
    for k,name in candidates:
        if len(k)<4: continue
        s=SequenceMatcher(None,key,k).ratio()
        if s>score: score,best=s,name
    return best if score>=0.78 else None

def match_star(raw):
    text,luu,status,am_duong=_strip_metadata(raw)
    groups,_=_star_index()
    name=_best_name(text)
    if not name:
        # A single OCR line can contain two or more stars; caller can use extract_stars.
        return None
    typ=next((g for g,s in groups.items() if name in s),"phu_tinh")
    return {"name":name,"type":typ,"luu":luu,"trang_thai":status,"am_duong":am_duong}

def extract_stars(raw: str) -> List[dict]:
    """Extract all known stars from a noisy line, not just an exact whole-line match."""
    groups,names=_star_index(); result=[]; seen=set()
    original=clean(raw)
    # Try every known name/alias, longest first, so compound lines are split safely.
    for k,name in sorted(names.items(),key=lambda kv:len(kv[0]),reverse=True):
        if len(k)<4: continue
        if k not in norm(original): continue
        # Find metadata immediately around the occurrence using a forgiving regex.
        luu=bool(re.search(r"(?:^|[\s+\-~\[]|\.)L\.?\s*$", original[:max(0, original.lower().find(name.lower()))], re.I))
        status=None; am_duong=None
        typ=next((g for g,s in groups.items() if name in s),"phu_tinh")
        key=(name,typ,luu)
        if key not in seen:
            seen.add(key); result.append({"name":name,"type":typ,"luu":luu,"trang_thai":status,"am_duong":am_duong})
    if not result:
        one=match_star(raw)
        if one: result=[one]
    return result

def _items(values):
    out=[]
    for value in values or []:
        if isinstance(value,dict):
            x=dict(value); x["text"]=clean(x.get("text",x.get("raw",""))); out.append(x)
        else:
            out.append({"text":clean(value),"confidence":1.0,"bbox":[]})
    return out

def normalize_processed_data(data):
    """Return one structured object per palace; raw OCR is retained only in local review data."""
    normalized={"schema_version":"3.0","source":"python_ocr","image_sent_to_llm":False,"cungs":{},"review":[]}
    for cung,values in (data or {}).get("cungs",{}).items():
        items=_items(values)
        # Add fuzzy star fragments as synthetic items only when a line contains known names.
        expanded=[]
        for item in items:
            stars=extract_stars(item.get("text",""))
            if len(stars)>1:
                # parse_palace_items will classify the original line as star; replace it with clean fragments.
                for s in stars:
                    expanded.append({**item,"text":s["name"],"_star_hint":s})
            else: expanded.append(item)
        meta=parse_palace_items(expanded,match_star)
        # Re-apply metadata from compound-line extraction and deduplicate.
        for item in expanded:
            hint=item.get("_star_hint")
            if hint:
                for s in meta["stars"]:
                    if s["name"]==hint["name"]: s.update({k:v for k,v in hint.items() if v is not None})
        # Keep low-confidence review notes outside the AI payload.
        for item in items:
            if float(item.get("confidence",1.0))<0.52:
                normalized["review"].append({"cung":cung,"text":item.get("text",""),"confidence":item.get("confidence")})
        normalized["cungs"][cung]=meta
    return normalized
