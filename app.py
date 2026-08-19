#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import io
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st
from PIL import Image
from github import Github, GithubException
from google import genai
from google.genai import types
from google.genai.errors import APIError


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

    /* Khung cuộn độc lập cho kết quả luận giải */
    div[data-testid="stVerticalBlock"]:has(> div.scrollable-anchor) {
        max-height: 75vh;
        overflow-y: auto;
        padding: 15px;
        border: 1px solid #30363d;
        border-radius: 10px;
        background-color: #161b22;
    }

    div[data-testid="stVerticalBlock"]:has(> div.scrollable-anchor)::-webkit-scrollbar {
        width: 8px;
    }
    div[data-testid="stVerticalBlock"]:has(> div.scrollable-anchor)::-webkit-scrollbar-track {
        background: #0d1117;
        border-radius: 8px;
    }
    div[data-testid="stVerticalBlock"]:has(> div.scrollable-anchor)::-webkit-scrollbar-thumb {
        background: #30363d;
        border-radius: 8px;
    }
    div[data-testid="stVerticalBlock"]:has(> div.scrollable-anchor)::-webkit-scrollbar-thumb:hover {
        background: #d4af37;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SECRETS / ĐƯỜNG DẪN
# ============================================================

def get_secret(name: str, default: str = "") -> str:
    """Đọc secret từ Streamlit Secrets trước, sau đó mới đến biến môi trường."""
    try:
        value = st.secrets.get(name)
    except Exception:
        value = None
    return str(value or os.environ.get(name, default) or "")


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
    """
    Lưu ảnh lên GitHub nếu người dùng chủ động bật tính năng.
    Dùng UUID để tránh trùng tên khi upload nhiều lần trong cùng một giây.
    """
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
# XỬ LÝ ẢNH / CẮT 12 CUNG
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
    """
    Cắt bố cục 4x4, trong đó 12 ô ngoài là 12 địa chi.
    Giữ vùng overlap để tránh mất chữ nằm trên đường biên.
    """
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


def image_to_bytes(image: Image.Image, fmt="PNG") -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def uploaded_file_to_image(uploaded_file):
    try:
        image = Image.open(uploaded_file)
        image.load()
        return image.convert("RGB"), None
    except Exception as exc:
        return None, f"Không thể đọc ảnh: {exc}"


# ============================================================
# PROMPT LUẬN GIẢI
# ============================================================

def build_analysis_prompt(
    system_prompt,
    engine_data,
    books_text,
    selected_year,
    user_note,
):
    engine_text = compact_json(engine_data, 120000)
    books_reference = compact_text(books_text, 100000)

    return f"""
BẠN ĐANG THỰC HIỆN LUẬN GIẢI MỘT LÁ SỐ TỬ VI ĐẨU SỐ.

NĂM CẦN LUẬN TIỂU HẠN/LƯU NIÊN:
{selected_year}

YÊU CẦU THÊM CỦA NGƯỜI DÙNG:
{user_note}

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
NGUYÊN TẮC XỬ LÝ ẢNH
============================================================

1. Đọc toàn bộ lá số trước khi kết luận.
2. Không được suy đoán vị trí sao nếu ảnh không đủ rõ.
3. Phân biệt chính tinh, phụ tinh, sát tinh, bại tinh, cát tinh và Tứ Hóa.
4. Xác định đúng Mệnh, Thân và 12 cung.
5. Khi xét một cung phải kiểm tra:
   - Bản cung.
   - Tam hợp.
   - Xung chiếu.
   - Nhị hợp nếu hệ quy tắc yêu cầu.
   - Giáp cung.
   - Tuần/Triệt.
   - Các sao hội chiếu.
6. Không được gọi nhầm xung chiếu thành tam hợp hoặc ngược lại.
7. Khi luận đại vận/tiểu vận/lưu niên phải phân biệt rõ từng tầng hạn.
8. Không được kết luận chỉ dựa vào một sao đơn lẻ.
9. Các kết luận quan trọng phải tổng hợp từ nhiều yếu tố.
10. Nếu dữ liệu trên ảnh không đủ để xác nhận một điểm, phải nói rõ "chưa đủ dữ liệu để xác nhận" thay vì tự bịa.
11. Khi sử dụng câu phú hoặc lý thuyết từ BOOKS_CACHE.JSON, phải trích dẫn tên sách/tác giả và câu phú nếu dữ liệu cung cấp đủ thông tin.
12. Không được tạo câu phú giả rồi gán cho cổ thư.

============================================================
CẤU TRÚC BÀI LUẬN GIẢI
============================================================

Hãy tạo một bài luận giải có hệ thống, không rời rạc:

I. KIỂM TRA VÀ TRÍCH XUẤT DỮ LIỆU LÁ SỐ
- Ngày giờ sinh nếu đọc được.
- Âm/dương, mệnh/cục nếu đọc được.
- Mệnh chủ, Thân chủ nếu đọc được.
- Mệnh, Thân.
- 12 cung.
- Chính tinh/phụ tinh/sát tinh quan trọng.

II. TỔNG QUAN MỆNH CỤC
- Mệnh và Thân.
- Ngũ hành bản mệnh và cục.
- Quan hệ Mệnh-Cục nếu xác định được.
- Thế đứng chính tinh.
- Các cách cục nổi bật.

III. LUẬN 12 CUNG
Với từng cung:
- Chính tinh.
- Phụ tinh.
- Sát tinh.
- Tứ Hóa.
- Tam hợp.
- Xung chiếu.
- Nhị hợp.
- Giáp cung.
- Tuần/Triệt.
- Kết luận riêng của cung.

IV. CÁC TRỤC QUAN TRỌNG
- Mệnh – Tài – Quan.
- Phúc – Phụ – Điền.
- Phu Thê.
- Tử Tức.
- Thiên Di.
- Tật Ách.
- Nô Bộc.
- Huynh Đệ.
- Các trục có ảnh hưởng mạnh.

V. ĐẠI VẬN
- Xác định đại vận.
- Sao trong đại vận.
- Cung đại vận.
- Quan hệ đại vận với nguyên cục.
- Cát/hung.
- Các mốc đáng chú ý.

VI. TIỂU HẠN / LƯU NIÊN {selected_year}
- Tiểu hạn.
- Lưu Thái Tuế.
- Lưu tinh nếu đọc được.
- Tác động lên Mệnh/Thân.
- Tác động lên Tài, Quan, Phu, Tật, Điền...
- Tháng/nửa đầu/nửa cuối năm nếu dữ liệu cho phép.
- Điểm cần thận trọng.
- Điểm có thể tận dụng.

VII. KẾT LUẬN
- 10 điểm quan trọng nhất.
- Cát/hung theo từng lĩnh vực.
- Những điều cần kiểm chứng nếu dữ liệu ảnh chưa đủ.

Hãy ưu tiên tính nhất quán và kiểm tra chéo hơn là viết dài.
"""


def generate_analysis(
    image: Image.Image,
    cropped_dict: dict,
    system_prompt,
    engine_data,
    books_text,
    selected_year,
    user_note,
):
    client = get_gemini_client(API_KEY)

    prompt = build_analysis_prompt(
        system_prompt=system_prompt,
        engine_data=engine_data,
        books_text=books_text,
        selected_year=selected_year,
        user_note=user_note,
    )

    image_bytes = image_to_bytes(image, "PNG")

    contents = [
        types.Part.from_text(text=prompt),
        types.Part.from_bytes(
            data=image_bytes,
            mime_type="image/png",
        ),
    ]

    # Gửi kèm 12 mảnh cắt giúp AI nhận diện chi tiết chữ nhỏ/mờ
    if cropped_dict:
        contents.append(types.Part.from_text(text="\n\nCHI TIẾT MẢNH CẮT 12 CUNG:\n"))
        for name, crop_img in cropped_dict.items():
            contents.append(types.Part.from_text(text=f"Mảnh cắt Cung {name}:"))
            crop_bytes = image_to_bytes(crop_img, "PNG")
            contents.append(types.Part.from_bytes(data=crop_bytes, mime_type="image/png"))

    response = client.models.generate_content(
        model="gemini-3.6-flash",  # Sử dụng model gemini-3.6-flash
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=30000,
        ),
    )

    text = getattr(response, "text", None)

    if not text:
        raise RuntimeError(
            "Gemini không trả về nội dung. Hãy kiểm tra API key, model và ảnh."
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
- Nếu cần dữ liệu chưa có trong bài luận giải hoặc ảnh, nói rõ thiếu dữ liệu.
- Không tự tạo câu phú hoặc nguồn sách.
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

    # Giới hạn lịch sử để tránh prompt phình quá lớn.
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
        model="gemini-3.6-flash",  # Sử dụng model gemini-3.6-flash
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
    '<div class="main-header">☯️ TỬ VI ĐẨU SỐ LUẬN GIẢI TỰ ĐỘNG</div>',
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
        help=(
            "Tắt mặc định để tránh tự động lưu ảnh cá nhân. "
            "Chỉ bật nếu repository của bạn phù hợp với việc lưu dữ liệu này."
        ),
    )

    if st.button("🗑️ Xóa bài luận & hội thoại"):
        st.session_state.analysis_result = ""
        st.session_state.chat_messages = []
        st.session_state.current_image_bytes = None
        st.session_state.current_image_name = ""
        st.session_state.cropped_dict = {}
        st.rerun()


