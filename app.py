#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tử Vi: lập lá số bằng TuViMCP vendored -> dữ liệu chuẩn -> chat AI."""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import streamlit as st
from google import genai
from google.genai import types

from tuvi_lap_so_engine import lap_la_so
from tu_vi_calculator import calculate_chart

st.set_page_config(page_title="Tử Vi Đẩu Số", page_icon="☯️", layout="wide")
BASE_DIR = Path(__file__).resolve().parent
BOOKS_FILE = BASE_DIR / "books_cache.json"
PROMPT_DIR = BASE_DIR / "system_prompts"
ENGINE_SOURCE = "local vendor: TuViMCP@667c68f564e135cae207df3471273f639fa2feb4"


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
        return {}, str(exc)


@st.cache_data(ttl=3600)
def load_prompt():
    files = sorted(PROMPT_DIR.glob("*.txt")) if PROMPT_DIR.exists() else []
    if not files:
        return "Bạn là chuyên gia Tử Vi Đẩu Số.", None
    try:
        return "\n\n".join(p.read_text(encoding="utf-8").strip() for p in files), None
    except Exception as exc:
        return "Bạn là chuyên gia Tử Vi Đẩu Số.", str(exc)


books, _ = load_json(BOOKS_FILE)
system_prompt, _ = load_prompt()


def compact(value, limit=90000):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return text if len(text) <= limit else text[:limit] + "..."


def ask_ai(question: str, chart: dict, calc: dict, year: int):
    prompt = f"""Năm luận: {year}

CÂU HỎI CỦA NGƯỜI DÙNG:
{question}

DỮ LIỆU LẬP LÁ SỐ TỪ ENGINE PYTHON/TuViMCP LOCAL:
{compact(chart)}

DỮ LIỆU QUAN HỆ TÍNH BẰNG PYTHON:
{compact(calc, 30000)}

TÀI LIỆU THAM KHẢO:
{compact(books, 40000)}

YÊU CẦU:
- Chỉ dùng dữ liệu lá số đã cung cấp.
- Không đọc ảnh và không dùng OCR.
- Không tự an sao, không tự thêm sao hoặc sửa Can-Chi.
- Dùng đầy đủ chính tinh, phụ tinh, sát tinh, Tứ Hóa, Tràng Sinh, Tuần/Triệt, Đại vận, Tiểu vận và các dữ liệu hạn nếu có.
- Can-Chi phải dùng dạng đầy đủ như Kỷ Hợi, Bính Thân.
- Nếu dữ liệu không có thông tin cần thiết, nói rõ thay vì tự đoán.
- Trả lời trực tiếp câu hỏi, có căn cứ từ lá số và giải thích dễ hiểu.
"""
    system = system_prompt + "\n\nBẮT BUỘC: TuViMCP LOCAL/Python là nguồn dữ liệu lập lá số. AI chỉ diễn giải và tuyệt đối không được thay đổi dữ liệu đầu vào."
    cfg = types.GenerateContentConfig(
        system_instruction=system,
        temperature=0.2,
        max_output_tokens=30000,
    )
    return get_client(API_KEY).models.generate_content(
        model="gemini-3.6-flash", contents=prompt, config=cfg
    ).text


for key, default in [("chart_json", None), ("chat_history", [])]:
    st.session_state.setdefault(key, default)

st.title("☯️ TỬ VI ĐẨU SỐ")
st.caption("Lập lá số bằng TuViMCP LOCAL → dữ liệu chuẩn → AI luận giải")

st.header("① Lập lá số")
st.info("TuViMCP được tích hợp trực tiếp trong repository, không gọi engine từ repository gốc.")

