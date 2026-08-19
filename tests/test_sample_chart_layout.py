# -*- coding: utf-8 -*-
"""Regression fixture for the supplied 920x1289 Tử Vi Cổ Học sample."""
from palace_parser import parse_palace_items
from ocr_normalizer import match_star


def item(text, x, y):
    # bbox is normalized to the palace crop.
    return {"text": text, "confidence": 0.99, "bbox": [[x-.03,y-.02],[x+.03,y-.02],[x+.03,y+.02],[x-.03,y+.02]]}


def test_menh_sample_metadata():
    items=[
        item("Mệnh<THÂN>", .50, .08),
        item("K.Hợi", .10, .08),
        item("+Kim", .10, .18),
        item("Thiên Đồng(Đ)", .50, .24),
        item("Trực phù", .25, .34),
        item("Thiên khôi", .70, .34),
        item("Thiên tài", .25, .42),
        item("Thiên thọ", .25, .50),
        item("Hóa lộc", .25, .58),
        item("Địa kiếp(Đ)", .72, .42),
        item("Địa không(Đ)", .72, .50),
        item("ĐV.", .10, .90),
        item("T3", .92, .90),
        item("Trường sinh", .50, .90),
    ]
    p=parse_palace_items(items, match_star, fallback_dia_chi="Hợi")
    assert p["cung"] == "Mệnh"
    assert p["than_cu"] is True
    assert p["can"] == "Kỷ"
    assert p["dia_chi"] == "Hợi"
    assert p["can_chi"] == "Kỷ Hợi"
    assert p["ngu_hanh"] == "Kim"
    assert p["am_duong"] == "Dương"
    assert p["vong_truong_sinh"] == "Trường Sinh"
    assert p["tieu_van"]["so_thu"] == 3


def test_dai_van_and_luu_nguyet_sample():
    items=[
        item("Tử Tức", .50, .08),
        item("B.Thân", .10, .08),
        item("+Kim", .10, .18),
        item("-Liêm Trinh(V)", .50, .24),
        item("93", .92, .08),
        item("Th.2", .92, .18),
        item("ĐV.Tật", .10, .90),
        item("LN.Tài", .92, .90),
        item("Tuyệt", .50, .90),
        item("Tuần", .50, .96),
    ]
    p=parse_palace_items(items, match_star, fallback_dia_chi="Thân")
    assert p["cung"] == "Tử Tức"
    assert p["can_chi"] == "Bính Thân"
    assert p["dai_van"]["tuoi_bat_dau"] == 93
    assert p["dai_van"]["cung"] == "Tật"
    assert p["luu_nien"]["cung"] == "Tài"
    assert p["luu_nguyet"]["thang"] == 2
    assert p["vong_truong_sinh"] == "Tuyệt"
    assert p["tuan"] is True
