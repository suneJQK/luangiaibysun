# -*- coding: utf-8 -*-
"""Convert normalized palace objects into the only payload allowed to reach the LLM."""
from __future__ import annotations

def _compact_period(value):
    if not value:return None
    return {k:v for k,v in value.items() if v not in (None, "", [], {})}

def build_chart_json(processed):
    out={"schema_version":"3.0","source":"python_ocr","image_sent_to_llm":False,"12_cung":{}}
    for palace_key, data in (processed or {}).get("cungs",{}).items():
        name=data.get("cung") or palace_key
        entry={
            "dia_chi":data.get("dia_chi"),
            "can":data.get("can"),
            "ngu_hanh":data.get("ngu_hanh"),
            "am_duong":data.get("am_duong"),
            "vong_truong_sinh":data.get("vong_truong_sinh"),
            "tuan":bool(data.get("tuan")),
            "triet":bool(data.get("triet")),
            "chinh_tinh":[],
            "phu_tinh":[],
            "luu_tinh":[],
            "tu_hoa":[],
            "sat_tinh":[],
            "dai_van":_compact_period(data.get("dai_van")),
            "tieu_van":_compact_period(data.get("tieu_van")),
            "luu_nien":_compact_period(data.get("luu_nien")),
            "luu_nguyet":_compact_period(data.get("luu_nguyet")),
            "luu_nhat":_compact_period(data.get("luu_nhat"))
        }
        for star in data.get("stars",[]):
            name_star=star.get("name")
            if not name_star:continue
            obj={"ten":name_star}
            if star.get("trang_thai"):obj["trang_thai"]=star["trang_thai"]
            if star.get("am_duong"):obj["am_duong"]=star["am_duong"]
            if star.get("luu"):obj["luu"]=True
            typ=star.get("type")
            if typ=="chinh_tinh":entry["chinh_tinh"].append(obj)
            elif typ=="phu_tinh":
                (entry["luu_tinh"] if star.get("luu") else entry["phu_tinh"]).append(name_star)
            elif typ=="hoa_tinh":entry["tu_hoa"].append(name_star)
            elif typ=="sat_tinh":entry["sat_tinh"].append(name_star)
        for key in ["dia_chi","can","ngu_hanh","am_duong","vong_truong_sinh","dai_van","tieu_van","luu_nien","luu_nguyet","luu_nhat"]:
            if entry.get(key) in (None,{},""):entry.pop(key,None)
        # Keep explicit false for Tuần/Triệt because absence means "not detected", not "false".
        out["12_cung"][name]=entry
    return out
