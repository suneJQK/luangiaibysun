#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tử Vi: lập lá số bằng engine TuViMCP vendored -> dữ liệu chuẩn -> AI."""
from __future__ import annotations

import html
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
        return None, str(exc)


@st.cache_data(ttl=3600)
def load_prompt():
    files = sorted(PROMPT_DIR.glob("*.txt")) if PROMPT_DIR.exists() else []
    if not files:
        return "Bạn là chuyên gia Tử Vi Đẩu Số.", None
    try:
        texts = [p.read_text(encoding="utf-8").strip() for p in files]
        return "\n\n".join(x for x in texts if x), None
    except Exception as exc:
        return "", str(exc)


books, books_err = load_json(BOOKS_FILE)
system_prompt, prompt_err = load_prompt()

SCHEMA = {
    "type": "object",
    "properties": {
        "tong_quan": {"type": "string"},
        "luan_12_cung": {"type": "array", "items": {"type": "object", "properties": {
            "cung": {"type": "string"}, "ket_luan": {"type": "string"},
            "can_cu": {"type": "array", "items": {"type": "string"}}
        }, "required": ["cung", "ket_luan", "can_cu"]}},
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
    prompt = f"""Năm luận: {year}\nYêu cầu: {note}\n\nDỮ LIỆU LẬP LÁ SỐ TỪ ENGINE PYTHON/TuViMCP LOCAL:\n{compact(chart, 90000)}\n\nDỮ LIỆU QUAN HỆ TÍNH BẰNG PYTHON:\n{compact(calc, 20000)}\n\nTÀI LIỆU THAM KHẢO:\n{compact(books, 50000)}\n\nQUY TẮC: Dữ liệu trong JSON lá số là nguồn duy nhất về vị trí cung và sao. Không đọc ảnh, không dùng OCR, không tự an sao, không tự thêm sao, không sửa Can-Chi. Phải dùng đầy đủ chính tinh, phụ tinh, sát tinh, Tứ Hóa, vòng Trường Sinh, Tuần/Triệt, Đại vận và Tiểu vận đã có. Can-Chi phải dùng dạng đầy đủ như Kỷ Hợi, Bính Thân. Tuổi bắt đầu Đại vận nằm ở dai_van.tuoi_bat_dau."""
    system = system_prompt + "\n\nBẮT BUỘC: TuViMCP LOCAL/Python là nguồn dữ liệu lập lá số. AI chỉ diễn giải và không được thay đổi dữ liệu đầu vào."
    cfg = types.GenerateContentConfig(system_instruction=system, temperature=0.15, max_output_tokens=30000, response_mime_type="application/json", response_schema=SCHEMA)
    return get_client(API_KEY).models.generate_content(model="gemini-3.6-flash", contents=prompt, config=cfg).text


def star_names(items):
    out = []
    for item in items or []:
        if isinstance(item, dict):
            name = item.get("ten") or ""
            state = item.get("dac_tinh") or item.get("trang_thai") or ""
            if name:
                out.append(name + (f" ({state})" if state else ""))
        elif item:
            out.append(str(item))
    return "; ".join(out) or "—"


def render_analysis(raw):
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
        for item in data.get("ket_luan", []): st.write("• " + item)
        if data.get("canh_bao"):
            with st.expander("⚠️ Cảnh báo"):
                for item in data["canh_bao"]: st.warning(item)
    except Exception:
        st.markdown(raw)


def _cell(data: dict, branch: str) -> str:
    if not data:
        return '<div class="palace empty"></div>'
    flags = []
    if data.get("tuan"): flags.append("TUẦN")
    if data.get("triet"): flags.append("TRIỆT")
    flag = " · ".join(flags)
    main = ", ".join(x.get("ten", "") for x in data.get("chinh_tinh", []) if isinstance(x, dict) and x.get("ten"))
    phu = ", ".join(x.get("ten", "") for x in data.get("phu_tinh", []) if isinstance(x, dict) and x.get("ten"))
    dv = data.get("dai_van", {}).get("tuoi_bat_dau")
    tv = data.get("tieu_van", {}).get("chi")
    return f'''<div class="palace"><div class="phead"><b>{html.escape(data.get("cung") or branch)}</b><span>{html.escape(data.get("can_chi") or branch)}</span></div><div class="meta">{html.escape(data.get("ngu_hanh") or "")} · {html.escape(data.get("vong_trang_sinh") or "")}</div><div class="flags">{html.escape(flag)}</div><div class="main">{html.escape(main or "—")}</div><div class="stars">{html.escape(phu or "")}</div><div class="small">ĐV {html.escape(str(dv if dv is not None else "—"))} · TV {html.escape(str(tv or "—"))}</div></div>'''


def render_chart(chart: dict):
    c = chart.get("12_cung", {})
    # Standard 4x4 Tử Vi board: the four center cells are left blank.
    layout = [["Tỵ", "Ngọ", "Mùi", "Thân"], ["Thìn", "", "", "Dậu"], ["Mão", "", "", "Tuất"], ["Dần", "Sửu", "Tý", "Hợi"]]
    by_branch = {str(v.get("dia_chi", "")): v for v in c.values() if isinstance(v, dict)}
    cards = "".join(_cell(by_branch.get(branch), branch) if branch else '<div class="center"><b>LÁ SỐ TỬ VI</b><br><span>TuViMCP LOCAL</span></div>' for row in layout for branch in row)
    st.markdown('''<style>.board{display:grid;grid-template-columns:repeat(4,minmax(170px,1fr));gap:3px;background:#555;padding:3px;border-radius:10px}.palace,.center{min-height:190px;background:#fff;padding:8px;overflow:hidden;border:1px solid #bbb}.center{display:flex;align-items:center;justify-content:center;text-align:center;font-size:18px}.center span{font-size:11px;opacity:.65}.phead{display:flex;justify-content:space-between;border-bottom:1px solid #ddd;padding-bottom:4px}.phead span{font-size:12px}.meta,.flags,.small{font-size:11px;margin-top:4px}.flags{font-weight:700}.main{font-weight:700;font-size:13px;margin-top:8px}.stars{font-size:11px;margin-top:5px;line-height:1.35}.small{border-top:1px solid #eee;padding-top:5px}@media(max-width:900px){.board{grid-template-columns:repeat(2,minmax(150px,1fr))}}</style>''', unsafe_allow_html=True)
    st.markdown(f'<div class="board">{cards}</div>', unsafe_allow_html=True)


for key, default in [("chart_json", None), ("analysis_result", ""), ("confirmed", False)]:
    st.session_state.setdefault(key, default)

st.title("☯️ TỬ VI ĐẨU SỐ")
st.caption("Lập lá số bằng TuViMCP LOCAL → an sao → hiển thị địa bàn → JSON chuẩn → AI chỉ luận trên dữ liệu đã tính.")

st.header("① Lập lá số")
st.info("Engine TuViMCP được tích hợp trực tiếp trong repository. Không gọi engine từ repository gốc.")

with st.form("lap_la_so_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
        lich = st.radio("Loại lịch", ["Dương lịch", "Âm lịch"], horizontal=True)
        ngay_sinh = st.date_input("Ngày sinh", value=date(1996, 1, 1), min_value=date(1900, 1, 1), max_value=date(2100, 12, 31), format="DD/MM/YYYY")
    with c2:
        gioi_tinh = st.radio("Giới tính", ["Nam", "Nữ"], horizontal=True)
        ten = st.text_input("Họ tên", "")
    with c3:
        hour_labels = ["Tý (23:00–00:59)", "Tý (00:00–00:59)", "Sửu (01:00–02:59)", "Dần (03:00–04:59)", "Mão (05:00–06:59)", "Thìn (07:00–08:59)", "Tỵ (09:00–10:59)", "Ngọ (11:00–12:59)", "Mùi (13:00–14:59)", "Thân (15:00–16:59)", "Dậu (17:00–18:59)", "Tuất (19:00–20:59)", "Hợi (21:00–22:59)"]
        gio_label = st.selectbox("Giờ sinh — chọn trực tiếp", hour_labels, index=7, key="gio_sinh_label")
        mui_gio = st.number_input("Múi giờ", min_value=-12, max_value=14, value=7, step=1)
    st.caption("Giờ được chọn theo 12 thời thần. Tý bắt đầu từ 23:00; nếu sinh đúng 23:00–23:59 vẫn thuộc giờ Tý. Bạn có thể đổi giờ trực tiếp, không cần nhập thủ công.")
    lap = st.form_submit_button("🧭 LẬP LÁ SỐ", type="primary", use_container_width=True)

if lap:
    try:
        branch = gio_label.split(" ", 1)[0]
        chart = lap_la_so(ngay=ngay_sinh.day, thang=ngay_sinh.month, nam=ngay_sinh.year, gio_sinh=branch, gioi_tinh=gioi_tinh, ten=ten, duong_lich=(lich == "Dương lịch"), time_zone=int(mui_gio))
        if not isinstance(chart, dict) or len(chart.get("12_cung", {})) != 12:
            raise ValueError("Engine không tạo đủ 12 cung.")
        chart.setdefault("input", {})["gio_hien_thi"] = gio_label
        st.session_state.chart_json = chart
        st.session_state.confirmed = False
        st.session_state.analysis_result = ""
        st.success("Đã lập lá số và an sao bằng engine local.")
    except Exception as exc:
        st.session_state.chart_json = None
        st.error(f"Không thể lập lá số: {type(exc).__name__}: {exc}")

if st.session_state.chart_json:
    chart = st.session_state.chart_json
    st.header("② Lá số")
    tb = chart.get("thien_ban", {})
    meta = st.columns(5)
    meta[0].metric("Nguồn", "LOCAL")
    meta[1].metric("12 cung", len(chart.get("12_cung", {})))
    meta[2].metric("Cục", tb.get("ten_cuc") or "—")
    meta[3].metric("Mệnh", tb.get("menh") or "—")
    meta[4].metric("Thân", tb.get("than_chu") or "—")
    render_chart(chart)

    st.header("③ Dữ liệu lập lá số")
    tabs = st.tabs(["Thiên bàn", "12 cung", "Hạn", "JSON gửi AI"])
    with tabs[0]: st.json(tb)
    with tabs[1]:
        rows = []
        for name, data in chart.get("12_cung", {}).items():
            flags = [x for x, ok in (("Tuần", data.get("tuan")), ("Triệt", data.get("triet"))) if ok]
            rows.append({"Cung": name + (" (Thân cư)" if data.get("than_cu") else ""), "Can-Chi": data.get("can_chi") or "—", "Hành": data.get("ngu_hanh") or "—", "Âm/Dương": data.get("am_duong") or "—", "Trường sinh": data.get("vong_trang_sinh") or "—", "Tuần/Triệt": ", ".join(flags) or "—", "Chính tinh": star_names(data.get("chinh_tinh")), "Phụ tinh": star_names(data.get("phu_tinh"))})
        st.dataframe(rows, use_container_width=True, hide_index=True)
    with tabs[2]:
        for name, data in chart.get("12_cung", {}).items():
            dv, tv = data.get("dai_van", {}), data.get("tieu_van", {})
            if dv.get("tuoi_bat_dau") is not None or tv:
                st.write(f"**{name}** — Đại vận bắt đầu: {dv.get('tuoi_bat_dau', '—')} | Tiểu vận: {tv.get('chi', '—')}")
    with tabs[3]:
        st.caption(f"Nguồn: {ENGINE_SOURCE}")
        st.json(chart)

    st.download_button("⬇️ Tải JSON dữ liệu lập lá số", json.dumps(chart, ensure_ascii=False, indent=2), "la_so_tuvi_engine.json", "application/json", use_container_width=True)
    st.session_state.confirmed = st.checkbox("☑ Tôi đã kiểm tra dữ liệu lập lá số", value=st.session_state.confirmed)

st.divider()
st.header("④ Luận giải bằng AI")
year = st.number_input("Năm luận", 1950, 2050, 2026)
note = st.text_input("Yêu cầu bổ sung", "Luận giải toàn bộ chính tinh, phụ tinh, sát tinh, Tứ Hóa và các hạn có trong lá số.")
if not st.session_state.confirmed: st.info("Hãy lập lá số và xác nhận dữ liệu trước khi gửi cho AI.")
if st.session_state.confirmed and st.button("🔮 BẮT ĐẦU LUẬN GIẢI", type="primary", use_container_width=True):
    if prompt_err or books_err: st.error("Thiếu System Prompt hoặc tài liệu.")
    elif not API_KEY: st.error("Thiếu GEMINI_API_KEY.")
    else:
        try:
            with st.spinner("Python tính quan hệ → AI luận theo System Prompt..."):
                calc = calculate_chart(st.session_state.chart_json)
                st.session_state.analysis_result = generate_analysis(st.session_state.chart_json, calc, year, note)
        except Exception as exc: st.error(f"Không thể gọi AI: {type(exc).__name__}: {exc}")
if st.session_state.analysis_result:
    st.header("⑤ Kết quả luận giải")
    render_analysis(st.session_state.analysis_result)
    st.download_button("⬇️ Tải kết quả luận giải", st.session_state.analysis_result, "analysis.json", "application/json")
