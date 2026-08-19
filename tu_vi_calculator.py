# -*- coding: utf-8 -*-
"""Deterministic relations from the already-normalized chart only."""
BRANCHES=["Tý","Sửu","Dần","Mão","Thìn","Tỵ","Ngọ","Mùi","Thân","Dậu","Tuất","Hợi"]

def relation(a,b):
    if a not in BRANCHES or b not in BRANCHES:return "unknown"
    d=(BRANCHES.index(b)-BRANCHES.index(a))%12
    if d in (4,8):return "tam_hop"
    if d==6:return "xung_chieu"
    if d in (5,7):return "giap_cung"
    if d in (1,11):return "nhi_hop"
    return "other"

def calculate_chart(chart):
    cungs=chart.get("12_cung",{}) if isinstance(chart,dict) else {}
    positions={k:v.get("dia_chi") for k,v in cungs.items() if v.get("dia_chi")}
    relations=[]
    names=list(positions)
    for i,a in enumerate(names):
        for b in names[i+1:]:
            r=relation(positions[a],positions[b])
            if r in {"tam_hop","xung_chieu","nhi_hop"}:relations.append({"a":a,"b":b,"quan_he":r})
    return {"calculator_version":"2.0","relations":relations}
