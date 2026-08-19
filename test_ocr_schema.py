# -*- coding: utf-8 -*-
"""Smoke tests for the position-aware OCR schema; run: python test_ocr_schema.py"""
from ocr_normalizer import normalize_processed_data
from chart_parser import build_chart_json

ITEMS=[
 {"text":"B.Thân","confidence":0.99,"bbox":[[.02,.02],[.18,.02],[.18,.08],[.02,.08]]},
 {"text":"TỬ TỨC","confidence":0.99,"bbox":[[.38,.02],[.62,.02],[.62,.08],[.38,.08]]},
 {"text":"93","confidence":0.99,"bbox":[[.88,.02],[.98,.02],[.98,.08],[.88,.08]]},
 {"text":"+Kim","confidence":0.99,"bbox":[[.02,.12],[.16,.12],[.16,.18],[.02,.18]]},
 {"text":"-LIÊM TRINH (V)","confidence":0.99,"bbox":[[.36,.14],[.72,.14],[.72,.21],[.36,.21]]},
 {"text":"Th.2","confidence":0.99,"bbox":[[.82,.14],[.98,.14],[.98,.21],[.82,.21]]},
 {"text":"Văn Tinh","confidence":0.99,"bbox":[[.03,.24],[.22,.24],[.22,.30],[.03,.30]]},
 {"text":"L.Văn Xương","confidence":0.99,"bbox":[[.03,.33],[.24,.33],[.24,.39],[.03,.39]]},
 {"text":"L.Thiên Mã","confidence":0.99,"bbox":[[.03,.42],[.25,.42],[.25,.48],[.03,.48]]},
 {"text":"Hóa Kỵ","confidence":0.99,"bbox":[[.70,.45],[.90,.45],[.90,.51],[.70,.51]]},
 {"text":"ĐV.TẬT","confidence":0.99,"bbox":[[.02,.90],[.22,.90],[.22,.96],[.02,.96]]},
 {"text":"Tuyệt","confidence":0.99,"bbox":[[.42,.86],[.58,.86],[.58,.91],[.42,.91]]},
 {"text":"Tuần","confidence":0.99,"bbox":[[.43,.93],[.58,.93],[.58,.99],[.43,.99]]},
 {"text":"LN.TÀI","confidence":0.99,"bbox":[[.78,.90],[.98,.90],[.98,.96],[.78,.96]]}
]

if __name__=="__main__":
    normalized=normalize_processed_data({"cungs":{"Tử Tức":ITEMS}})
    chart=build_chart_json(normalized)
    p=chart["12_cung"]["Tử Tức"]
    assert p["can"]=="Bính",p
    assert p["dia_chi"]=="Thân",p
    assert p["ngu_hanh"]=="Kim" and p["am_duong"]=="Dương",p
    assert p["dai_van"]["tuoi_bat_dau"]==93,p
    assert p["luu_nguyet"]["thang"]==2,p
    assert p["dai_van"]["cung"]=="Tật",p
    assert p["luu_nien"]["cung"]=="TÀI",p
    assert p["vong_truong_sinh"]=="Tuyệt",p
    assert p["tuan"] is True and p["triet"] is False,p
    assert p["chinh_tinh"][0]["ten"]=="Liêm Trinh",p
    assert p["chinh_tinh"][0]["trang_thai"]=="V",p
    assert "Văn Tinh" in p["phu_tinh"],p
    assert "Văn Xương" in p["luu_tinh"],p
    assert "Thiên Mã" in p["luu_tinh"],p
    assert "Hóa Kỵ" in p["tu_hoa"],p
    print("OCR schema smoke test: PASS")
