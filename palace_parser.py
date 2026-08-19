# -*- coding: utf-8 -*-
"""Position-aware parser for one Tử Vi palace."""
from __future__ import annotations
import re,unicodedata
from typing import Any,Dict,Iterable

CAN_MAP={"G":"Giáp","A":"Ất","B":"Bính","Đ":"Đinh","D":"Đinh","M":"Mậu","K":"Kỷ","C":"Canh","T":"Tân","N":"Nhâm","Q":"Quý","GI":"Giáp","AT":"Ất","BINH":"Bính","DINH":"Đinh","MAU":"Mậu","KY":"Kỷ","CANH":"Canh","TAN":"Tân","NHAM":"Nhâm","QUI":"Quý","QUY":"Quý"}
BRANCHES=["Tý","Sửu","Dần","Mão","Thìn","Tỵ","Ngọ","Mùi","Thân","Dậu","Tuất","Hợi"]
ELEMENTS={"kim":"Kim","moc":"Mộc","thuy":"Thủy","hoa":"Hỏa","tho":"Thổ"}
LIFE_STAGES=["Trường Sinh","Mộc Dục","Quan Đới","Lâm Quan","Đế Vượng","Suy","Bệnh","Tử","Mộ","Tuyệt","Thai","Dưỡng"]
PALACES=["Mệnh","Phụ Mẫu","Phúc Đức","Điền Trạch","Quan Lộc","Nô Bộc","Thiên Di","Tật Ách","Tài Bạch","Tử Tức","Phu Thê","Huynh Đệ"]

def norm(s:str)->str:
    s=unicodedata.normalize("NFD",str(s));s="".join(c for c in s if unicodedata.category(c)!="Mn")
    return re.sub(r"[^a-z0-9]+","",s.lower())

_CAN_KEYS={norm(k):v for k,v in CAN_MAP.items()};_BRANCH_KEYS={norm(x):x for x in BRANCHES}

def bbox_center(item:Dict[str,Any]):
    b=item.get("bbox") or []
    if len(b)<4:return .5,.5
    try:
        xs=[float(p[0]) for p in b];ys=[float(p[1]) for p in b]
        return (min(xs)+max(xs))/2,(min(ys)+max(ys))/2
    except Exception:return .5,.5

def parse_can_token(text):return _CAN_KEYS.get(norm(text))
def parse_branch_token(text):return _BRANCH_KEYS.get(norm(text))

def can_chi(text):
    ns=norm(text)
    for branch in sorted(BRANCHES,key=len,reverse=True):
        nb=norm(branch);pos=ns.find(nb)
        if pos<0:continue
        prefix=ns[:pos]
        can=_CAN_KEYS.get(prefix)
        if can is None:
            for k,v in sorted(_CAN_KEYS.items(),key=lambda x:len(x[0]),reverse=True):
                if prefix.endswith(k):can=v;break
        if can:return can,branch
    return None,None

def parse_element(text):
    s=str(text);n=norm(s);element=next((v for k,v in ELEMENTS.items() if k in n),None)
    if not element:return None,None
    return element,("Dương" if s.lstrip().startswith("+") else "Âm" if s.lstrip().startswith("-") else None)

def parse_period(text):
    s=str(text).strip();n=norm(s)
    m=re.search(r"(?:Th|Thang)\.?\s*(\d{1,2})\b",s,re.I)
    if m:return {"kind":"luu_nguyet","thang":int(m.group(1))}
    # In the chart layout T1..T12 is the Tiểu vận marker printed at the
    # lower-right of every palace. It is an index, not a star and not age.
    mt=re.fullmatch(r"T\s*(\d{1,2})",s,re.I)
    if mt:return {"kind":"tieu_van","so_thu":int(mt.group(1))}
    if re.match(r"(?:luu\s*)?nhat",s,re.I):
        m2=re.search(r"(\d{1,2})",s);return {"kind":"luu_nhat","ngay":int(m2.group(1)) if m2 else None}
    if n.startswith("dv"):return {"kind":"dai_van","cung":re.sub(r"^dv[.]?","",s,flags=re.I).strip(" .")}
    if n.startswith("ln"):return {"kind":"luu_nien","cung":re.sub(r"^ln[.]?","",s,flags=re.I).strip(" .")}
    if n.startswith("tv") or n.startswith("tieuhan"):return {"kind":"tieu_van","cung":re.sub(r"^(?:tv|tieu\s*han)[.]?","",s,flags=re.I).strip(" .")}
    if re.fullmatch(r"\d{1,3}",s):return {"kind":"age","value":int(s)}
    return None

def _palace_name(text):
    n=norm(text)
    for p in sorted(PALACES,key=len,reverse=True):
        if n.startswith(norm(p)):return p
    return None