# ============================================================
# GIAO DIỆN CHÍNH
# ============================================================

col_input, col_output = st.columns([1, 1], gap="large")


# ============================================================
# CỘT INPUT
# ============================================================

with col_input:

    with st.expander(
        "📸 TẢI LÊN & CẤU HÌNH LÁ SỐ",
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
            height=100,
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
                    top_val = st.slider(
                        "⬆️ Bỏ lề TRÊN (%):",
                        0,
                        25,
                        0,
                        1,
                    )

                    bottom_val = st.slider(
                        "⬇️ Bỏ lề DƯỚI (%):",
                        0,
                        25,
                        3,
                        1,
                    )

                    side_val = st.slider(
                        "↔️ Bỏ lề TRÁI/PHẢI (%):",
                        0,
                        15,
                        0,
                        1,
                    )

                    overlap_val = st.slider(
                        "🔍 Vùng phủ đường biên (Px):",
                        5,
                        60,
                        15,
                        1,
                    )

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

                with st.expander("🔍 Xem mảnh cắt 12 Cung", expanded=False):
                    crop_cols = st.columns(3)

                    for idx, (name, crop_img) in enumerate(
                        cropped_dict.items()
                    ):
                        crop_cols[idx % 3].image(
                            crop_img,
                            caption=f"Cung {name}",
                            use_container_width=True,
                        )

        analyze_clicked = st.button(
            "🔮 BẮT ĐẦU LUẬN GIẢI",
            type="primary",
            use_container_width=True,
        )


# ============================================================
# XỬ LÝ LUẬN GIẢI
# ============================================================

if analyze_clicked:
    if not API_KEY:
        st.error(
            "❌ Chưa cấu hình GEMINI_API_KEY. "
            "Hãy thêm key vào Streamlit Secrets hoặc biến môi trường."
        )
    elif not uploaded_file:
        st.warning("⚠️ Hãy tải ảnh lá số trước.")
    elif prompt_err:
        st.error(f"❌ System Prompt lỗi: {prompt_err}")
    elif engine_err:
        st.error(f"❌ Engine lỗi: {engine_err}")
    else:
        image = st.session_state.get("current_image")

        if image is None:
            image, image_error = uploaded_file_to_image(uploaded_file)

            if image_error:
                st.error(image_error)
                image = None

        if image is not None:
            with st.spinner(
                "🔮 Gemini đang đọc lá số và thực hiện luận giải..."
            ):
                try:
                    result = generate_analysis(
                        image=image,
                        cropped_dict=st.session_state.get("cropped_dict", {}),
                        system_prompt=main_system_prompt,
                        engine_data=engine_data,
                        books_text=books_text,
                        selected_year=selected_year,
                        user_note=user_note,
                    )

                    st.session_state.analysis_result = result

                    # Reset chat khi tạo một bài luận giải mới.
                    st.session_state.chat_messages = []

                    st.success("✅ Đã hoàn thành bài luận giải.")
                    st.rerun()

                except APIError as exc:
                    if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                        st.error("⚠️ Hạn ngạch API đã vượt quá giới hạn (429 Resource Exhausted). Vui lòng thử lại sau vài phút hoặc kiểm tra lại API key.")
                    else:
                        st.error(f"❌ Lỗi Gemini API: {exc}")
                except Exception as exc:
                    st.error(
                        "❌ Không thể hoàn thành luận giải.\n\n"
                        f"Chi tiết: {exc}"
                    )


# ============================================================
# CỘT OUTPUT
# ============================================================

with col_output:

    st.markdown(
        '<div class="analysis-header-title">📜 BÀI LUẬN GIẢI</div>',
        unsafe_allow_html=True,
    )

    analysis_result = st.session_state.get("analysis_result", "")

    if analysis_result:
        analysis_container = st.container()
        with analysis_container:
            st.markdown('<div class="scrollable-anchor"></div>', unsafe_allow_html=True)
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
            "Chưa có bài luận giải. "
            "Hãy tải ảnh lá số và bấm **BẮT ĐẦU LUẬN GIẢI**."
        )


