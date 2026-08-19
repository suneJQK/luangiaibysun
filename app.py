#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tử Vi: image scan -> minimal 12-palace table -> Gemini."""
import json, os
from pathlib import Path
import streamlit as st
from google import genai
from google.genai import types
from ocr_engine import crop_12_cung, extract_chart_text
from ocr_normalizer import normalize_processed_data
from chart_validator import validate_chart
from chart_parser import build_chart_json
from tu_vi_calculator import calculate_chart

st.set_page_config(page_title="Tử Vi Đẩu Số", page_icon="☯️", layout="wide")
BASE_DIR=Path(__file__).resolve().parent
ENGINE_FILE=BASE_DIR/"tu_vi_engine.json"; BOOKS_FILE=BASE_DIR/"books_cache.json"; PROMPT_DIR=BASE_DIR/"system_prompts"

def secret(name):
    try:
        if name in st.secrets: return str(st.secrets[name])
    except Exception: pass
    return os.environ.get(name,"") or ""
API_KEY=secret("GEMINI_API_KEY")
@st.cache_resource
def get_client(key):
    if not key: raise ValueError("Thiếu GEMINI_API_KEY")
    return genai.Client(api_key=key)
@st.cache_data(ttl=3600)
def load_json(path):
    try: return json.loads(path.read_text(encoding="utf-8")),None
    except Exception as e: return None,str(e)
@st.cache_data(ttl=3600)
def load_prompt():
    files=sorted(PROMPT_DIR.glob("*.txt")) if PROMPT_DIR.exists() else []
    if not files:return "Bạn là chuyên gia Tử Vi Đẩu Số.",None
    try:return "\n\n".join(p.read_text(encoding="utf-8").strip() for p in files if p.read_text(encoding="utf-8").strip()),None
    except Exception as e:return "",str(e)
engine,engine_err=load_json(ENGINE_FILE); books,books_err=load_json(BOOKS_FILE); system_prompt,prompt_err=load_prompt()
SCHEMA={"type":"object","properties":{"tong_quan":{"type":"string"},"luan_12_cung":{"type":"array","items":{"type":"object","properties":{"cung":{"type":"string"},"ket_luan":{"type":"string"},"can_cu":{"type":"array","items":{"type":"string"}}},"required":["cung","ket_luan","can_cu"]}},"dai_van":{"type":"array","items":{"type":"string"}},"tieu_han":{"type":"array","items":{"type":"string"}},"ket_luan":{"type":"array","items":{"type":"string"}},"canh_bao":{"type":"array","items":{"type":"string"}}},"required":["tong_quan","luan_12_cung","dai_van","tieu_han","ket_luan","canh_bao"]}

def compact(value,limit=60000):
    text=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,separators=(",",":"))
    return text if len(text)<=limit else text[:limit]+"..."

def generate_analysis(chart,calc,year,note):
    prompt=f"Năm luận: {year}\nYêu cầu: {note}\n\nBẢNG 12 CUNG ĐÃ LỌC TỪ OCR (nguồn duy nhất về vị trí/sao):\n{compact(chart,50000)}\n\nDỮ LIỆU TÍNH TOÁN PYTHON:\n{compact(calc,30000)}\n\nENGINE KIẾN THỨC:\n{compact(engine,70000)}\n\nTÀI LIỆU:\n{compact(books,50000)}\n\nChỉ luận các sao có trong BẢNG 12 CUNG. Không nhìn ảnh, không khôi phục dữ liệu OCR thô, không tự thêm sao. Nếu cung có can_xac_nhan thì nêu rõ bất định. Luận đủ các sao được liệt kê trong từng cung và giải thích quan hệ giữa chúng."
    cfg=types.GenerateContentConfig(system_instruction=system_prompt,temperature=0.15,max_output_tokens=30000,response_mime_type="application/json",response_schema=SCHEMA)
    return get_client(API_KEY).models.generate_content(model="gemini-3.6-flash",contents=prompt,config=cfg).text