def classify_position(item):
    text=str(item.get("text","")).strip();x,y=bbox_center(item);low=norm(text)
    if _palace_name(text):return "palace_name"
    if "tuan" in low:return "tuan"
    if "triet" in low:return "triet"
    if any(norm(x)==low for x in LIFE_STAGES):return "life_stage"
    if y<.30 and x<.45 and can_chi(text)[1]:return "can_chi"
    if y<.30 and x<.45 and parse_can_token(text):return "can"
    if y<.30 and x<.45 and parse_branch_token(text):return "dia_chi"
    if y<.40 and x<.45 and parse_element(text)[0]:return "element"
    if y<.32 and x>.55 and re.fullmatch(r"\d{1,3}",text):return "dai_van_age"
    if y<.40 and x>.55 and parse_period(text):return "period"
    if y>.70 and x<.45 and low.startswith("dv"):return "dai_van_cung"
    if y>.70 and x>.55 and low.startswith("ln"):return "luu_nien_cung"
    # T1..T12 is the Tiểu vận index at the bottom-right of a palace.
    if y>.70 and x>.55 and re.fullmatch(r"t\s*\d{1,2}",text,re.I):return "tieu_van_marker"
    if y>.70 and .25<=x<=.75 and (low.startswith("tv") or "tieuhan" in low):return "tieu_van_cung"
    if re.fullmatch(r"th\d{1,2}",low):return "luu_nguyet"
    return "star"

def parse_palace_items(items:Iterable[Dict[str,Any]],match_star,fallback_dia_chi=None):
    meta={"cung":None,"than_cu":False,"can":None,"dia_chi":None,"can_chi":None,"ngu_hanh":None,"am_duong":None,"vong_truong_sinh":None,"tuan":False,"triet":False,"dai_van":{},"tieu_van":{},"luu_nien":{},"luu_nguyet":{},"luu_nhat":{}}
    stars=[]
    for item in items or []:
        text=str(item.get("text","")).strip()
        if not text:continue
        kind=classify_position(item);low=norm(text)
        if kind=="palace_name":
            meta["cung"]=_palace_name(text) or meta["cung"]
            if "than" in low:meta["than_cu"]=True
            continue
        if kind=="can_chi":
            can,branch=can_chi(text);meta["can"]=can or meta["can"];meta["dia_chi"]=branch or meta["dia_chi"];continue
        if kind=="can":meta["can"]=parse_can_token(text) or meta["can"];continue
        if kind=="dia_chi":meta["dia_chi"]=parse_branch_token(text) or meta["dia_chi"];continue
        if kind=="element":
            e,ay=parse_element(text);meta["ngu_hanh"]=e;meta["am_duong"]=ay;continue
        if kind=="tuan":meta["tuan"]=True;continue
        if kind=="triet":meta["triet"]=True;continue
        if kind=="life_stage":meta["vong_truong_sinh"]=next((x for x in LIFE_STAGES if norm(x)==norm(text)),text);continue
        if kind in {"dai_van_age","dai_van_cung","tieu_van_marker","tieu_van_cung","luu_nien_cung","period","luu_nguyet"}:
            p=parse_period(text)
            if kind=="dai_van_age" and p:meta["dai_van"]["tuoi_bat_dau"]=p["value"]
            elif kind=="dai_van_cung":meta["dai_van"]["cung"]=re.sub(r"^ĐV\.?","",text,flags=re.I).strip()
            elif kind=="tieu_van_marker" and p:meta["tieu_van"]["so_thu"]=p["so_thu"]
            elif kind=="tieu_van_cung":meta["tieu_van"]["cung"]=re.sub(r"^(?:TV|Tiểu hạn)\.?","",text,flags=re.I).strip()
            elif kind=="luu_nien_cung":meta["luu_nien"]["cung"]=re.sub(r"^LN\.?","",text,flags=re.I).strip()
            elif p and p.get("kind")=="luu_nguyet":meta["luu_nguyet"]["thang"]=p["thang"]
            elif p and p.get("kind")=="luu_nhat":meta["luu_nhat"]["ngay"]=p.get("ngay")
            continue
        found=match_star(text)
        if found:found["source_text"]=text;stars.append(found)
    if meta["dia_chi"] is None and fallback_dia_chi:meta["dia_chi"]=parse_branch_token(fallback_dia_chi)
    if meta["can"] and meta["dia_chi"]:meta["can_chi"]=f"{meta['can']} {meta['dia_chi']}"
    seen=set();meta["stars"]=[]
    for star in stars:
        key=(star.get("name"),star.get("type"),bool(star.get("luu")))
        if key not in seen:seen.add(key);meta["stars"].append(star)
    return meta
