# -*- coding: utf-8 -*-
import unittest
from ocr_normalizer import extract_stars
from palace_parser import parse_palace_items
from chart_parser import build_chart_json

class OCRRegression(unittest.TestCase):
    def test_star_noise(self):
        names={"Thiên Đồng":"chinh_tinh","Liêm Trinh":"chinh_tinh","Văn Xương":"phu_tinh","Thiên Mã":"phu_tinh","Hóa Kỵ":"hoa_tinh"}
        def match(text):
            for n,t in names.items():
                if n.lower() in text.lower(): return {"name":n,"type":t,"luu":text.startswith("L."),"trang_thai":None,"am_duong":None}
            return None
        stars=extract_stars("Văn Xương (Đ) Linh Tinh (H)")
        self.assertTrue(any(x["name"]=="Văn Xương" for x in stars))

    def test_palace_metadata(self):
        items=[
            {"text":"Tử Tức","bbox":[[.65,.03],[.95,.08]]},
            {"text":"B.Thân","bbox":[[.03,.03],[.20,.08]]},
            {"text":"+Kim","bbox":[[.03,.12],[.16,.17]]},
            {"text":"-LIÊM TRINH (V)","bbox":[[.20,.12],[.55,.18]]},
            {"text":"93","bbox":[[.86,.03],[.96,.08]]},
            {"text":"Th.2","bbox":[[.78,.12],[.96,.18]]},
            {"text":"ĐV.TẬT","bbox":[[.03,.90],[.20,.96]]},
            {"text":"LN.TÀI","bbox":[[.78,.90],[.96,.96]]},
            {"text":"Tuyệt","bbox":[[.45,.90],[.60,.96]]},
            {"text":"Tuần","bbox":[[.45,.95],[.60,.99]]}
        ]
        def match(text):
            if "LIÊM TRINH" in text:return {"name":"Liêm Trinh","type":"chinh_tinh","luu":False,"trang_thai":"V","am_duong":"Âm"}
            return None
        d=parse_palace_items(items,match)
        self.assertEqual(d["can"],"Bính");self.assertEqual(d["dia_chi"],"Thân");self.assertEqual(d["can_chi"],"Bính Thân")
        self.assertEqual(d["ngu_hanh"],"Kim");self.assertEqual(d["am_duong"],"Dương")
        self.assertEqual(d["dai_van"]["tuoi_bat_dau"],93);self.assertEqual(d["luu_nguyet"]["thang"],2)
        self.assertTrue(d["tuan"]);self.assertFalse(d["triet"])

if __name__=="__main__":unittest.main()
