#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tử Vi: lập lá số bằng engine định trước -> JSON sạch -> Gemini."""
from __future__ import annotations

import json
import os
from datetime import date, time
from pathlib import Path

import streamlit as st
from google import genai
from google.genai import types

from tuvi_lap_so_engine import lap_la_so
from tu_vi_calculator import calculate_chart

st.set_page_config(page_title="Tử Vi Đẩu Số", page_icon="☯️", layout="wide")
BASE_DIR = Path(__file__).resolve().parent
ENGINE_FILE = BASE_DIR / "tu_vi_engine.json"
BOOKS_FILE = BASE_DIR / "books_cache.json"
PROMPT_DIR = BASE_DIR / "system_prompts"


def secret(name: str) -> str:
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, "") or ""


API_KEY = secret("GEMINI_API_KEY")


@st.cache_resource
def get_client(key: str):
    if not key:
        raise ValueError("Thiếu GEMINI_API_KEY")
    return genai.Client(api_key=key)


@st.cache_data(ttl=3600)
def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, str(exc)


@st.cache_data(ttl=3600)
def load_prompt():
    files = sorted(PROMPT_DIR.glob("*.txt")) if PROMPT_DIR.exists() else []
    if not files:
        return "Bạn là chuyên gia Tử Vi Đẩu Số.", None
    try:
        texts = []
        for path in files:
            text = path.read_text(encoding="utf-8").strip()
            if text:
                texts.append(text)
        return "\n\n".join(texts), None
    except Exception as exc:
        return "", str(exc)


engine, engine_err = load_json(ENGINE_FILE)
books, books_err = load_json(BOOKS_FILE)
system_prompt, prompt_err = load_prompt()

SCHEMA = {
    "type": "object",
    "properties": {
        "tong_quan": {"type": "string"},
        "luan_12_cung": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "cung": {"type": "string"},
                    "ket_luan": {"type": "string"},
                    "can_cu": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["cung", "ket_luan", "can_cu"],
            },
        },
        "dai_van": {"type": "array", "items": {"type": "string"}},
        "tieu_han": {"type": "array", "items": {"type": "string"}},
        "ket_luan": {"type": "array", "items": {"type": "string"}},
        "canh_bao": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["tong_quan", "luan_12_cung", "dai_van", "tieu_han", "ket_luan", "canh_bao"],
}


def compact(value, limit=60000):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return text if len(text) <= limit else text[:limit] + "..."


def generate_analysis(chart, calc, year, note):
    prompt = f"""Năm luận: {year}\nYêu cầu: {note}\n\nDỮ LIỆU LÁ SỐ ĐƯỢC TÍNH BẰNG PYTHON/TuViMCP (nguồn duy nhất về vị trí và sao):\n{compact(chart, 70000)}\n\nDỮ LIỆU QUAN HỆ TÍNH BẰNG PYTHON:\n{compact(calc, 20000)}\n\nENGINE KIẾN THỨC:\n{compact(engine, 70000)}\n\nTÀI LIỆU:\n{compact(books, 50000)}\n\nQUY TẮC: Chỉ sử dụng dữ liệu lá số đã tính. Không đọc ảnh, không dùng OCR, không tự an sao, không tự thêm sao hoặc thay đổi vị trí. Phải luận đủ chính tinh, phụ tinh, sát tinh, vòng Trường Sinh, Tuần/Triệt, Đại vận và Tiểu vận đã có trong JSON. Can-Chi phải dùng dạng đầy đủ như Kỷ Hợi, Bính Thân. Tuổi bắt đầu Đại vận là trường dai_van.tuoi_bat_dau."""
    system = (
        system_prompt
        + "\n\nBẮT BUỘC: Python/TuViMCP là nguồn dữ liệu lập lá số. AI chỉ diễn giải, tuyệt đối không sửa dữ liệu đầu vào."
    )
    cfg = types.GenerateContentConfig(
        system_instruction=system,
        temperature=0.15,
        max_output_tokens=30000,
        response_mime_type="application/json",
        response_schema=SCHEMA,
    )
    return get_client(API_KEY).models.generate_content(
        model="gemini-3.6-flash", contents=prompt, config=cfg
    ).text


