#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tử Vi: local Python OCR -> normalized/validated Chart JSON -> Gemini."""
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

st.set_page_config(page_title="Tử Vi Đẩu Số - Python OCR", page_icon="☯️", layout="wide")
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
        text="\n\n".join(p.read_text(encoding="utf-8").strip() for p in files if p.read_text(encoding="utf-8").strip())
        if not text: return "", "System prompt rỗng."
        return text,None
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
    return f"""Năm luận: {year}\nYêu cầu bổ sung của người dùng: {note}\n\nDỮ LIỆU ĐÃ ĐƯỢC PYTHON XỬ LÝ VÀ XÁC NHẬN\nCHART JSON:\n{compact(chart,100000)}\n\nCALCULATION JSON:\n{compact(calc,80000)}\n\nENGINE:\n{compact(engine,100000)}\n\nBOOKS:\n{books}\n\nHãy tuân thủ toàn bộ SYSTEM INSTRUCTION được cung cấp ở cấp system. Chỉ sử dụng các dữ liệu trên. Nếu thiếu dữ liệu, ghi rõ. Trả JSON đúng schema. Không kết luận từ một sao đơn lẻ. Không tạo trích dẫn sách không có trong BOOKS."""
def gemini_config(system_prompt, **kwargs):
    return types.GenerateContentConfig(system_instruction=system_prompt, **kwargs)
def generate_analysis(chart,calc,system,engine,books,year,note):
    r=get_gemini_client(API_KEY).models.generate_content(model="gemini-3.6-flash",contents=make_prompt(engine,books,chart,calc,year,note),config=gemini_config(system,temperature=0.15,max_output_tokens=30000,response_mime_type="application/json",response_schema=SCHEMA))
    return getattr(r,"text","")
def render_analysis(raw):
    try:
        d=json.loads(raw); st.markdown("### Tổng quan\n"+d.get("tong_quan",""))
        for x in d.get("luan_12_cung",[]):
            with st.expander(x.get("cung","Cung")): st.write(x.get("ket_luan","")); st.caption("Căn cứ: "+"; ".join(x.get("can_cu",[])))
        st.markdown("### Kết luận")
        for x in d.get("ket_luan",[]): st.write("- "+x)
        if d.get("canh_bao"): st.warning("\n".join(d["canh_bao"]))
    except Exception: st.markdown(raw)
for key,default in [("processed_data",None),("chart_json",None),("validation",None),("analysis_result","")]:
    if key not in st.session_state: st.session_state[key]=default
if "confirmed" not in st.session_state: st.session_state.confirmed=False
if "chat_messages" not in st.session_state: st.session_state.chat_messages=[]
system_prompt,prompt_err=load_system_prompt(); engine,engine_err=load_json_file(ENGINE_FILE); books,books_err=load_books()
st.title("☯️ TỬ VI ĐẨU SỐ — PYTHON OCR → ENGINE → GEMINI"); st.caption("Ảnh chỉ xử lý local. Gemini chỉ nhận Chart JSON đã xác nhận.")
with st.sidebar:
    st.write("Gemini API:","✅" if API_KEY else "❌"); st.write("OCR Python:","✅ EasyOCR"); st.write("Engine:","✅" if not engine_err else "❌"); st.write("System Prompt:","✅" if not prompt_err else "❌")
    if st.button("🗑️ Xóa phiên"):
        st.session_state.processed_data=None; st.session_state.chart_json=None; st.session_state.validation=None; st.session_state.analysis_result=""; st.session_state.confirmed=False; st.session_state.chat_messages=[]; st.rerun()
left,right=st.columns([1,1],gap="large")
with left:
    uploaded=st.file_uploader("📸 Tải ảnh lá số",type=["jpg","jpeg","png","webp"]); year=st.number_input("📅 Năm luận",1950,2050,2026); note=st.text_area("📝 Yêu cầu","Luận giải dựa nghiêm ngặt trên dữ liệu đã xác nhận.")
    top=st.slider("Bỏ lề trên (%)",0,25,0); bottom=st.slider("Bỏ lề dưới (%)",0,25,3); side=st.slider("Bỏ lề trái/phải (%)",0,15,0); overlap=st.slider("Overlap (px)",5,60,15)
    if uploaded:
        from PIL import Image
        image=Image.open(uploaded).convert("RGB"); st.image(image,use_container_width=True,caption="Ảnh gốc — không gửi Gemini"); crops=crop_12_cung(image,top,bottom,side,overlap)
        with st.expander("12 vùng cắt"):
            cols=st.columns(3)
            for i,(name,crop) in enumerate(crops.items()): cols[i%3].image(crop,caption=name,use_container_width=True)
        if st.button("🔍 1. PYTHON OCR",use_container_width=True):
            with st.spinner("Python/EasyOCR đang xử lý..."):
                normalized=normalize_processed_data(extract_chart_text(image,crops)); st.session_state.processed_data=normalized; st.session_state.validation=validate_chart(normalized); st.session_state.chart_json=build_chart_json(normalized); st.session_state.confirmed=False
            st.success("OCR + chuẩn hóa xong; Gemini chưa được gọi.")
        if st.session_state.processed_data:
            v=st.session_state.validation
            if v["errors"]: st.error("\n".join(v["errors"]))
            if v["warnings"]: st.warning("\n".join(v["warnings"][:20]))
            st.json(st.session_state.chart_json); st.session_state.confirmed=st.checkbox("✅ Tôi đã kiểm tra và xác nhận dữ liệu OCR",value=st.session_state.confirmed)
        if st.session_state.confirmed and st.button("🔮 2. LUẬN GIẢI",type="primary",use_container_width=True):
            if prompt_err or engine_err or books_err: st.error("Thiếu dữ liệu engine/prompt/books.")
            elif not API_KEY: st.error("Thiếu GEMINI_API_KEY.")
            else:
                with st.spinner("Python tính dữ liệu → Gemini áp dụng System Prompt → diễn giải..."):
                    calc=calculate_chart(st.session_state.chart_json); st.session_state.analysis_result=generate_analysis(st.session_state.chart_json,calc,system_prompt,engine,books,year,note)
        if st.checkbox("☁️ Lưu ảnh lên GitHub",False) and st.button("Lưu ảnh"):
            ok,msg=upload_to_github(uploaded); st.success(msg) if ok else st.warning(msg)
with right:
    st.subheader("📜 KẾT QUẢ")
    if st.session_state.analysis_result: render_analysis(st.session_state.analysis_result); st.download_button("⬇️ Tải JSON",st.session_state.analysis_result,"analysis.json","application/json")
    else: st.info("OCR → kiểm tra → xác nhận → luận giải")
st.markdown("### 💬 Hỏi đáp")
for m in st.session_state.chat_messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])
q=st.chat_input("Hỏi về dữ liệu đã xác nhận...")
if q and st.session_state.analysis_result:
    chat_system=(system_prompt+"\n\nBỔ SUNG: Khi trả lời chat, vẫn phải tuân thủ toàn bộ hệ thống trên; chỉ dùng dữ liệu luận giải đã tạo và không nhìn ảnh.")
    r=get_gemini_client(API_KEY).models.generate_content(model="gemini-3.6-flash",contents=f"DỮ LIỆU LUẬN GIẢI ĐÃ TẠO:\n{st.session_state.analysis_result}\n\nCÂU HỎI: {q}",config=gemini_config(chat_system,temperature=0.2,max_output_tokens=10000)); ans=getattr(r,"text",""); st.session_state.chat_messages += [{"role":"user","content":q},{"role":"assistant","content":ans}]; st.rerun()
