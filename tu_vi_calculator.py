# -*- coding: utf-8 -*-
"""Conservative deterministic relation calculator.

This module only computes relations that are unambiguous from palace/branch
labels. It deliberately does not invent missing birth-data calculations.
"""
BRANCHES=["Tý","Sửu","Dần","Mão","Thìn","Tỵ","Ngọ","Mùi","Thân","Dậu","Tuất","Hợi"]

def relation(a,b):
    if a not in BRANCHES or b not in BRANCHES: return "unknown"
    d=(BRANCHES.index(b)-BRANCHES.index(a))%12
    if d in (4,8): return "tam_hop"
    if d==6: return "xung_chieu"
    if d in (5,7): return "giap_cung"
    if d in (1,11): return "nhi_hop"
    return "other"

def calculate_chart(chart):
    # Keep deterministic metadata only; birth-time-dependent placements remain OCR/input data.
    return {"calculator_version":"1.0","relations_note":"Relations require canonical địa chi labels.","cungs":chart.get("cungs",{})}
