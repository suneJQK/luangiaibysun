#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import io
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import easyocr
import numpy as np
import streamlit as st
from PIL import Image
from github import Github, GithubException
from google import genai
from google.genai import types
from google.genai.errors import APIError


# ============================================================
# TẢI MODEL OCR (CACHED)
# ============================================================

@st.cache_resource
def load_ocr_reader():
    """Khởi tạo EasyOCR reader một lần duy nhất để tối ưu hiệu năng."""
    return easyocr.Reader(["vi", "en"], gpu=False)


reader = load_ocr_reader()


# ============================================================
# CẤU HÌNH STREAMLIT
# ============================================================

st.set_page_config(
    page_title="Tử Vi Đẩu Số - Luận Giải Tự Động Engine",
    page_icon="☯️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    button[data-testid="stSidebarCollapseButton"],
    button[data-testid="baseButton-header"],
    div[data-testid="stSidebarNav"] button,
    [data-testid="collapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        z-index: 999999 !important;
    }

    [data-testid="collapsedControl"] {
        top: 0.5rem !important;
        left: 0.5rem !important;
    }

    .stApp {
        background-color: #0e1117;
    }

    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #f6d365;
        text-align: center;
        margin-bottom: 0.5rem;
        text-shadow: 0px 0px 10px rgba(246, 211, 101, 0.2);
    }

    div.stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #d4af37 0%, #f6d365 100%);
        color: #1a202c;
        font-weight: bold;
        border: none;
        border-radius: 8px;
        transition: all 0.3s ease;
    }

    div.stButton > button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(246, 211, 101, 0.4);
    }

    .analysis-header-title {
        font-size: 1.3rem;
        font-weight: 700;
        color: #f6d365;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 10px;
        border-bottom: 1px solid #30363d;
        padding-bottom: 10px;
    }

    .scrollable-result-content {
        color: #e6edf3;
        font-size: 1rem;
        line-height: 1.6;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SECRETS / ĐƯỜNG DẪN (ĐÃ CẬP NHẬT AN TOÀN)
# ============================================================

def get_secret(name: str, default: str = "") -> str:
    """
    Đọc secret an toàn, không bị bẫy lỗi StreamlitSecretNotFoundError 
    khi chạy ở môi trường Codespaces / Local chưa tạo secrets.toml.
    """
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return str(os.environ.get(name, default) or "")


API_KEY = get_secret("GEMINI_API_KEY")
GITHUB_TOKEN = get_secret("GITHUB_TOKEN")
GITHUB_REPO = get_secret("GITHUB_REPO")

BASE_DIR = Path(__file__).resolve().parent
ENGINE_FILE = BASE_DIR / "tu_vi_engine.json"
BOOKS_FILE = BASE_DIR / "books_cache.json"
PROMPT_DIR = BASE_DIR / "system_prompts"


# ============================================================
# SESSION STATE
# ============================================================

DEFAULTS = {
    "analysis_result": "",
    "chat_messages": [],
    "current_image_bytes": None,
    "current_image_name": "",
    "cropped_dict": {},
    "extracted_data": {},
    "last_uploaded": "",
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# GEMINI
# ============================================================

@st.cache_resource
def get_gemini_client(api_key: str):
    if not api_key:
        raise ValueError("Chưa cấu hình GEMINI_API_KEY.")
    return genai.Client(api_key=api_key)


# ============================================================
# ĐỌC DỮ LIỆU
# ============================================================

@st.cache_data(ttl=3600)
def load_system_prompt():
    """Đọc TẤT CẢ .txt trong system_prompts theo thứ tự tên file."""
    if not PROMPT_DIR.exists():
        return (
            "Bạn là chuyên gia Tử Vi Đẩu Số cao cấp.",
            f"Không tìm thấy thư mục {PROMPT_DIR.name}",
        )

    txt_files = sorted(PROMPT_DIR.glob("*.txt"), key=lambda p: p.name.lower())

    if not txt_files:
        return (
            "Bạn là chuyên gia Tử Vi Đẩu Số cao cấp.",
            "Thư mục system_prompts trống.",
        )

    sections = []

    for target_file in txt_files:
        try:
            content = target_file.read_text(encoding="utf-8").strip()
            if content:
                sections.append(
                    f"\n===== SYSTEM PROMPT: {target_file.name} =====\n"
                    f"{content}"
                )
        except Exception as exc:
            return "", f"Lỗi đọc file {target_file.name}: {exc}"

    if not sections:
        return (
            "Bạn là chuyên gia Tử Vi Đẩu Số cao cấp.",
            "Không có nội dung hợp lệ trong system_prompts.",
        )

    return "\n\n".join(sections), None


@st.cache_data(ttl=3600)
def load_engine_rules():
    if not ENGINE_FILE.exists():
        return None, f"Không tìm thấy file quy tắc: {ENGINE_FILE.name}"

    try:
        data = json.loads(ENGINE_FILE.read_text(encoding="utf-8"))
        return data, None
    except json.JSONDecodeError as exc:
        return None, f"{ENGINE_FILE.name} không phải JSON hợp lệ: {exc}"
    except Exception as exc:
        return None, f"Lỗi đọc {ENGINE_FILE.name}: {exc}"


@st.cache_data(ttl=3600)
def load_books_reference():
    if not BOOKS_FILE.exists():
        return None, f"Không tìm thấy file tham khảo: {BOOKS_FILE.name}"

    try:
        data = json.loads(BOOKS_FILE.read_text(encoding="utf-8"))

        if isinstance(data, list):
            text = "\n\n".join(str(item) for item in data)
        elif isinstance(data, dict):
            text = json.dumps(data, ensure_ascii=False, indent=2)
        else:
            text = str(data)

        return text, None

    except json.JSONDecodeError as exc:
        return None, f"{BOOKS_FILE.name} không phải JSON hợp lệ: {exc}"
    except Exception as exc:
        return None, f"Lỗi đọc {BOOKS_FILE.name}: {exc}"


def compact_json(data, max_chars=120000):
    if not data:
        return ""

    try:
        text = json.dumps(data, ensure_ascii=False, indent=2)
    except Exception:
        text = str(data)

    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "\n...[ĐÃ CẮT BỚT DO GIỚI HẠN KÍCH THƯỚC]..."


def compact_text(text, max_chars=120000):
    if not text:
        return ""

    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "\n...[ĐÃ CẮT BỚT DO GIỚI HẠN KÍCH THƯỚC]..."


# ============================================================
# GITHUB - TÙY CHỌN
# ============================================================

def upload_to_github(uploaded_file):
    """Lưu ảnh lên GitHub nếu người dùng chủ động bật tính năng."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False, "Thiếu GITHUB_TOKEN hoặc GITHUB_REPO trong Secrets."

    try:
        github_client = Github(GITHUB_TOKEN)
        repo = github_client.get_repo(GITHUB_REPO)

        ext = Path(uploaded_file.name).suffix.lower() or ".png"
        unique_name = f"laso_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
        file_path = f"uploaded_laso/{unique_name}"

        file_content = uploaded_file.getvalue()
        commit_message = f"Upload lá số: {unique_name}"

        repo.create_file(
            path=file_path,
            message=commit_message,
            content=file_content,
        )

        return True, f"https://github.com/{GITHUB_REPO}/blob/main/{file_path}"

    except GithubException as exc:
        return False, f"GitHub API lỗi: {exc}"
    except Exception as exc:
        return False, str(exc)


# ============================================================
# XỬ LÝ ẢNH & OCR (PYTHON TỰ XỬ LÝ)
# ============================================================

GRID_MAP = {
    "Hợi": (3, 3),
    "Tý": (2, 3),
    "Sửu": (1, 3),
    "Dần": (0, 3),
    "Mão": (0, 2),
    "Thìn": (0, 1),
    "Tị": (0, 0),
    "Ngọ": (1, 0),
    "Mùi": (2, 0),
    "Thân": (3, 0),
    "Dậu": (3, 1),
    "Tuất": (3, 2),
}


def crop_12_cung_overlap(
    img: Image.Image,
    top_cut=0,
    bottom_cut=3,
    side_cut=0,
    overlap_px=15,
):
    """Cắt bố cục 4x4 thành 12 ô địa chi."""
    if img is None:
        return {}

    width, height = img.size

    left_start = width * (side_cut / 100.0)
    right_end = width * (1.0 - side_cut / 100.0)
    top_start = height * (top_cut / 100.0)
    bottom_end = height * (1.0 - bottom_cut / 100.0)

    effective_width = max(1, right_end - left_start)
    effective_height = max(1, bottom_end - top_start)

    w_step = effective_width / 4.0
    h_step = effective_height / 4.0

    cropped_cungs = {}

    for cung_name, (col, row) in GRID_MAP.items():
        left = max(0, int(left_start + col * w_step - overlap_px))
        top = max(0, int(top_start + row * h_step - overlap_px))
        right = min(width, int(left_start + (col + 1) * w_step + overlap_px))
        bottom = min(height, int(top_start + (row + 1) * h_step + overlap_px))

        if right > left and bottom > top:
            cropped_cungs[cung_name] = img.crop((left, top, right, bottom))

    return cropped_cungs


def extract_text_from_cungs(cropped_dict):
    """Python dùng EasyOCR bóc tách chữ từ 12 mảnh cắt."""
    extracted_data = {}
    for cung_name, crop_img in cropped_dict.items():
        img_np = np.array(crop_img)
        text_list = reader.readtext(img_np, detail=0)
        extracted_data[cung_name] = text_list
    return extracted_data


def uploaded_file_to_image(uploaded_file):
    try:
        image = Image.open(uploaded_file)
        image.load()
        return image.convert("RGB"), None
    except Exception as exc:
        return None, f"Không thể đọc ảnh: {exc}"


# ============================================================
# PROMPT LUẬN GIẢI (CHỈ DÙNG DỮ LIỆU TEXT)
# ============================================================

def build_analysis_prompt(
    extracted_data,
    system_prompt,
    engine_data,
    books_text,
    selected_year,
    user_note,
):
    engine_text = compact_json(engine_data, 120000)
    books_reference = compact_text(books_text, 100000)
    ocr_json_text = json.dumps(extracted_data, ensure_ascii=False, indent=2)

    return f"""
BẠN ĐANG THỰC HIỆN LUẬN GIẢI MỘT LÁ SỐ TỬ VI ĐẨU SỐ DỰA TRÊN DỮ LIỆU VĂN BẢN (OCR) ĐÃ ĐƯỢC PYTHON BÓC TÁCH.

NĂM CẦN LUẬN TIỂU HẠN/LƯU NIÊN:
{selected_year}

YÊU CẦU THÊM CỦA NGƯỜI DÙNG:
{user_note}

============================================================
DỮ LIỆU CÁC CUNG ĐÃ BÓC TÁCH TỪ PYTHON (OCR TEXT):
============================================================
{ocr_json_text}

============================================================
SYSTEM PROMPT / BỘ QUY TẮC LUẬN GIẢI
============================================================
{system_prompt}

============================================================
TU_VI_ENGINE.JSON
============================================================
{engine_text}

============================================================
BOOKS_CACHE.JSON - KHO SÁCH / CÂU PHÚ THAM KHẢO
============================================================
{books_reference}

============================================================
NGUYÊN TẮC XỬ LÝ DỮ LIỆU OCR
============================================================

1. Phân tích hoàn toàn dựa vào dữ liệu chữ đã trích xuất từ 12 cung.
2. Nếu OCR có lỗi chính tả nhỏ, hãy tự điều chỉnh đúng tên sao dựa trên ngữ cảnh Tử Vi.
3. Phân biệt chính tinh, phụ tinh, sát tinh, bại tinh, cát tinh và Tứ Hóa.
4. Xác định đúng Mệnh, Thân và 12 cung.
5. Khi xét một cung phải kiểm tra: Bản cung, Tam hợp, Xung chiếu, Nhị hợp, Giáp cung, Tuần/Triệt, các sao hội chiếu.
6. Không được gọi nhầm xung chiếu thành tam hợp hoặc ngược lại.
7. Khi luận đại vận/tiểu vận/lưu niên phải phân biệt rõ từng tầng hạn.
8. Không được kết luận chỉ dựa vào một sao đơn lẻ.
9. Nếu dữ liệu OCR thiếu thông tin ở cung nào, ghi rõ "chưa đủ dữ liệu OCR" thay vì tự suy đoán.
10. Trích dẫn câu phú đúng nguồn nếu dữ liệu sách có cung cấp.

============================================================
CẤU TRÚC BÀI LUẬN GIẢI
============================================================

Hãy tạo một bài luận giải có hệ thống, không rời rạc:

I. KIỂM TRA VÀ TRÍCH XUẤT DỮ LIỆU LÁ SỐ
- Ngày giờ sinh (nếu OCR quét được).
- Mệnh, Thân và vị trí 12 cung.
- Các sao chính tinh/phụ tinh nổi bật bóc tách được.

II. TỔNG QUAN MỆNH CỤC
- Mệnh và Thân.
- Ngũ hành bản mệnh và cục.
- Thế đứng chính tinh và các cách cục nổi bật.

III. LUẬN 12 CUNG
Với từng cung: Chính tinh, Phụ tinh, Sát tinh, Tứ Hóa, Tam hợp, Xung chiếu, Nhị hợp, Giáp cung, Tuần/Triệt, Kết luận.

IV. CÁC TRỤC QUAN TRỌNG
- Mệnh – Tài – Quan.
- Phúc – Phụ – Điền.
- Phu Thê, Tử Tức, Thiên Di, Tật Ách, Nô Bộc, Huynh Đệ.

V. ĐẠI VẬN
- Cung đại vận, các sao và đánh giá cát/hung.

VI. TIỂU HẠN / LƯU NIÊN {selected_year}
- Tác động lên Mệnh/Thân, Tài, Quan, Phu, Tật...
- Các điểm cần thận trọng và tận dụng.

VII. KẾT LUẬN
- 10 điểm quan trọng nhất.
"""


def generate_analysis(
    extracted_data: dict,
    system_prompt,
    engine_data,
    books_text,
    selected_year,
    user_note,
):
    client = get_gemini_client(API_KEY)

    prompt = build_analysis_prompt(
        extracted_data=extracted_data,
        system_prompt=system_prompt,
        engine_data=engine_data,
        books_text=books_text,
        selected_year=selected_year,
        user_note=user_note,
    )

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=30000,
        ),
    )

    text = getattr(response, "text", None)

    if not text:
        raise RuntimeError(
            "Gemini không trả về nội dung. Hãy kiểm tra API key hoặc dữ liệu văn bản."
        )

    return text


# ============================================================
# CHAT
# ============================================================

def build_chat_instruction(
    main_system_prompt,
    engine_data,
    analysis_context,
    selected_year,
):
    engine_text = compact_json(engine_data, 80000)
    analysis_text = compact_text(analysis_context, 100000)

    return f"""{main_system_prompt}

Bạn đang tiếp tục hội thoại về chính lá số đã được phân tích.

NĂM ĐANG XÉT:{selected_year}

BÀI LUẬN GIẢI GỐC:
--- START ANALYSIS ---{analysis_text}
--- END ANALYSIS ---

BỘ QUY TẮC CỐT LÕI:
--- START ENGINE ---{engine_text}
--- END ENGINE ---

QUY TẮC TRẢ LỜI:
- Trả lời trực tiếp câu hỏi.
- Không mâu thuẫn với dữ liệu lá số đã phân tích.
- Nếu câu hỏi yêu cầu tính đại vận/tiểu vận/lưu niên, phải phân biệt từng tầng hạn.
- Khi người dùng yêu cầu giải thích, hãy chỉ rõ căn cứ: bản cung, tam hợp, xung chiếu, nhị hợp, giáp cung, Tuần/Triệt, sao và hạn liên quan.
"""


def ask_chat(question, selected_year, main_system_prompt, engine_data):
    client = get_gemini_client(API_KEY)

    analysis_context = st.session_state.get(
        "analysis_result",
        "Chưa có bài luận giải chi tiết.",
    )

    instruction = build_chat_instruction(
        main_system_prompt=main_system_prompt,
        engine_data=engine_data,
        analysis_context=analysis_context,
        selected_year=selected_year,
    )

    history_parts = []

    for message in st.session_state.chat_messages[-12:]:
        role = message.get("role", "user")
        content = message.get("content", "")
        history_parts.append(f"{role.upper()}: {content}")

    conversation = "\n\n".join(history_parts)

    full_prompt = f"""{instruction}

LỊCH SỬ HỘI THOẠI:{conversation}

CÂU HỎI MỚI:{question}
"""

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=full_prompt,
        config=types.GenerateContentConfig(
            temperature=0.25,
            max_output_tokens=12000,
        ),
    )

    answer = getattr(response, "text", None)

    if not answer:
        raise RuntimeError("Gemini không trả về câu trả lời.")

    return answer


# ============================================================
# LOAD DỮ LIỆU
# ============================================================

main_system_prompt, prompt_err = load_system_prompt()
engine_data, engine_err = load_engine_rules()
books_text, books_err = load_books_reference()


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-header">☯️ TỬ VI ĐẨU SỐ LUẬN GIẢI TỰ ĐỘNG (PYTHON OCR)</div>',
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.image(
        "https://img.icons8.com/color/96/yin-yang.png",
        width=64,
    )

    st.title("⚙️ Thông Tin Hệ Thống")

    if API_KEY:
        st.caption("✅ Gemini API: **Đã cấu hình**")
    else:
        st.caption("❌ Gemini API: **Chưa cấu hình KEY**")

    if prompt_err:
        st.warning(f"System Prompt: {prompt_err}")
    else:
        st.caption("📜 System Prompt: **Đã nạp**")

    if engine_err:
        st.warning(f"Engine: {engine_err}")
    else:
        st.caption("📜 Quy tắc chính: **Đã nạp**")

    if books_err:
        st.warning(f"Books: {books_err}")
    else:
        st.caption("📚 Kho tham khảo: **Đã nạp**")

    st.divider()

    save_to_github = st.checkbox(
        "☁️ Lưu ảnh lá số lên GitHub",
        value=False,
    )

    if st.button("🗑️ Xóa bài luận & hội thoại"):
        st.session_state.analysis_result = ""
        st.session_state.chat_messages = []
        st.session_state.current_image_bytes = None
        st.session_state.current_image_name = ""
        st.session_state.cropped_dict = {}
        st.session_state.extracted_data = {}
        st.rerun()


# ============================================================
# GIAO DIỆN CHÍNH
# ============================================================

col_input, col_output = st.columns([1, 1], gap="large")


# ============================================================
# CỘT INPUT & CHAT (BÊN TRÁI)
# ============================================================

with col_input:

    with st.expander(
        "📸 TẢI LÊN & QUÉT DỮ LIỆU LÁ SỐ",
        expanded=True,
    ):
        uploaded_file = st.file_uploader(
            "Tải lên ảnh lá số:",
            type=["jpg", "jpeg", "png", "webp"],
        )

        selected_year = st.number_input(
            "📅 Năm luận Tiểu Hạn / Lưu Niên:",
            min_value=1950,
            max_value=2050,
            value=2026,
            step=1,
        )

        user_note = st.text_area(
            "📝 Ghi chú / Yêu cầu thêm:",
            value=(
                "Yêu cầu AI áp dụng nghiêm ngặt quy tắc trong "
                "tu_vi_engine.json và sử dụng câu phú từ kho sách "
                "khi dữ liệu thực sự có căn cứ."
            ),
            height=80,
        )

        top_val = 0
        bottom_val = 3
        side_val = 0
        overlap_val = 15

        if uploaded_file:
            raw_bytes = uploaded_file.getvalue()

            if (
                st.session_state.current_image_name != uploaded_file.name
                or st.session_state.current_image_bytes != raw_bytes
            ):
                st.session_state.current_image_name = uploaded_file.name
                st.session_state.current_image_bytes = raw_bytes
                st.session_state.extracted_data = {}

            if save_to_github and st.session_state.get("last_uploaded") != uploaded_file.name:
                with st.spinner("☁️ Đang lưu bản sao lên GitHub..."):
                    gh_success, gh_msg = upload_to_github(uploaded_file)

                if gh_success:
                    st.success("✅ Đã lưu ảnh lên GitHub.")
                    st.caption(gh_msg)
                else:
                    st.warning(f"⚠️ Không lưu được GitHub: {gh_msg}")

                st.session_state.last_uploaded = uploaded_file.name

            image, image_error = uploaded_file_to_image(uploaded_file)

            if image_error:
                st.error(image_error)
            else:
                st.session_state.current_image = image

                with st.expander(
                    "🛠️ Căn chỉnh lề & Vùng phủ đường biên",
                    expanded=False,
                ):
                    top_val = st.slider("⬆️ Bỏ lề TRÊN (%):", 0, 25, 0, 1)
                    bottom_val = st.slider("⬇️ Bỏ lề DƯỚI (%):", 0, 25, 3, 1)
                    side_val = st.slider("↔️ Bỏ lề TRÁI/PHẢI (%):", 0, 15, 0, 1)
                    overlap_val = st.slider("🔍 Vùng phủ đường biên (Px):", 5, 60, 15, 1)

                st.image(
                    image,
                    caption="Lá số đã tải lên",
                    use_container_width=True,
                )

                cropped_dict = crop_12_cung_overlap(
                    image,
                    top_cut=top_val,
                    bottom_cut=bottom_val,
                    side_cut=side_val,
                    overlap_px=overlap_val,
                )

                st.session_state.cropped_dict = cropped_dict

                if st.button("🔍 Python Tự Quét Văn Bản (OCR 12 Cung)", use_container_width=True):
                    with st.spinner("🐍 Python đang bóc tách chữ từ 12 cung..."):
                        extracted = extract_text_from_cungs(cropped_dict)
                        st.session_state.extracted_data = extracted
                        st.success("✅ Python đã bóc tách dữ liệu văn bản thành công!")

        if st.session_state.extracted_data:
            with st.expander("📄 Dữ liệu Text Python quét được từ 12 Cung", expanded=False):
                st.json(st.session_state.extracted_data)

        analyze_clicked = st.button(
            "🔮 BẮT ĐẦU LUẬN GIẢI (GỬI DỮ LIỆU TEXT)",
            type="primary",
            use_container_width=True,
        )

    # --------------------------------------------------------
    # KHUNG CHAT BÊN TRÁI
    # --------------------------------------------------------
    st.markdown(
        '<div class="analysis-header-title" style="margin-top: 15px;">💬 TRÒ CHUYỆN & HỎI ĐÁP VỚI AI</div>',
        unsafe_allow_html=True,
    )

    chat_container = st.container(height=450)

    with chat_container:
        if not st.session_state.chat_messages:
            st.info("Chưa có tin nhắn nào. Bạn có thể hỏi bất kỳ câu nào về lá số dưới đây.")
        else:
            for msg in st.session_state.chat_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])


# ============================================================
# CỘT OUTPUT (BÀI LUẬN GIẢI BÊN PHẢI)
# ============================================================

with col_output:

    st.markdown(
        '<div class="analysis-header-title">📜 BÀI LUẬN GIẢI</div>',
        unsafe_allow_html=True,
    )

    analysis_result = st.session_state.get("analysis_result", "")

    if analysis_result:
        with st.container(height=700):
            st.markdown(
                f'<div class="scrollable-result-content">{analysis_result}</div>',
                unsafe_allow_html=True,
            )

        st.download_button(
            "⬇️ Tải bài luận giải (.txt)",
            data=analysis_result,
            file_name="luan_giai_tu_vi.txt",
            mime="text/plain",
            use_container_width=True,
        )
    else:
        st.info(
            "Chưa có bài luận giải. Hãy tải ảnh lá số, nhấn **Python Tự Quét Văn Bản** rồi bấm **BẮT ĐẦU LUẬN GIẢI**."
        )


# ============================================================
# XỬ LÝ SỰ KIỆN NÚT BẮT ĐẦU LUẬN GIẢI
# ============================================================

if analyze_clicked:
    if not API_KEY:
        st.error("❌ Chưa cấu hình GEMINI_API_KEY.")
    elif not uploaded_file:
        st.warning("⚠️ Hãy tải ảnh lá số trước.")
    elif prompt_err:
        st.error(f"❌ System Prompt lỗi: {prompt_err}")
    elif engine_err:
        st.error(f"❌ Engine lỗi: {engine_err}")
    else:
        if not st.session_state.extracted_data:
            with st.spinner("🐍 Python đang bóc tách chữ từ 12 cung..."):
                st.session_state.extracted_data = extract_text_from_cungs(
                    st.session_state.cropped_dict
                )

        with st.spinner("🔮 Gemini đang đọc dữ liệu văn bản và thực hiện luận giải..."):
            try:
                result = generate_analysis(
                    extracted_data=st.session_state.extracted_data,
                    system_prompt=main_system_prompt,
                    engine_data=engine_data,
                    books_text=books_text,
                    selected_year=selected_year,
                    user_note=user_note,
                )

                st.session_state.analysis_result = result
                st.session_state.chat_messages = []
                st.success("✅ Đã hoàn thành bài luận giải.")
                st.rerun()

            except APIError as exc:
                if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                    st.error("⚠️ Hạn ngạch API đã vượt quá giới hạn (429 Resource Exhausted). Vui lòng thử lại sau vài phút.")
                else:
                    st.error(f"❌ Lỗi Gemini API: {exc}")
            except Exception as exc:
                st.error(f"❌ Không thể hoàn thành luận giải.\n\nChi tiết: {exc}")


# ============================================================
# Ô NHẬP TIN NHẮN (ST.CHAT_INPUT)
# ============================================================

user_question = st.chat_input(
    "Nhập câu hỏi về lá số (Ví dụ: Hạn năm 2026 cần lưu ý gì?)..."
)

if user_question:
    if not API_KEY:
        st.error("❌ Chưa cấu hình GEMINI_API_KEY.")
    else:
        st.session_state.chat_messages.append(
            {
                "role": "user",
                "content": user_question,
            }
        )

        try:
            answer = ask_chat(
                question=user_question,
                selected_year=selected_year,
                main_system_prompt=main_system_prompt,
                engine_data=engine_data,
            )

            st.session_state.chat_messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                }
            )
            st.rerun()

        except APIError as exc:
            if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                error_message = "⚠️ Hạn ngạch gọi API đã hết (429 Resource Exhausted). Hãy đợi ít phút rồi gửi lại câu hỏi."
            else:
                error_message = f"❌ Lỗi Gemini API: {exc}"

            st.session_state.chat_messages.append(
                {
                    "role": "assistant",
                    "content": error_message,
                }
            )
            st.rerun()
        except Exception as exc:
            error_message = f"❌ Lỗi khi hỏi Gemini: {exc}"
            st.session_state.chat_messages.append(
                {
                    "role": "assistant",
                    "content": error_message,
                }
            )
            st.rerun()