# ============================================================
# CHAT HỎI ĐÁP
# ============================================================

st.divider()

st.markdown(
    '<div class="analysis-header-title">💬 TRÒ CHUYỆN & HỎI ĐÁP VỚI AI</div>',
    unsafe_allow_html=True,
)

for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

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

        with st.chat_message("user"):
            st.markdown(user_question)

        with st.chat_message("assistant"):
            with st.spinner("🔮 AI đang suy luận câu trả lời..."):
                try:
                    answer = ask_chat(
                        question=user_question,
                        selected_year=selected_year,
                        main_system_prompt=main_system_prompt,
                        engine_data=engine_data,
                    )

                    st.markdown(answer)

                    st.session_state.chat_messages.append(
                        {
                            "role": "assistant",
                            "content": answer,
                        }
                    )

                except APIError as exc:
                    if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                        error_message = "⚠️ Hạn ngạch gọi API đã hết (429 Resource Exhausted). Hãy đợi ít phút rồi gửi lại câu hỏi."
                    else:
                        error_message = f"❌ Lỗi Gemini API: {exc}"
                    st.error(error_message)
                    st.session_state.chat_messages.append(
                        {
                            "role": "assistant",
                            "content": error_message,
                        }
                    )
                except Exception as exc:
                    error_message = f"❌ Lỗi khi hỏi Gemini: {exc}"
                    st.error(error_message)

                    st.session_state.chat_messages.append(
                        {
                            "role": "assistant",
                            "content": error_message,
                        }
                    )
