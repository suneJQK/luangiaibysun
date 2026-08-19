#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tử Vi: local image scan -> normalized/validated Chart JSON -> Gemini."""
import json, os, uuid
from datetime import datetime
from pathlib import Path
import streamlit as st
from github import Github, GithubException
from google import genai
from google.genai import types
from ocr_engine import crop_12_cung, extract_chart_text
from ocr_normalizer import normalize_processed_data
from chart_validator import validate_chart
from chart_parser import build_chart_json
from tu_vi_calculator import calculate_chart

st.set_page_config(page_title="Tử Vi Đẩu Số", page_icon="☯️", layout="wide", initial_sidebar_state="expanded")
BASE_DIR=Path(__file__).resolve().parent
ENGINE_FILE=BASE_DIR/"tu_vi_engine.json"; BOOKS_FILE=BASE_DIR/"books_cache.json"; PROMPT_DIR=BASE_DIR/"system_prompts"

def get_secret(name, default=""):
    try:
        if name in st.secrets: return str(st.secrets[name])
    except Exception: pass
    return str(os.environ.get(name, default) or "")
API_KEY=get_secret("GEMINI_API_KEY"); GITHUB_TOKEN=get_secret("GITHUB_TOKEN"); GITHUB_REPO=get_secret("GITHUB_REPO")
@st.cache_resource
def get_gemini_client(key):
    if not key: raise ValueError("Chưa cấu hình GEMINI_API_KEY.")
    return genai.Client(api_key=key)
@st.cache_data(ttl=3600)
def load_json_file(path):
    if not path.exists(): return None, f"Không tìm thấy {path.name}"
    try: return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as e: return None, f"{path.name} không hợp lệ: {e}"
@st.cache_data(ttl=3600)
def load_system_prompt():
    files=sorted(PROMPT_DIR.glob("*.txt"),key=lambda p:p.name.lower()) if PROMPT_DIR.exists() else []
    if not files: return "Bạn là chuyên gia Tử Vi Đẩu Số cao cấp.",None
    try:
        parts=[]
        for p in files:
            text=p.read_text(encoding="utf-8").strip()
            if text: parts.append(f"===== {p.name} =====\n{text}")
        return "\n\n".join(parts),None
    except Exception as e: return "",str(e)
def compact(data,limit):
    text=data if isinstance(data,str) else json.dumps(data,ensure_ascii=False,indent=2)
    return text if len(text)<=limit else text[:limit]+"\n...[truncated]..."
@st.cache_data(ttl=3600)
def load_books():
    data,err=load_json_file(BOOKS_FILE); return (compact(data,100000),None) if not err else ("",err)
def upload_to_github(f):
    if not GITHUB_TOKEN or not GITHUB_REPO: return False,"Thiếu GITHUB_TOKEN hoặc GITHUB_REPO."
    try:
        repo=Github(GITHUB_TOKEN).get_repo(GITHUB_REPO); ext=Path(f.name).suffix.lower() or ".png"; name=f"laso_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}{ext}"; path=f"uploaded_laso/{name}"
        repo.create_file(path=path,message=f"Upload lá số: {name}",content=f.getvalue()); return True,f"https://github.com/{GITHUB_REPO}/blob/main/{path}"
    except (GithubException,Exception) as e: return False,str(e)
SCHEMA={"type":"object","properties":{"tong_quan":{"type":"string"},"kiem_tra_du_lieu":{"type":"array","items":{"type":"string"}},"luan_12_cung":{"type":"array","items":{"type":"object","properties":{"cung":{"type":"string"},"ket_luan":{"type":"string"},"can_cu":{"type":"array","items":{"type":"string"}}},"required":["cung","ket_luan","can_cu"]}},"dai_van":{"type":"array","items":{"type":"string"}},"tieu_han":{"type":"array","items":{"type":"string"}},"ket_luan":{"type":"array","items":{"type":"string"}},"canh_bao":{"type":"array","items":{"type":"string"}}},"required":["tong_quan","kiem_tra_du_lieu","luan_12_cung","dai_van","tieu_han","ket_luan","canh_bao"]}
def make_prompt(engine,books,chart,calc,year,note):
    return f"""Năm luận: {year}\nYêu cầu bổ sung: {note}\n\nDỮ LIỆU CHỈ ĐƯỢC PHÉP DÙNG SAU KHI PYTHON XỬ LÝ VÀ XÁC NHẬN\nCHART JSON:\n{compact(chart,100000)}\n\nCALCULATION JSON:\n{compact(calc,80000)}\n\nENGINE:\n{compact(engine,100000)}\n\nBOOKS:\n{books}\n\nTuân thủ toàn bộ SYSTEM INSTRUCTION ở cấp system. Không nhìn ảnh, không tự tạo dữ liệu thiếu, không kết luận từ một sao đơn lẻ. Trả JSON đúng schema."""
