#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tử Vi Đẩu Số - Python OCR -> structured data -> Gemini.

IMPORTANT: Gemini never receives the original chart image or cropped images.
It receives only JSON/text produced by ocr_engine.py.
"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st
from github import Github, GithubException
from google import genai
from google.genai import types

from ocr_engine import crop_12_cung, extract_chart_text

st.set_page_config(page_title="Tử Vi Đẩu Số - Python OCR", page_icon="☯️", layout="wide")

BASE_DIR = Path(__file__).resolve().parent
ENGINE_FILE = BASE_DIR / "tu_vi_engine.json"
BOOKS_FILE = BASE_DIR / "books_cache.json"
PROMPT_DIR = BASE_DIR / "system_prompts"


def get_secret(name: str, default: str = "") -> str:
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return str(os.environ.get(name, default) or "")


API_KEY = get_secret("GEMINI_API_KEY")
GITHUB_TOKEN = get_secret("GITHUB_TOKEN")
GITHUB_REPO = get_secret("GITHUB_REPO")


@st.cache_resource
def get_gemini_client(api_key: str):
    if not api_key:
        raise ValueError("Chưa cấu hình GEMINI_API_KEY.")
    return genai.Client(api_key=api_key)


@st.cache_data(ttl=3600)
def load_system_prompt():
    files = sorted(PROMPT_DIR.glob("*.txt"), key=lambda p: p.name.lower()) if PROMPT_DIR.exists() else []
    if not files:
        return "Bạn là chuyên gia Tử Vi Đẩu Số cao cấp.", None
    parts = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8").strip()
            if text:
                parts.append(f"===== SYSTEM PROMPT: {path.name} =====\n{text}")
        except Exception as exc:
            return "", f"Lỗi đọc {path.name}: {exc}"
    return "\n\n".join(parts), None


@st.cache_data(ttl=3600)
def load_json_file(path: Path):
    if not path.exists():
        return None, f"Không tìm thấy {path.name}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, f"{path.name} không hợp lệ: {exc}"


def compact_json(data, limit):
    text = json.dumps(data, ensure_ascii=False, indent=2) if not isinstance(data, str) else data
    return text if len(text) <= limit else text[:limit] + "\n...[cắt theo giới hạn]..."


@st.cache_data(ttl=3600)
def load_books():
    data, err = load_json_file(BOOKS_FILE)
    if err:
        return "", err
    return compact_json(data, 100000), None


def upload_to_github(uploaded_file):
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False, "Thiếu GITHUB_TOKEN hoặc GITHUB_REPO."
    try:
        repo = Github(GITHUB_TOKEN).get_repo(GITHUB_REPO)
        ext = Path(uploaded_file.name).suffix.lower() or ".png"
        name = f"laso_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}{ext}"
        path = f"uploaded_laso/{name}"
        repo.create_file(path=path, message=f"Upload lá số: {name}", content=uploaded_file.getvalue())
        return True, f"https://github.com/{GITHUB_REPO}/blob/main/{path}"
    except GithubException as exc:
        return False, f"GitHub API lỗi: {exc}"
    except Exception as exc:
        return False, str(exc)


