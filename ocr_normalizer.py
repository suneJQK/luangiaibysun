# -*- coding: utf-8 -*-
"""Noise-tolerant OCR normalization for Tử Vi.

OCR is evidence only. This layer converts noisy text into canonical stars,
classifies them, and keeps uncertain fragments outside the AI payload.
"""
from __future__ import annotations
import json,re,unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional
from palace_parser import parse_palace_items,norm

BASE=Path(__file__).resolve().parent
EXTRA_ALIASES={
    "thientho":"Thiên Thọ","thien tho":"Thiên Thọ","thientho":"Thiên Thọ",
    "thienkhoc":"Thiên Khốc","thien khoc":"Thiên Khốc","thienkhoc":"Thiên Khốc",
    "thienhu":"Thiên Hư","thien hu":"Thiên Hư",
    "daihao":"Đại Hao","dai hao":"Đại Hao","dai fao":"Đại Hao",
    "tieuhao":"Tiểu Hao","tieu hao":"Tiểu Hao",
    "benhphu":"Bệnh Phù","benh phu":"Bệnh Phù","benhphù":"Bệnh Phù",
    "lucsy":"Lực Sỹ","luc sy":"Lực Sỹ","lu csy":"Lực Sỹ",
    "vantinh":"Văn Tinh","van tinh":"Văn Tinh","vantinh":"Văn Tinh",
    "vanxuong":"Văn Xương","van xuong":"Văn Xương",
    "vankhuc":"Văn Khúc","van khuc":"Văn Khúc",
    "thienma":"Thiên Mã","thien ma":"Thiên Mã",
    "tangmon":"Tang Môn","tang mon":"Tang Môn","bachho":"Bạch Hổ","bach ho":"Bạch Hổ",
    "hoaloc":"Hóa Lộc","hoa loc":"Hóa Lộc","hoaquyen":"Hóa Quyền","hoa quyen":"Hóa Quyền",
    "hoakhoa":"Hóa Khoa","hoa khoa":"Hóa Khoa","hoaky":"Hóa Kỵ","hoa ky":"Hóa Kỵ",
    "thiendong":"Thiên Đồng","thien dong":"Thiên Đồng","thienphu":"Thiên Phủ","thien phu":"Thiên Phủ",
    "thienco":"Thiên Cơ","thien co":"Thiên Cơ","thaiduong":"Thái Dương","thai duong":"Thái Dương",
    "thaiam":"Thái Âm","thai am":"Thái Âm","vukhuc":"Vũ Khúc","vu khuc":"Vũ Khúc",
    "thamlang":"Tham Lang","tham lang":"Tham Lang","cumen":"Cự Môn","cu men":"Cự Môn",
    "thientuong":"Thiên Tướng","thien tuong":"Thiên Tướng","thienluong":"Thiên Lương","thien luong":"Thiên Lương",
    "thatsat":"Thất Sát","that sat":"Thất Sát","phaquan":"Phá Quân","pha quan":"Phá Quân",
    "liemtrinh":"Liêm Trinh","liem trinh":"Liêm Trinh","l iem trinh":"Liêm Trinh",
    "t u vi":"Tử Vi","tuvi":"Tử Vi","tu vi":"Tử Vi",
    "thienkhoi":"Thiên Khôi","thien khoi":"Thiên Khôi","thienviet":"Thiên Việt","thien viet":"Thiên Việt",
    "thientai":"Thiên Tài","thien tai":"Thiên Tài","trucphu":"Trực Phù","truc phu":"Trực Phù",
    "diakhong":"Địa Không","dia khong":"Địa Không","diakiep":"Địa Kiếp","dia kiep":"Địa Kiếp"
}

