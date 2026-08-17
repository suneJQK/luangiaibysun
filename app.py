#!/usr/bin/env python3
import os
import json
import time
from pathlib import Path
from datetime import datetime
import streamlit as st
from PIL import Image
from github import Github, GithubException
from google import genai
from google.genai import types

# --- 1. CẤU HÌNH TRANG STREAMLIT ---
st.set_page_config(
    page_title="Tử Vi Đẩu Số - Luận Giải Tự Động Engine",
    page_icon="☯️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- 2. TÙY CHỈNH GIAO DIỆN (CSS) ---
st.markdown(
    """
    <style>
    /* Nút đóng/mở Sidebar */
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
    
    .stApp { background-color: #0e1117; }
    
    /* Style tiêu đề chính */
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #f6d365;
        text-align: center;
        margin-bottom: 0.5rem;
        text-shadow: 0px 0px 10px rgba(246, 211, 101, 0.2);
    }
    
    /* Style nút bấm nổi bật */
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

    /* MỤC NỘI DUNG LUẬN GIẢI TRƯỢT RIÊNG BIỆT (SCROLLABLE CONTAINER) */
    .scrollable-interpretation-box {
        max-height: 520px;
        overflow-y: auto;
        padding: 18px;
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 10px;
        box-shadow: inset 0 0 10px rgba(0, 0, 0, 0.5);
        margin-bottom: 1rem;
    }
    
    /* Tùy chỉnh thanh cuộn đẹp mắt cho vùng trượt */
    .scrollable-interpretation-box::-webkit-scrollbar {
        width: 8px;
    }
    .scrollable-interpretation-box::-webkit-scrollbar-track {
        background: #0d1117;
        border-radius: 4px;
    }
    .scrollable-interpretation-box::-webkit-scrollbar-thumb {
        background: #d4af37;
        border-radius: 4px;
    }
    .scrollable-interpretation-box::-webkit-scrollbar-thumb:hover {
        background: #f6d365;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- 3. LẤY SECRETS & CẤU HÌNH ĐƯỜNG DẪN FILE ---
API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", os.environ.get("GITHUB_TOKEN", ""))
GITHUB_REPO = st.secrets.get("GITHUB_REPO", os.environ.get("GITHUB_REPO", ""))

BASE_DIR = Path(__file__).parent
ENGINE_FILE = BASE_DIR / "tu_vi_engine.json"
BOOKS_FILE = BASE_DIR / "books_cache.json"
PROMPT_FILE = BASE_DIR / "system_prompt.txt"

# --- 4. HÀM NẠP SYSTEM PROMPT TỪ FILE RIÊNG ---
@st.cache_data(ttl=3600)
def load_system_prompt():
    """Nạp file system_prompt.txt làm System Instruction cho AI"""
    if not PROMPT_FILE.exists():
        return "Bạn là chuyên gia Tử Vi Đẩu Số cao cấp. Hãy luận giải lá số dựa trên quy tắc được cung cấp.", f"Chưa có file {PROMPT_FILE.name}, đang dùng prompt mặc định."
    try:
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
        return content, None
    except Exception as e:
        return "", f"Lỗi đọc file {PROMPT_FILE.name}: {str(e)}"

# --- 5. HÀM NẠP NGẦM BỘ QUY TẮC CHÍNH (tu_vi_engine.json) ---
@st.cache_data(ttl=3600)
def load_engine_rules():
    """Nạp ngầm file tu_vi_engine.json"""
    if not ENGINE_FILE.exists():
        return None, f"Không tìm thấy file quy tắc: {ENGINE_FILE.name}"
    try:
        with open(ENGINE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data, None
    except Exception as e:
        return None, f"Lỗi cấu trúc file {ENGINE_FILE.name}: {str(e)}"

# --- 6. HÀM NẠP NGẦM KHO SÁCH THAM KHẢO (books_cache.json) ---
@st.cache_data(ttl=3600)
def load_books_reference():
    """Nạp ngầm file books_cache.json"""
    if not BOOKS_FILE.exists():
        return None, f"Không tìm thấy file tham khảo: {BOOKS_FILE.name}"
    try:
        with open(BOOKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return "\n\n".join([str(item) for item in data]), None
        elif isinstance(data, dict):
            return json.dumps(data, ensure_ascii=False, indent=2), None
        return str(data), None
    except Exception as e:
        return None, f"Lỗi đọc file {BOOKS_FILE.name}: {str(e)}"

# --- 7. HÀM LƯU ẢNH LÊN GITHUB ---
def upload_to_github(uploaded_file):
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False, "Thiếu 'GITHUB_TOKEN' hoặc 'GITHUB_REPO' trong Secrets."
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        ext = Path(uploaded_file.name).suffix
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = f"uploaded_laso/laso_{timestamp}{ext}"
        file_content = uploaded_file.getvalue()
        commit_message = f"Upload lá số mới: laso_{timestamp}{ext}"
        try:
            contents = repo.get_contents(file_path)
            repo.update_file(contents.path, commit_message, file_content, contents.sha)
        except GithubException:
            repo.create_file(file_path, commit_message, file_content)
        return True, f"https://github.com/{GITHUB_REPO}/blob/main/{file_path}"
    except Exception as e:
        return False, str(e)

# --- 8. HÀM CẮT 12 CUNG LÁ SỐ ---
def crop_12_cung_overlap(img, top_cut=0, bottom_cut=3, side_cut=0, overlap_px=15):
    width, height = img.size
    left_start = width * (side_cut / 100)
    right_end = width * (1 - side_cut / 100)
    top_start = height * (top_cut / 100)
    bottom_end = height * (1 - bottom_cut / 100)

    effective_width = right_end - left_start
    effective_height = bottom_end - top_start
    w_step = effective_width / 4
    h_step = effective_height / 4

    grid_map = {
        "Hợi": (3, 3), "Tý": (2, 3), "Sửu": (1, 3), "Dần": (0, 3),
        "Mão": (0, 2), "Thìn": (0, 1), "Tị": (0, 0), "Ngọ": (1, 0),
        "Mùi": (2, 0), "Thân": (3, 0), "Dậu": (3, 1), "Tuất": (3, 2),
    }

    cropped_cungs = {}
    for cung_name, (col, row) in grid_map.items():
        left = max(0, left_start + col * w_step - overlap_px)
        top = max(0, top_start + row * h_step - overlap_px)
        right = min(width, left_start + (col + 1) * w_step + overlap_px)
        bottom = min(height, top_start + (row + 1) * h_step + overlap_px)
        cropped_cungs[cung_name] = img.crop((left, top, right, bottom))
    return cropped_cungs

# --- 9. GIAO DIỆN CHÍNH & NẠP DỮ LIỆU ---
st.markdown('<div class="main-header">☯️ TỬ VI ĐẨU SỐ LUẬN GIẢI TỰ ĐỘNG</div>', unsafe_allow_html=True)

main_system_prompt, prompt_err = load_system_prompt()
engine_data, engine_err = load_engine_rules()
books_text, books_err = load_books_reference()

# --- 10. SIDEBAR ĐIỀU HƯỚNG ---
with st.sidebar:
    st.image("https://img.icons8.com/color/96/yin-yang.png", width=64)
    st.title("⚙️ Cấu Hình Luận Giải")
    selected_year = st.number_input("📅 Năm luận Tiểu Hạn:", 1950, 2050, 2026, 1)
    user_note = st.text_area(
        "📝 Ghi chú / Yêu cầu thêm:",
        value="Yêu cầu AI áp dụng nghiêm ngặt quy tắc Tử Vi và dẫn chứng thêm câu phú từ kho sách.",
        height=100,
    )
    btn_sidebar_analyze = st.button("🔮 BẮT ĐẦU LUẬN GIẢI", type="primary", key="btn_sidebar", use_container_width=True)
    
    st.markdown("---")
    st.subheader("🔌 Trạng Thái Dữ Liệu")
    
    if API_KEY:
        st.caption("✅ Gemini API: **Đã kết nối**")
    else:
        st.caption("❌ Gemini API: **Chưa cấu hình KEY**")

    # Chỉ thể hiện trạng thái của System Prompt (Đã ẩn trạng thái tu_vi_engine và books_cache)
    if not prompt_err:
        st.caption("📜 System Prompt: **`system_prompt.txt` (Đã nạp)**")
    else:
        st.caption(f"⚠️ System Prompt: **{prompt_err}**")

# --- 11. PHÂN CHIA TABS ---
tab_main, tab_sys_prompt, tab_contact = st.tabs([
    "🔮 Luận Giải Lá Số",
    "⚙️ System Prompt (system_prompt.txt)",
    "🔗 Liên Hệ & Hỗ Trợ"
])

# ==========================================
# TAB 1: LUẬN GIẢI LÁ SỐ
# ==========================================
with tab_main:
    col_input, col_output = st.columns([1, 1.3], gap="large")

    with col_input:
        st.subheader("📸 Upload & Căn Chỉnh Lá Số")
        uploaded_file = st.file_uploader("Tải lên ảnh lá số:", type=["jpg", "jpeg", "png", "webp"])
        cropped_dict = {}

        if uploaded_file:
            if st.session_state.get("last_uploaded") != uploaded_file.name:
                with st.spinner("🐙 Đang lưu bản sao lá số..."):
                    gh_success, gh_msg = upload_to_github(uploaded_file)
                    if gh_success:
                        st.toast("✅ Đã lưu lá số an toàn!", icon="✅")
                    st.session_state.last_uploaded = uploaded_file.name

            image = Image.open(uploaded_file).convert("RGB")

            with st.expander("🛠️ Căn chỉnh lề & Vạch ngăn Tuần/Triệt", expanded=False):
                top_val = st.slider("⬆️ Bỏ lề TRÊN (%):", 0, 25, 0, 1)
                bottom_val = st.slider("⬇️ Bỏ lề DƯỚI (%):", 0, 25, 3, 1)
                side_val = st.slider("↔️ Bỏ lề TRÁI/PHẢI (%):", 0, 15, 0, 1)
                overlap_val = st.slider("🔍 Vùng phủ vạch ngăn (Px):", 5, 40, 15, 1)

            st.image(image, caption="Lá số đã tải lên", use_container_width=True)
            cropped_dict = crop_12_cung_overlap(image, top_val, bottom_val, side_val, overlap_val)

            with st.expander("🔍 Xem mảnh cắt 12 Cung"):
                cols = st.columns(3)
                for idx, (name, crop_img) in enumerate(cropped_dict.items()):
                    cols[idx % 3].image(crop_img, caption=f"Cung {name}", use_container_width=True)

        btn_main_analyze = st.button("🔮 BẮT ĐẦU LUẬN GIẢI", type="primary", key="btn_main", use_container_width=True)

    with col_output:
        st.subheader("📜 Kết Quả Luận Giải Tự Động")

        if "analysis_result" not in st.session_state:
            st.session_state.analysis_result = None
        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = []

        if btn_sidebar_analyze or btn_main_analyze:
            if not uploaded_file:
                st.warning("⚠️ Vui lòng tải lên ảnh lá số trước!")
            elif not API_KEY:
                st.error("❌ Chưa cấu hình GEMINI_API_KEY trong Secrets!")
            else:
                with st.spinner("⚡ AI đang nạp dữ liệu và tiến hành luận giải..."):
                    try:
                        client = genai.Client(api_key=API_KEY)

                        # Sử dụng f-string ba dấu ngoặc kép để tránh lỗi SyntaxError đối với ký tự \n
                        if engine_data:
                            engine_str = json.dumps(engine_data, ensure_ascii=False, indent=2)[:250000]
                            engine_context = f"""```json
{engine_str}