def gemini_config(system_prompt, **kwargs): return types.GenerateContentConfig(system_instruction=system_prompt, **kwargs)
def generate_analysis(chart,calc,system,engine,books,year,note):
    r=get_gemini_client(API_KEY).models.generate_content(model="gemini-3.6-flash",contents=make_prompt(engine,books,chart,calc,year,note),config=gemini_config(system,temperature=0.15,max_output_tokens=30000,response_mime_type="application/json",response_schema=SCHEMA))
    return getattr(r,"text","")
def render_analysis(raw):
    try:
        d=json.loads(raw)
        st.markdown("### Tổng quan\n"+d.get("tong_quan",""))
        with st.expander("Kiểm tra dữ liệu", expanded=False):
            for x in d.get("kiem_tra_du_lieu",[]): st.write("• "+x)
        for x in d.get("luan_12_cung",[]):
            with st.expander(x.get("cung","Cung"), expanded=False):
                st.markdown(x.get("ket_luan","")); st.caption("Căn cứ: "+"; ".join(x.get("can_cu",[])))
        with st.expander("Đại vận", expanded=False):
            for x in d.get("dai_van",[]): st.write("• "+x)
        with st.expander("Tiểu hạn", expanded=False):
            for x in d.get("tieu_han",[]): st.write("• "+x)
        st.markdown("### Kết luận")
        for x in d.get("ket_luan",[]): st.write("• "+x)
        if d.get("canh_bao"):
            with st.expander("⚠️ Cảnh báo", expanded=False):
                for x in d["canh_bao"]: st.warning(x)
    except Exception: st.markdown(raw)

for key,default in [("processed_data",None),("chart_json",None),("validation",None),("analysis_result","")]:
    if key not in st.session_state: st.session_state[key]=default
if "confirmed" not in st.session_state: st.session_state.confirmed=False
if "chat_messages" not in st.session_state: st.session_state.chat_messages=[]
system_prompt,prompt_err=load_system_prompt(); engine,engine_err=load_json_file(ENGINE_FILE); books,books_err=load_books()

st.title("☯️ TỬ VI ĐẨU SỐ")
st.caption("Quét hình ảnh bằng Python → kiểm tra dữ liệu → luận giải bằng AI. Ảnh không được gửi cho AI.")

with st.sidebar:
    st.subheader("Hệ thống")
    st.write("Gemini API:","✅" if API_KEY else "❌")
    st.write("Quét hình ảnh:","✅ Python/EasyOCR")
    st.write("Engine:","✅" if not engine_err else "❌")
    st.write("System Prompt:","✅" if not prompt_err else "❌")
    if st.button("🗑️ Xóa phiên", use_container_width=True):
        for k,v in [("processed_data",None),("chart_json",None),("validation",None),("analysis_result","")]: st.session_state[k]=v
        st.session_state.confirmed=False; st.session_state.chat_messages=[]; st.rerun()

# Khu vực 1: nhập và quét ảnh, hoàn toàn tách khỏi khu vực luận giải.
st.header("① Quét hình ảnh")
uploaded=st.file_uploader("Chọn ảnh lá số",type=["jpg","jpeg","png","webp"], key="chart_upload")
with st.expander("⚙️ Tùy chỉnh vùng quét", expanded=False):
    top=st.slider("Bỏ lề trên (%)",0,25,0); bottom=st.slider("Bỏ lề dưới (%)",0,25,3); side=st.slider("Bỏ lề trái/phải (%)",0,15,0); overlap=st.slider("Overlap (px)",5,60,15)

