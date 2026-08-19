#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tử Vi: image -> position-aware Python OCR -> clean chart -> Gemini."""
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
        if name in st.secrets:return str(st.secrets[name])
    except Exception:pass
    return os.environ.get(name,"") or ""
API_KEY=secret("GEMINI_API_KEY")
@st.cache_resource
def get_client(key):
    if not key:raise ValueError("Thiếu GEMINI_API_KEY")
    return genai.Client(api_key=key)
@st.cache_data(ttl=3600)
def load_json(path):
    try:return json.loads(path.read_text(encoding="utf-8")),None
    except Exception as e:return None,str(e)
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
    prompt=f"""Năm luận: {year}\nYêu cầu: {note}\n\nDỮ LIỆU LÁ SỐ ĐÃ CHUẨN HÓA BỞI PYTHON (nguồn duy nhất về vị trí và sao):\n{compact(chart,50000)}\n\nDỮ LIỆU QUAN HỆ TÍNH BỞI PYTHON:\n{compact(calc,20000)}\n\nENGINE KIẾN THỨC:\n{compact(engine,70000)}\n\nTÀI LIỆU:\n{compact(books,50000)}\n\nQUY TẮC DỮ LIỆU: Chỉ sử dụng các trường có trong JSON sạch. Không nhìn ảnh, không sử dụng raw OCR, không tự thêm sao, không biến số tuổi thành sao. 93 trong dai_van.tuoi_bat_dau là tuổi bắt đầu Đại vận. Th.2 là lưu nguyệt tháng 2. ĐV.X là cung Đại vận; LN.X là cung Lưu niên; Tuần/Triệt là trạng thái của cung; vong_truong_sinh là vòng Trường Sinh; can + địa chi + ngũ hành là vị trí của cung. Luận đủ các chính tinh, phụ tinh, tứ hóa và sát tinh đã được liệt kê."""
    system=system_prompt+"\n\nBẮT BUỘC: dữ liệu đầu vào đã được Python lọc; tuyệt đối không suy đoán sao không có trong JSON."
    cfg=types.GenerateContentConfig(system_instruction=system,temperature=0.15,max_output_tokens=30000,response_mime_type="application/json",response_schema=SCHEMA)
    return get_client(API_KEY).models.generate_content(model="gemini-3.6-flash",contents=prompt,config=cfg).text

def render(raw):
    try:
        d=json.loads(raw);st.markdown("### Tổng quan\n"+d.get("tong_quan",""))
        for x in d.get("luan_12_cung",[]):
            with st.expander(x.get("cung","Cung")):st.markdown(x.get("ket_luan",""));st.caption("Căn cứ: "+"; ".join(x.get("can_cu",[])))
        for title,key in [("Đại vận","dai_van"),("Tiểu hạn","tieu_han")]:
            with st.expander(title):
                for x in d.get(key,[]):st.write("• "+x)
        st.markdown("### Kết luận")
        for x in d.get("ket_luan",[]):st.write("• "+x)
        if d.get("canh_bao"):
            with st.expander("⚠️ Cảnh báo"):
                for x in d["canh_bao"]:st.warning(x)
    except Exception:st.markdown(raw)

for k,v in [("chart_json",None),("normalized",None),("validation",None),("analysis_result","")]:st.session_state.setdefault(k,v)
st.session_state.setdefault("confirmed",False)

st.title("☯️ TỬ VI ĐẨU SỐ")
st.caption("Quét hình ảnh bằng Python → phân tích vị trí từng ô → chuẩn hóa 12 cung → AI chỉ nhận JSON sạch.")
st.header("① Quét hình ảnh")
uploaded=st.file_uploader("Chọn ảnh lá số",type=["jpg","jpeg","png","webp"])
with st.expander("⚙️ Tùy chỉnh vùng quét"):
    top=st.slider("Bỏ lề trên (%)",0,25,0);bottom=st.slider("Bỏ lề dưới (%)",0,25,3);side=st.slider("Bỏ lề trái/phải (%)",0,15,0);overlap=st.slider("Overlap (px)",5,60,20)
