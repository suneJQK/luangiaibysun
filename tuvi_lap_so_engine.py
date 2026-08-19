# -*- coding: utf-8 -*-
"""Adapter for the locally vendored TuViMCP chart/ansa engine."""
from __future__ import annotations

import unicodedata
from typing import Any

from vendor.tuvi_mcp._engine import diaBan, lapDiaBan, lapThienBan

BRANCH_TO_INDEX = {"Tý": 1, "Sửu": 2, "Dần": 3, "Mão": 4, "Thìn": 5, "Tỵ": 6, "Tị": 6, "Ngọ": 7, "Mùi": 8, "Thân": 9, "Dậu": 10, "Tuất": 11, "Hợi": 12}
MAIN_STAR_NAMES = {"tử vi", "thiên cơ", "thái dương", "vũ khúc", "thiên đồng", "liêm trinh", "thiên phủ", "thái âm", "tham lang", "cự môn", "thiên tướng", "thiên lương", "thất sát", "phá quân"}

def _canonical_name(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    text = text.split("[", 1)[0].strip()
    text = unicodedata.normalize("NFC", text).casefold()
    return " ".join(text.split())

def _gender_value(gioi_tinh: str | int) -> int:
    if isinstance(gioi_tinh, int): return 1 if gioi_tinh == 1 else -1
    value = str(gioi_tinh).strip().lower()
    if value in {"nam", "male", "m", "1", "+1"}: return 1
    if value in {"nữ", "nu", "female", "f", "0", "-1"}: return -1
    raise ValueError("gioi_tinh phải là Nam/Nữ hoặc 1/-1")

def _hour_branch(gio_sinh: str | int) -> int:
    if isinstance(gio_sinh, int):
        if 1 <= gio_sinh <= 12: return gio_sinh
        raise ValueError("gio_sinh phải nằm trong 1..12")
    value = str(gio_sinh).strip()
    if value.isdigit(): return _hour_branch(int(value))
    if value not in BRANCH_TO_INDEX: raise ValueError(f"Không nhận diện được giờ sinh: {gio_sinh}")
    return BRANCH_TO_INDEX[value]

def _star_dict(star: dict[str, Any]) -> dict[str, Any]:
    return {"id": star.get("saoID"), "ten": star.get("saoTen"), "ngu_hanh": star.get("saoNguHanh"), "loai": star.get("saoLoai"), "phuong_vi": star.get("saoPhuongVi"), "am_duong": star.get("saoAmDuong"), "dac_tinh": star.get("saoDacTinh"), "vong_trang_sinh": bool(star.get("vongTrangSinh"))}

def _is_main_star(star: dict[str, Any]) -> bool:
    if _canonical_name(star.get("ten")) in MAIN_STAR_NAMES: return True
    loai = star.get("loai")
    return loai == 1 or str(loai).strip() == "1"

def _palace_json(cung: Any) -> dict[str, Any]:
    stars = [_star_dict(x) for x in getattr(cung, "cungSao", [])]
    main = [x for x in stars if _is_main_star(x)]
    phu = [x for x in stars if not _is_main_star(x) and not x.get("vong_trang_sinh")]
    trang_sinh = [x for x in stars if x.get("vong_trang_sinh")]
    return {"cung": getattr(cung, "cungChu", ""), "can_chi": getattr(cung, "cungTen", "").strip(), "dia_chi": getattr(cung, "cungDiaChi", ""), "ngu_hanh": getattr(cung, "cungHanh", ""), "am_duong": "Dương" if getattr(cung, "cungAmDuong", 0) == 1 else "Âm", "than_cu": bool(getattr(cung, "cungThan", False)), "tuan": bool(getattr(cung, "tuanTrung", False)), "triet": bool(getattr(cung, "trietLo", False)), "dai_van": {"tuoi_bat_dau": getattr(cung, "cungDaiHan", None)}, "tieu_van": {"chi": getattr(cung, "cungTieuHan", None)}, "chinh_tinh": main, "phu_tinh": phu, "vong_trang_sinh": trang_sinh[0]["ten"] if trang_sinh else None, "sao": stars}

def lap_la_so(ngay: int, thang: int, nam: int, gio_sinh: str | int, gioi_tinh: str | int, ten: str = "", duong_lich: bool = True, time_zone: int = 7) -> dict[str, Any]:
    gender = _gender_value(gioi_tinh)
    hour_branch = _hour_branch(gio_sinh)
    db = lapDiaBan(diaBan, ngay, thang, nam, hour_branch, gender, duong_lich, time_zone)
    tb = lapThienBan(ngay, thang, nam, hour_branch, gender, ten, db, duong_lich, time_zone)
    cungs: dict[str, Any] = {}
    for idx in range(1, 13):
        row = _palace_json(db.thapNhiCung[idx])
        cungs[row["cung"] or row["dia_chi"] or str(idx)] = row
    return {"schema_version": "engine_1.2", "source": "local_vendor_TuViMCP_667c68f", "input": {"ngay": ngay, "thang": thang, "nam": nam, "gio_sinh": hour_branch, "gioi_tinh": "Nam" if gender == 1 else "Nữ", "duong_lich": duong_lich, "time_zone": time_zone}, "thien_ban": {"ten": getattr(tb, "ten", ten), "nam_nu": getattr(tb, "namNu", None), "gio_sinh": getattr(tb, "gioSinh", None), "can_nam": getattr(tb, "canNamTen", None), "chi_nam": getattr(tb, "chiNamTen", None), "can_thang": getattr(tb, "canThangTen", None), "can_ngay": getattr(tb, "canNgayTen", None), "menh": getattr(tb, "menh", None), "ban_menh": getattr(tb, "banMenh", None), "ten_cuc": getattr(tb, "tenCuc", None), "menh_chu": getattr(tb, "menhChu", None), "than_chu": getattr(tb, "thanChu", None), "am_duong_menh": getattr(tb, "amDuongMenh", None), "sinh_khac": getattr(tb, "sinhKhac", None)}, "12_cung": cungs}