if uploaded:
    from PIL import Image
    image=Image.open(uploaded).convert("RGB")
    with st.expander("Xem ảnh gốc", expanded=False): st.image(image,use_container_width=True)
    if st.button("🔎 QUÉT HÌNH ẢNH", type="primary", use_container_width=True):
        crops=crop_12_cung(image,top,bottom,side,overlap)
        with st.spinner("Đang xử lý ảnh bằng Python/EasyOCR..."):
            normalized=normalize_processed_data(extract_chart_text(image,crops))
            st.session_state.processed_data=normalized
            st.session_state.validation=validate_chart(normalized)
            st.session_state.chart_json=build_chart_json(normalized)
            st.session_state.confirmed=False
        st.success("Đã quét xong. Kiểm tra bảng dữ liệu bên dưới trước khi luận giải.")

if st.session_state.processed_data:
    st.header("② Kết quả quét")
    v=st.session_state.validation or {"errors":[],"warnings":[]}
    if v["errors"]: st.error("Có lỗi cần kiểm tra: "+"; ".join(v["errors"][:5]))
    if v["warnings"]: st.warning(f"Có {len(v['warnings'])} cảnh báo OCR. Bạn có thể xem chi tiết trong mục kiểm tra.")
    chart=st.session_state.chart_json or {}
    cungs=chart.get("cungs", chart.get("palaces", {})) if isinstance(chart,dict) else {}
    st.metric("Số cung đã đọc", len(cungs) if isinstance(cungs,dict) else 0)
    with st.expander("📋 Xem dữ liệu OCR đã chuẩn hóa", expanded=False):
        st.json(chart)
    with st.expander("🔍 Xem cảnh báo/chi tiết OCR", expanded=False):
        if v["errors"]:
            st.markdown("**Lỗi:**"); [st.write("• "+x) for x in v["errors"]]
        if v["warnings"]:
            st.markdown("**Cảnh báo:**"); [st.write("• "+x) for x in v["warnings"]]
    st.session_state.confirmed=st.checkbox("Tôi đã kiểm tra và xác nhận dữ liệu quét",value=st.session_state.confirmed)

# Khu vực 3: luận giải độc lập, không bị thay đổi bởi việc hiển thị OCR.
st.divider()
st.header("③ Luận giải")
with st.container(border=True):
    col1,col2=st.columns([1,3])
    with col1: year=st.number_input("Năm luận",1950,2050,2026)
    with col2: note=st.text_input("Yêu cầu bổ sung", "Luận giải dựa nghiêm ngặt trên dữ liệu đã xác nhận.")
    can_analyze=st.session_state.confirmed and bool(st.session_state.chart_json)
    if not can_analyze: st.info("Hãy quét hình ảnh → kiểm tra → xác nhận dữ liệu trước khi luận giải.")
    if can_analyze and st.button("🔮 BẮT ĐẦU LUẬN GIẢI",type="primary",use_container_width=True):
        if prompt_err or engine_err or books_err: st.error("Thiếu dữ liệu engine/prompt/books.")
        elif not API_KEY: st.error("Thiếu GEMINI_API_KEY.")
        else:
            with st.spinner("Python tính dữ liệu → AI áp dụng System Prompt → diễn giải..."):
                calc=calculate_chart(st.session_state.chart_json)
                st.session_state.analysis_result=generate_analysis(st.session_state.chart_json,calc,system_prompt,engine,books,year,note)

if st.session_state.analysis_result:
    st.header("④ Kết quả luận giải")
    with st.container(border=True):
        render_analysis(st.session_state.analysis_result)
        st.download_button("⬇️ Tải kết quả JSON",st.session_state.analysis_result,"analysis.json","application/json")

st.divider()
st.header("⑤ Hỏi đáp")
for m in st.session_state.chat_messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])
q=st.chat_input("Hỏi về bài luận giải...")
if q and st.session_state.analysis_result:
    chat_system=system_prompt+"\n\nBỔ SUNG: Khi trả lời chat, tiếp tục tuân thủ toàn bộ system prompt; chỉ dùng dữ liệu luận giải đã tạo và không nhìn ảnh."
    r=get_gemini_client(API_KEY).models.generate_content(model="gemini-3.6-flash",contents=f"DỮ LIỆU LUẬN GIẢI:\n{st.session_state.analysis_result}\n\nCÂU HỎI: {q}",config=gemini_config(chat_system,temperature=0.2,max_output_tokens=10000))
    ans=getattr(r,"text",""); st.session_state.chat_messages += [{"role":"user","content":q},{"role":"assistant","content":ans}]; st.rerun()