def build_analysis_prompt(system_prompt, engine_data, books_text, processed_data, selected_year, user_note):
    return f"""
BẠN LUẬN GIẢI LÁ SỐ TỬ VI ĐẨU SỐ.

NĂM XÉT: {selected_year}
YÊU CẦU NGƯỜI DÙNG: {user_note}

============================================================
DỮ LIỆU LÁ SỐ ĐÃ ĐƯỢC PYTHON OCR XỬ LÝ
============================================================
{compact_json(processed_data, 120000)}

QUY TẮC BẮT BUỘC:
- Dữ liệu hình ảnh đã được xử lý hoàn toàn bằng Python/EasyOCR trước khi gọi Gemini.
- Gemini KHÔNG được nhận ảnh, bytes ảnh, crop ảnh hoặc yêu cầu tự nhìn ảnh.
- Chỉ được sử dụng dữ liệu OCR ở trên, tu_vi_engine.json, system prompt và kho sách.
- Không được tự bịa dữ liệu bị OCR thiếu.
- Nếu OCR thiếu hoặc mâu thuẫn, ghi rõ "chưa đủ dữ liệu OCR".
- Có thể sửa lỗi OCR hiển nhiên dựa trên ngữ cảnh Tử Vi nhưng phải giữ tính thận trọng.
- Phân biệt bản cung, tam hợp, xung chiếu, nhị hợp, giáp cung, Tuần/Triệt.
- Không kết luận chỉ từ một sao.
- Không tạo câu phú giả; chỉ trích dẫn nguồn có trong kho sách.

============================================================
SYSTEM PROMPT
============================================================
{system_prompt}

============================================================
TU_VI_ENGINE.JSON
============================================================
{compact_json(engine_data, 120000)}

============================================================
BOOKS_CACHE.JSON
============================================================
{books_text}

============================================================
YÊU CẦU ĐẦU RA
============================================================
I. Kiểm tra dữ liệu OCR và chỉ ra điểm thiếu/không chắc.
II. Tổng quan Mệnh - Thân - Mệnh Cục.
III. Luận 12 cung dựa trên dữ liệu đã xử lý.
IV. Trục Mệnh - Tài - Quan và các trục quan trọng.
V. Đại vận.
VI. Tiểu hạn/Lưu niên {selected_year}.
VII. 10 kết luận quan trọng nhất.

Ưu tiên tính nhất quán và căn cứ dữ liệu hơn độ dài.
"""


def generate_analysis(processed_data, system_prompt, engine_data, books_text, selected_year, user_note):
    client = get_gemini_client(API_KEY)
    prompt = build_analysis_prompt(system_prompt, engine_data, books_text, processed_data, selected_year, user_note)
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=30000),
    )
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini không trả về nội dung.")
    return text


def ask_chat(question, selected_year, system_prompt, engine_data):
    client = get_gemini_client(API_KEY)
    analysis = st.session_state.get("analysis_result", "Chưa có bài luận giải.")
    history = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in st.session_state.chat_messages[-12:])
    prompt = f"""{system_prompt}

Bạn chỉ được trả lời dựa trên bài luận giải và dữ liệu đã OCR trước đó.
Không được nhìn ảnh và không được suy đoán dữ liệu ảnh chưa có.
Năm: {selected_year}

BÀI LUẬN GIẢI:
{analysis}

LỊCH SỬ CHAT:
{history}

CÂU HỎI:
{question}
"""
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.25, max_output_tokens=12000),
    )
    answer = getattr(response, "text", None)
    if not answer:
        raise RuntimeError("Gemini không trả về câu trả lời.")
    return answer


if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = ""
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "processed_data" not in st.session_state:
    st.session_state.processed_data = None

system_prompt, prompt_err = load_system_prompt()
engine_data, engine_err = load_json_file(ENGINE_FILE)
books_text, books_err = load_books()

st.markdown("# ☯️ TỬ VI ĐẨU SỐ — PYTHON OCR")
st.caption("Ảnh → Python/EasyOCR → JSON/text đã xử lý → Gemini. Gemini không nhận ảnh.")

with st.sidebar:
    st.subheader("Trạng thái")
    st.write("Gemini API:", "✅" if API_KEY else "❌")
    st.write("Python OCR:", "✅ EasyOCR")
    st.write("Engine:", "✅" if not engine_err else "❌")
    st.write("System prompt:", "✅" if not prompt_err else "❌")
    st.write("Books:", "✅" if not books_err else "❌")
    save_to_github = st.checkbox("☁️ Lưu ảnh lên GitHub", value=False)
    if st.button("🗑️ Xóa dữ liệu"):
        st.session_state.analysis_result = ""
        st.session_state.chat_messages = []
        st.session_state.processed_data = None
        st.rerun()

left, right = st.columns([1, 1], gap="large")

