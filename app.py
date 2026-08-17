#!/usr/bin/env python3
import os
import json
import streamlit as st
from pathlib import Path
from datetime import datetime
from PIL import Image
from github import Github, GithubException
from google import genai
from google.genai import types

# Cấu hình trang
st.set_page_config(page_title="Tử Vi Đẩu Số Engine", layout="wide")

# Hàm nạp tài nguyên (caching)
@st.cache_data(ttl=3600)
def load_file(filename):
    path = Path(__file__).parent / filename
    if not path.exists(): return None, f"Không thấy file {filename}"
    try:
        if filename.endswith('.json'):
            with open(path, 'r', encoding='utf-8') as f: return json.load(f), None
        with open(path, 'r', encoding='utf-8') as f: return f.read().strip(), None
    except Exception as e: return None, str(e)

# Logic xử lý chính
def main():
    st.markdown("<h1 style='text-align: center; color: #f6d365;'>☯️ TỬ VI ĐẨU SỐ ENGINE</h1>", unsafe_allow_html=True)
    
    # Nạp dữ liệu
    sys_prompt, _ = load_file("system_prompt.txt")
    engine_data, _ = load_file("tu_vi_engine.json")
    
    # Sidebar
    api_key = st.secrets.get("GEMINI_API_KEY")
    
    # Tabs
    tab1, tab2 = st.tabs(["Luận Giải", "Cấu Hình"])
    
    with tab1:
        uploaded_file = st.file_uploader("Tải lá số", type=["jpg", "png"])
        if uploaded_file and api_key:
            if st.button("Bắt đầu luận giải"):
                try:
                    client = genai.Client(api_key=api_key)
                    # Payload dữ liệu
                    engine_context = json.dumps(engine_data, ensure_ascii=False) if engine_data else ""
                    
                    response = client.models.generate_content(
                        model="gemini-2.0-flash", # Đảm bảo dùng model khả dụng
                        contents=[f"System: {sys_prompt}\nRules: {engine_context}", Image.open(uploaded_file)],
                    )
                    st.markdown(response.text)
                except Exception as e:
                    st.error(f"Lỗi: {e}")

if __name__ == "__main__":
    main()