def render(raw):
    try:
        data = json.loads(raw)
        st.markdown("### Tổng quan\n" + data.get("tong_quan", ""))
        for item in data.get("luan_12_cung", []):
            with st.expander(item.get("cung", "Cung")):
                st.markdown(item.get("ket_luan", ""))
                st.caption("Căn cứ: " + "; ".join(item.get("can_cu", [])))
        for title, key in [("Đại vận", "dai_van"), ("Tiểu hạn", "tieu_han")]:
            with st.expander(title):
                for item in data.get(key, []):
                    st.write("• " + item)
        st.markdown("### Kết luận")
        for item in data.get("ket_luan", []):
            st.write("• " + item)
        if data.get("canh_bao"):
            with st.expander("⚠️ Cảnh báo"):
                for item in data["canh_bao"]:
                    st.warning(item)
    except Exception:
        st.markdown(raw)


def star_names(items):
    result = []
    for item in items or []:
        if isinstance(item, dict):
            name = item.get("ten") or ""
            state = item.get("dac_tinh") or item.get("trang_thai") or ""
            if name:
                result.append(name + (f" ({state})" if state else ""))
        elif item:
            result.append(str(item))
    return "; ".join(result) or "—"


for key, default in [
    ("chart_json", None),
    ("analysis_result", ""),
    ("confirmed", False),
]:
    st.session_state.setdefault(key, default)

st.title("☯️ TỬ VI ĐẨU SỐ")
st.caption("Lập lá số bằng Python/TuViMCP → an sao tự động → tạo JSON sạch → AI chỉ nhận dữ liệu đã tính.")

st.header("① Lập lá số")
st.info("Không cần tải ảnh lá số. Nhập ngày, tháng, năm, giờ sinh và giới tính; Python sẽ tự lập địa bàn, an sao, Mệnh/Thân, Đại vận và Tiểu vận.")