def render(raw):
    try:
        d=json.loads(raw); st.markdown("### Tổng quan\n"+d.get("tong_quan",""))
        for x in d.get("luan_12_cung",[]):
            with st.expander(x.get("cung","Cung")):
                st.markdown(x.get("ket_luan","")); st.caption("Căn cứ: "+"; ".join(x.get("can_cu",[])))
        for title,key in [("Đại vận","dai_van"),("Tiểu hạn","tieu_han")]:
            with st.expander(title):
                for x in d.get(key,[]): st.write("• "+x)
        st.markdown("### Kết luận")
        for x in d.get("ket_luan",[]):st.write("• "+x)
        if d.get("canh_bao"):
            with st.expander("⚠️ Cảnh báo"):
                for x in d["canh_bao"]:st.warning(x)
    except Exception:st.markdown(raw)

for k,v in [("chart_json",None),("validation",None),("analysis_result","")]:st.session_state.setdefault(k,v)
st.session_state.setdefault("confirmed",False)

st.title("☯️ TỬ VI ĐẨU SỐ")
st.caption("Quét hình ảnh bằng Python → tạo bảng 12 cung tối giản → AI chỉ nhận bảng sạch.")

st.header("① Quét hình ảnh")
uploaded=st.file_uploader("Chọn ảnh lá số",type=["jpg","jpeg","png","webp"])
with st.expander("⚙️ Tùy chỉnh vùng quét"):
    top=st.slider("Bỏ lề trên (%)",0,25,0); bottom=st.slider("Bỏ lề dưới (%)",0,25,3); side=st.slider("Bỏ lề trái/phải (%)",0,15,0); overlap=st.slider("Overlap (px)",5,60,15)
if uploaded:
    from PIL import Image
    image=Image.open(uploaded).convert("RGB")
    with st.expander("Xem ảnh gốc"):st.image(image,use_container_width=True)
    if st.button("🔎 QUÉT HÌNH ẢNH",type="primary",use_container_width=True):
        with st.spinner("Đang tìm tên sao trong 12 cung..."):
            raw=extract_chart_text(image,crop_12_cung(image,top,bottom,side,overlap))
            normalized=normalize_processed_data(raw)
            st.session_state.chart_json=build_chart_json(normalized)
            st.session_state.validation=validate_chart(normalized)
            st.session_state.confirmed=False
        st.success("Đã tạo bảng 12 cung sạch.")

if st.session_state.chart_json:
    st.header("② Bảng 12 cung")
    chart=st.session_state.chart_json
    rows=[]
    for name,data in chart.get("12_cung",{}).items():
        stars=" • ".join(data.get("sao",[])) or "—"
        if data.get("can_xac_nhan"):stars += "  ⚠ " + ", ".join(data["can_xac_nhan"])
        rows.append({"Cung":name,"Địa chi":data.get("dia_chi","—"),"Các sao":stars})
    if rows:st.dataframe(rows,use_container_width=True,hide_index=True)
    with st.expander("Xem JSON sạch gửi cho AI"):st.json(chart)
    v=st.session_state.validation or {"errors":[],"warnings":[]}
    if v.get("errors"):st.error("; ".join(v["errors"][:5]))
    if v.get("warnings"):st.warning(f"Có {len(v['warnings'])} cảnh báo cần kiểm tra.")
    st.session_state.confirmed=st.checkbox("☑ Tôi đã kiểm tra bảng 12 cung",value=st.session_state.confirmed)

st.divider(); st.header("③ Luận giải")
col1,col2=st.columns([1,3])
with col1:year=st.number_input("Năm luận",1950,2050,2026)
with col2:note=st.text_input("Yêu cầu bổ sung","Luận giải toàn bộ sao có trong bảng 12 cung.")
if not st.session_state.confirmed:st.info("Hãy quét hình ảnh và xác nhận bảng 12 cung trước khi luận giải.")
if st.session_state.confirmed and st.button("🔮 BẮT ĐẦU LUẬN GIẢI",type="primary",use_container_width=True):
    if prompt_err or engine_err or books_err:st.error("Thiếu System Prompt / Engine / Books.")
    elif not API_KEY:st.error("Thiếu GEMINI_API_KEY.")
    else:
        with st.spinner("Python tính dữ liệu → AI luận theo System Prompt..."):
            calc=calculate_chart(st.session_state.chart_json)
            st.session_state.analysis_result=generate_analysis(st.session_state.chart_json,calc,year,note)
if st.session_state.analysis_result:
    st.header("④ Kết quả luận giải"); render(st.session_state.analysis_result)
    st.download_button("⬇️ Tải JSON",st.session_state.analysis_result,"analysis.json","application/json")