with left:
    uploaded = st.file_uploader("📸 Tải ảnh lá số", type=["jpg", "jpeg", "png", "webp"])
    selected_year = st.number_input("📅 Năm luận", min_value=1950, max_value=2050, value=2026)
    user_note = st.text_area("📝 Yêu cầu thêm", value="Luận giải dựa nghiêm ngặt trên dữ liệu OCR đã xử lý.", height=80)

    top = st.slider("Bỏ lề trên (%)", 0, 25, 0)
    bottom = st.slider("Bỏ lề dưới (%)", 0, 25, 3)
    side = st.slider("Bỏ lề trái/phải (%)", 0, 15, 0)
    overlap = st.slider("Overlap (px)", 5, 60, 15)

    if uploaded:
        from PIL import Image
        try:
            image = Image.open(uploaded).convert("RGB")
            st.image(image, caption="Ảnh gốc — chỉ xử lý local", use_container_width=True)
            crops = crop_12_cung(image, top, bottom, side, overlap)
            with st.expander("Xem 12 vùng cắt"):
                cols = st.columns(3)
                for i, (name, crop) in enumerate(crops.items()):
                    cols[i % 3].image(crop, caption=name, use_container_width=True)

            if st.button("🔍 PYTHON QUÉT OCR", use_container_width=True):
                with st.spinner("Python đang xử lý ảnh và OCR 12 cung..."):
                    st.session_state.processed_data = extract_chart_text(image, crops)
                st.success("Đã OCR xong. Gemini chưa được gọi.")

            if st.session_state.processed_data:
                st.json(st.session_state.processed_data)

            if save_to_github and st.button("☁️ Lưu ảnh lên GitHub"):
                ok, msg = upload_to_github(uploaded)
                st.success(msg) if ok else st.warning(msg)

            analyze = st.button("🔮 BẮT ĐẦU LUẬN GIẢI", type="primary", use_container_width=True)
        except Exception as exc:
            st.error(f"Không đọc được ảnh: {exc}")
            analyze = False
    else:
        analyze = False

with right:
    st.subheader("📜 BÀI LUẬN GIẢI")
    if st.session_state.analysis_result:
        st.markdown(st.session_state.analysis_result)
        st.download_button("⬇️ Tải TXT", st.session_state.analysis_result, "luan_giai_tu_vi.txt", "text/plain")
    else:
        st.info("Hãy tải ảnh → bấm PYTHON QUÉT OCR → kiểm tra dữ liệu → BẮT ĐẦU LUẬN GIẢI.")

if analyze:
    if not API_KEY:
        st.error("Chưa cấu hình GEMINI_API_KEY.")
    elif not st.session_state.processed_data:
        st.warning("Hãy chạy PYTHON QUÉT OCR trước. Gemini chỉ được phép nhận dữ liệu đã xử lý.")
    elif prompt_err or engine_err or books_err:
        st.error("Dữ liệu hệ thống chưa đầy đủ.")
    else:
        with st.spinner("Gemini đang luận giải từ dữ liệu OCR đã xử lý..."):
            try:
                st.session_state.analysis_result = generate_analysis(
                    st.session_state.processed_data,
                    system_prompt,
                    engine_data,
                    books_text,
                    selected_year,
                    user_note,
                )
                st.rerun()
            except Exception as exc:
                st.error(f"Lỗi luận giải: {exc}")

st.markdown("### 💬 Hỏi đáp")
for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

question = st.chat_input("Hỏi về lá số đã OCR...")
if question:
    if not API_KEY:
        st.error("Chưa cấu hình GEMINI_API_KEY.")
    elif not st.session_state.analysis_result:
        st.warning("Chưa có bài luận giải.")
    else:
        st.session_state.chat_messages.append({"role": "user", "content": question})
        try:
            answer = ask_chat(question, selected_year, system_prompt, engine_data)
            st.session_state.chat_messages.append({"role": "assistant", "content": answer})
        except Exception as exc:
            st.error(f"Lỗi chat: {exc}")
        st.rerun()