with st.form("lap_la_so_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
        lich = st.radio("Loại lịch", ["Dương lịch", "Âm lịch"], horizontal=True)
        ngay_sinh = st.date_input("Ngày sinh", value=date(1996, 1, 1), min_value=date(1900, 1, 1), max_value=date(2100, 12, 31), format="DD/MM/YYYY")
    with c2:
        gioi_tinh = st.radio("Giới tính", ["Nam", "Nữ"], horizontal=True)
        ten = st.text_input("Họ tên", "")
    with c3:
        gio = st.time_input("Giờ sinh", value=time(12, 0), step=300)
        mui_gio = st.number_input("Múi giờ", min_value=-12, max_value=14, value=7, step=1)

    st.caption("Giờ sinh được quy về 12 thời thần Tý–Hợi theo engine. Múi giờ mặc định Việt Nam là UTC+7.")
    lap = st.form_submit_button("🧭 LẬP LÁ SỐ", type="primary", use_container_width=True)

if lap:
    try:
        # Quy đổi giờ đồng hồ sang thời thần: Tý=23-01, Sửu=01-03, ..., Hợi=21-23.
        hour = gio.hour
        if hour == 23:
            hour_branch = 1
        else:
            hour_branch = ((hour + 1) // 2) + 1
            if hour_branch > 12:
                hour_branch = 12

        chart = lap_la_so(
            ngay=ngay_sinh.day,
            thang=ngay_sinh.month,
            nam=ngay_sinh.year,
            gio_sinh=hour_branch,
            gioi_tinh=gioi_tinh,
            ten=ten,
            duong_lich=(lich == "Dương lịch"),
            time_zone=int(mui_gio),
        )
        if not isinstance(chart, dict) or not isinstance(chart.get("12_cung"), dict) or len(chart["12_cung"]) != 12:
            raise ValueError("Engine không tạo đủ 12 cung.")
        st.session_state.chart_json = chart
        st.session_state.confirmed = False
        st.session_state.analysis_result = ""
        st.success("Đã lập lá số và an sao thành công. Dữ liệu dưới đây là nguồn duy nhất gửi cho AI.")
    except Exception as exc:
        st.session_state.chart_json = None
        st.error(f"Không thể lập lá số: {type(exc).__name__}: {exc}")


if st.session_state.chart_json:
    chart = st.session_state.chart_json
    st.header("② Lá số đã lập — dữ liệu sạch")

    tb = chart.get("thien_ban", {})
    info_cols = st.columns(5)
    info_cols[0].metric("Can năm", tb.get("can_nam") or "—")
    info_cols[1].metric("Chi năm", tb.get("chi_nam") or "—")
    info_cols[2].metric("Mệnh", tb.get("menh") or "—")
    info_cols[3].metric("Cục", tb.get("ten_cuc") or "—")
    info_cols[4].metric("Thân chủ", tb.get("than_chu") or "—")

    rows = []
    for name, data in chart.get("12_cung", {}).items():
        flags = []
        if data.get("tuan"):
            flags.append("Tuần")
        if data.get("triet"):
            flags.append("Triệt")
        rows.append({
            "Cung": name + (" (Thân cư)" if data.get("than_cu") else ""),
            "Can-Chi": data.get("can_chi") or "—",
            "Hành": data.get("ngu_hanh") or "—",
            "Âm/Dương": data.get("am_duong") or "—",
            "Trường sinh": data.get("vong_trang_sinh") or "—",
            "Tuần/Triệt": ", ".join(flags) or "—",
            "Đại vận": json.dumps(data.get("dai_van", {}), ensure_ascii=False),
            "Tiểu vận": json.dumps(data.get("tieu_van", {}), ensure_ascii=False),
            "Chính tinh": star_names(data.get("chinh_tinh")),
            "Phụ tinh": star_names(data.get("phu_tinh")),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    with st.expander("⭐ Toàn bộ sao theo từng cung"):
        for name, data in chart.get("12_cung", {}).items():
            st.markdown(f"**{name} — {data.get('can_chi', '—')}**")
            st.write("Chính tinh:", star_names(data.get("chinh_tinh")))
            st.write("Phụ tinh:", star_names(data.get("phu_tinh")))
            st.write("Tất cả sao:", star_names(data.get("sao")))

    with st.expander("📦 JSON sạch gửi cho AI"):
        st.json(chart)

    st.download_button(
        "⬇️ Tải JSON lá số",
        data=json.dumps(chart, ensure_ascii=False, indent=2),
        file_name="la_so_tu_vi.json",
        mime="application/json",
        use_container_width=True,
    )

    st.session_state.confirmed = st.checkbox("☑ Tôi đã kiểm tra dữ liệu lá số", value=st.session_state.confirmed)

st.divider()
st.header("③ Luận giải bằng AI")
col1, col2 = st.columns([1, 3])
with col1:
    year = st.number_input("Năm luận", 1950, 2050, 2026)
with col2:
    note = st.text_input("Yêu cầu bổ sung", "Luận giải toàn bộ chính tinh, phụ tinh, sát tinh và các hạn có trong lá số.")

if not st.session_state.confirmed:
    st.info("Hãy lập lá số và xác nhận dữ liệu trước khi gửi cho AI.")

if st.session_state.confirmed and st.button("🔮 BẮT ĐẦU LUẬN GIẢI", type="primary", use_container_width=True):
    if prompt_err or engine_err or books_err:
        st.error("Thiếu System Prompt / Engine / Books.")
    elif not API_KEY:
        st.error("Thiếu GEMINI_API_KEY.")
    else:
        try:
            with st.spinner("Python tính quan hệ → AI luận theo System Prompt..."):
                calc = calculate_chart(st.session_state.chart_json)
                st.session_state.analysis_result = generate_analysis(st.session_state.chart_json, calc, year, note)
        except Exception as exc:
            st.error(f"Không thể gọi AI: {type(exc).__name__}: {exc}")

if st.session_state.analysis_result:
    st.header("④ Kết quả luận giải")
    render(st.session_state.analysis_result)
    st.download_button(
        "⬇️ Tải kết quả luận giải",
        st.session_state.analysis_result,
        "analysis.json",
        "application/json",
    )