with st.form("lap_la_so_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
        lich = st.radio("Loại lịch", ["Dương lịch", "Âm lịch"], horizontal=True)
        ngay_sinh = st.date_input(
            "Ngày sinh", value=date(1996, 1, 1),
            min_value=date(1900, 1, 1), max_value=date(2100, 12, 31),
            format="DD/MM/YYYY",
        )
    with c2:
        gioi_tinh = st.radio("Giới tính", ["Nam", "Nữ"], horizontal=True)
        ten = st.text_input("Họ tên", "")
    with c3:
        hour_labels = [
            "Tý (23:00–00:59)", "Sửu (01:00–02:59)", "Dần (03:00–04:59)",
            "Mão (05:00–06:59)", "Thìn (07:00–08:59)", "Tỵ (09:00–10:59)",
            "Ngọ (11:00–12:59)", "Mùi (13:00–14:59)", "Thân (15:00–16:59)",
            "Dậu (17:00–18:59)", "Tuất (19:00–20:59)", "Hợi (21:00–22:59)",
        ]
        gio_label = st.selectbox("Giờ sinh — chọn trực tiếp", hour_labels, index=6)
        mui_gio = st.number_input("Múi giờ", min_value=-12, max_value=14, value=7, step=1)
    st.caption("Chọn trực tiếp thời thần. Tý bắt đầu từ 23:00.")
    lap = st.form_submit_button("🧭 LẬP LÁ SỐ", type="primary", use_container_width=True)

if lap:
    try:
        branch = gio_label.split(" ", 1)[0]
        chart = lap_la_so(
            ngay=ngay_sinh.day,
            thang=ngay_sinh.month,
            nam=ngay_sinh.year,
            gio_sinh=branch,
            gioi_tinh=gioi_tinh,
            ten=ten,
            duong_lich=(lich == "Dương lịch"),
            time_zone=int(mui_gio),
        )
        if not isinstance(chart, dict) or len(chart.get("12_cung", {})) != 12:
            raise ValueError("Engine không tạo đủ 12 cung.")
        chart.setdefault("input", {})["gio_hien_thi"] = gio_label
        chart["input"]["lich"] = lich
        st.session_state.chart_json = chart
        st.session_state.chat_history = []
        st.success("Đã lập lá số và an sao bằng engine local.")
    except Exception as exc:
        st.error(f"Không thể lập lá số: {type(exc).__name__}: {exc}")

if st.session_state.chart_json:
    chart = st.session_state.chart_json
    tb = chart.get("thien_ban", {})

    # Không hiển thị bàn lá số 4x4. Chỉ hiển thị dữ liệu gọn để kiểm tra.
    st.header("② Dữ liệu lập lá số")
    m = st.columns(5)
    m[0].metric("Nguồn", "LOCAL")
    m[1].metric("12 cung", len(chart.get("12_cung", {})))
    m[2].metric("Cục", tb.get("ten_cuc") or "—")
    m[3].metric("Mệnh", tb.get("menh") or "—")
    m[4].metric("Thân", tb.get("than_chu") or "—")

    tabs = st.tabs(["Thiên bàn", "12 cung", "Hạn", "JSON gửi AI"])
    with tabs[0]:
        st.json(tb)
    with tabs[1]:
        rows = []
        for name, data in chart.get("12_cung", {}).items():
            if not isinstance(data, dict):
                continue
            flags = [x for x, ok in (("Tuần", data.get("tuan")), ("Triệt", data.get("triet"))) if ok]
            main = data.get("chinh_tinh") or []
            phu = data.get("phu_tinh") or []
            def names(items):
                result = []
                for x in items:
                    result.append(x.get("ten", "") if isinstance(x, dict) else str(x))
                return "; ".join(x for x in result if x) or "—"
            rows.append({
                "Cung": name + (" (Thân cư)" if data.get("than_cu") else ""),
                "Can-Chi": data.get("can_chi") or "—",
                "Ngũ hành": data.get("ngu_hanh") or "—",
                "Tràng sinh": data.get("vong_trang_sinh") or "—",
                "Tuần/Triệt": ", ".join(flags) or "—",
                "Chính tinh": names(main),
                "Phụ tinh": names(phu),
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)
    with tabs[2]:
        st.json({name: data.get("dai_van", {}) | {"tieu_van": data.get("tieu_van", {}), "luu_nien": data.get("luu_nien", {}), "luu_nguyet": data.get("luu_nguyet", {})} for name, data in chart.get("12_cung", {}).items() if isinstance(data, dict)})
    with tabs[3]:
        st.json(chart)

    st.download_button(
        "⬇️ Tải JSON lá số",
        data=json.dumps(chart, ensure_ascii=False, indent=2),
        file_name="la_so_tu_vi.json",
        mime="application/json",
        use_container_width=True,
    )

    st.header("③ Chat với AI")
    st.caption("AI chỉ nhận dữ liệu lập lá số từ TuViMCP LOCAL và dữ liệu Python; không nhận ảnh/OCR.")

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input("Nhập câu hỏi về lá số…")
    if question:
        st.session_state.chat_history.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            try:
                with st.spinner("AI đang luận giải…"):
                    calc = calculate_chart(chart)
                    answer = ask_ai(question, chart, calc, date.today().year)
                st.markdown(answer)
                st.session_state.chat_history.append({"role": "assistant", "content": answer})
            except Exception as exc:
                answer = f"Không thể gọi AI: {type(exc).__name__}: {exc}"
                st.error(answer)
                st.session_state.chat_history.append({"role": "assistant", "content": answer})
else:
    st.info("Nhập thông tin sinh và bấm LẬP LÁ SỐ. Sau đó phần Chat với AI sẽ xuất hiện.")