def dictionary():return json.loads((BASE/"tu_vi_dictionary.json").read_text(encoding="utf-8"))
def clean(s):
    s=re.sub(r"\[conf=[0-9.]+\]","",str(s));s=re.sub(r"[|\[\]{}<>]"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def _index():
    d=dictionary();groups={"chinh_tinh":set(d.get("major_stars",[])),"phu_tinh":set(d.get("supporting_stars",[])),"hoa_tinh":set(d.get("transformations",[])),"sat_tinh":set(d.get("malefics",[]))}
    names={norm(x):x for group in groups.values() for x in group}
    names.update({norm(k):v for k,v in d.get("aliases",{}).items()});names.update({norm(k):v for k,v in EXTRA_ALIASES.items()})
    return groups,names

def _metadata(text):
    s=clean(text)
    # L./LN./ĐV. are metadata prefixes, not part of star names.
    luu=bool(re.search(r"(?:^|[\s\[\(])L\.?\s*(?=[A-Za-zÀ-ỹĐđ])",s,re.I))
    am_duong="Dương" if re.match(r"^\s*\+",s) else "Âm" if re.match(r"^\s*-",s) else None
    status=None;m=re.search(r"\((M|V|Đ|D|H)\)",s,re.I)
    if m:status={"D":"Đ"}.get(m.group(1).upper(),m.group(1).upper())
    s=re.sub(r"(?:^|\s)L\.?\s*"," ",s,flags=re.I)
    s=re.sub(r"\b(?:LN|ĐV|DV)\.?\s*"," ",s,flags=re.I)
    s=re.sub(r"^[+\-~]+\s*","",s)
    s=re.sub(r"\((?:M|V|Đ|D|H)\)"," ",s,flags=re.I)
    s=re.sub(r"\bTh\.?\s*\d{1,2}\b.*$","",s,flags=re.I)
    return re.sub(r"\s+"," ",s).strip(" .,:;\"'"),luu,status,am_duong

def _type(name,groups):return next((g for g,s in groups.items() if name in s),"phu_tinh")
def _fuzzy(key,names,threshold=.82):
    if key in names:return names[key]
    best=None;score=0
    for k,name in names.items():
        if len(k)<5:continue
        s=SequenceMatcher(None,key,k).ratio()
        if s>score:score,best=s,name
    return best if score>=threshold else None

def match_star(raw):
    text,luu,status,am_duong=_metadata(raw);groups,names=_index();key=norm(text)
    if not key:return None
    name=names.get(key)
    if not name:
        for k,n in sorted(names.items(),key=lambda x:len(x[0]),reverse=True):
            if len(k)>=5 and k in key:name=n;break
    if not name:name=_fuzzy(key,names,.78)
    if not name:return None
    return {"name":name,"type":_type(name,groups),"luu":luu,"trang_thai":status,"am_duong":am_duong}

def extract_stars(raw):
    """Split compound OCR lines and recover fuzzy star names.
    Examples: 'Văn Xương (Đ) Linh Tinh (H)' -> two stars;
    '-Thuỷ +THIÊN ĐỒNG (Đ) Ths' -> Thiên Đồng.
    """
    original=clean(raw);core,default_luu,_,_= _metadata(original);tokens=re.findall(r"[A-Za-zÀ-ỹĐđ]+",core)
    groups,names=_index();found=[];seen=set()
    # Exact windows before fuzzy windows avoids false positives.
    for fuzzy in (False,True):
        for size in (3,2,4,1):
            for i in range(max(0,len(tokens)-size+1)):
                chunk=" ".join(tokens[i:i+size]);key=norm(chunk)
                if len(key)<5:continue
                name=names.get(key) if not fuzzy else _fuzzy(key,names,.86)
                if not name or name in seen:continue
                # Reject a fuzzy one-word fragment; it creates too many false stars.
                if fuzzy and size==1:continue
                seen.add(name);prefix=" ".join(tokens[:i])
                luu=default_luu or bool(re.search(r"(?:^|\s)L\.?\s*$",prefix,re.I))
                # Find the nearest state marker in the original text.
                status=None;am=None
                m=re.search(r"\((M|V|Đ|D|H)\)",original,re.I)
                if m:status={"D":"Đ"}.get(m.group(1).upper(),m.group(1).upper())
                if re.search(r"(?:^|\s)\+\s*$",prefix):am="Dương"
                elif re.search(r"(?:^|\s)-\s*$",prefix):am="Âm"
                found.append({"name":name,"type":_type(name,groups),"luu":luu,"trang_thai":status,"am_duong":am})
    if not found:
        one=match_star(raw)
        if one:found=[one]
    return found

def _items(values):
    out=[]
    for v in values or []:
        if isinstance(v,dict):
            x=dict(v);x["text"]=clean(x.get("text",x.get("raw","")));out.append(x)
        else:out.append({"text":clean(v),"confidence":1.0,"bbox":[]})
    return out

def normalize_processed_data(data):
    out={"schema_version":"3.1","source":"python_ocr","image_sent_to_llm":False,"cungs":{},"review":[]}
    for cung,values in (data or {}).get("cungs",{}).items():
        items=_items(values);expanded=[]
        for item in items:
            stars=extract_stars(item.get("text",""))
            if len(stars)>1:
                for star in stars:expanded.append({**item,"text":star["name"],"_star_hint":star})
            else:expanded.append(item)
        meta=parse_palace_items(expanded,match_star,fallback_dia_chi=cung)
        for item in expanded:
            hint=item.get("_star_hint")
            if hint:
                for star in meta.get("stars",[]):
                    if star.get("name")==hint.get("name"):star.update({k:v for k,v in hint.items() if v is not None})
        for item in items:
            try:conf=float(item.get("confidence",1.0))
            except Exception:conf=1.0
            if conf<.52:out["review"].append({"cung":cung,"text":item.get("text",""),"confidence":conf,"bbox":item.get("bbox",[])})
        out["cungs"][cung]=meta
    return out