if uploaded:
    from PIL import Image
    image=Image.open(uploaded).convert("RGB")
    with st.expander("Xem ảnh gốc"):st.image(image,use_container_width=True)
    if st.button("🔎 QUÉT HÌNH ẢNH",type="primary",use_container_width=True):
        try:
            with st.spinner("Python đang đọc vị trí, sao và các hạn trong 12 cung..."):
                cropped=crop_12_cung(image,top,bottom,side,overlap)
                raw=extract_chart_text(image,cropped)
                normalized=normalize_processed_data(raw)
                chart=build_chart_json(normalized)
                if not isinstance(chart,dict) or not isinstance(chart.get("12_cung"),dict):
                    raise ValueError("Bộ chuẩn hóa OCR không tạo được bảng 12 cung hợp lệ.")
                st.session_state.normalized=normalized
                st.session_state.chart_json=chart
                st.session_state.validation=validate_chart(normalized)
                st.session_state.confirmed=False
            st.success("Đã quét và chuẩn hóa dữ liệu. Ảnh không được gửi cho AI.")
        except Exception as exc:
            st.session_state.chart_json=None
            st.session_state.normalized=None
            st.error(f"Không thể hoàn tất bước quét/chuẩn hóa OCR: {type(exc).__name__}: {exc}")
            st.info("Bản sửa mới đã thêm lớp bảo vệ để lỗi parser không làm treo toàn bộ ứng dụng. Hãy chờ Streamlit Cloud deploy commit mới rồi quét lại.")

if st.session_state.chart_json:
    st.header("② Bảng 12 cung sạch")
    chart=st.session_state.chart_json;rows=[]
    for name,data in chart.get("12_cung",{}).items():
        main="; ".join(x.get("ten","")+(f" ({x['trang_thai']})" if x.get("trang_thai") else "") for x in data.get("chinh_tinh",[])) or "—"
        sup="; ".join(data.get("phu_tinh",[])) or "—"
        periods=[]
        if data.get("dai_van"):periods.append("ĐV "+json.dumps(data["dai_van"],ensure_ascii=False))
        if data.get("tieu_van"):periods.append("TV "+json.dumps(data["tieu_van"],ensure_ascii=False))
        if data.get("luu_nien"):periods.append("LN "+json.dumps(data["luu_nien"],ensure_ascii=False))
        if data.get("luu_nguyet"):periods.append("Th "+str(data["luu_nguyet"].get("thang")))
        flags=("Tuần " if data.get("tuan") else "")+("Triệt" if data.get("triet") else "")
        rows.append({"Cung":name,"Can":data.get("can","—"),"Địa chi":data.get("dia_chi","—"),"Hành":(("+" if data.get("am_duong")=="Dương" else "-") if data.get("am_duong") else "")+(data.get("ngu_hanh") or "—"),"Trường sinh":data.get("vong_truong_sinh","—"),"Tuần/Triệt":flags or "—","Chính tinh":main,"Phụ tinh":sup,"Hạn": " | ".join(periods) or "—"})
    if rows:st.dataframe(rows,use_container_width=True,hide_index=True)
    with st.expander("Xem JSON sạch gửi cho AI"):st.json(chart)
    if st.session_state.normalized and st.session_state.normalized.get("review"):
        with st.expander("🔍 OCR cần kiểm tra (không gửi AI)"):st.dataframe(st.session_state.normalized["review"],use_container_width=True,hide_index=True)
    v=st.session_state.validation or {"errors":[],"warnings":[]}
    if v.get("errors"):st.error("; ".join(v["errors"][:5]))
    if v.get("warnings"):st.warning(f"Có {len(v['warnings'])} cảnh báo cần kiểm tra.")
    st.session_state.confirmed=st.checkbox("☑ Tôi đã kiểm tra bảng 12 cung",value=st.session_state.confirmed)

st.divider();st.header("③ Luận giải")
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
    st.header("④ Kết quả luận giải");render(st.session_state.analysis_result)
    st.download_button("⬇️ Tải JSON",st.session_state.analysis_result,"analysis.json","application/json")
