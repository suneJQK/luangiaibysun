#!/usr/bin/env python3
import io
import json
import os
import time
from datetime import datetime
from pathlib import Path

from github import Github, GithubException
from google import genai
from PIL import Image
from pypdf import PdfReader
import streamlit as st

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Tử Vi Đẩu Số - Luận Giải Toàn Diện",
    page_icon="☯️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- TUỲ CHỈNH GIAO DIỆN (CUSTOM CSS) ---
st.markdown(
    """
    <style>
    /* Tổng thể giao diện */
    .stApp {
        background-color: #0e1117;
    }
    
    /* Header chính */
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #f6d365;
        text-align: center;
        margin-bottom: 0.5rem;
        text-shadow: 0px 0px 10px rgba(246, 211, 101, 0.2);
    }
    .sub-header {
        font-size: 1rem;
        color: #a0aec0;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    /* Style cho các card container */
    div[data-testid="stExpander"], div.stCard {
        background-color: #1a202c;
        border-radius: 10px;
        border: 1px solid #2d3748;
        padding: 10px;
    }
    
    /* Button chính */
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
    </style>
""",
    unsafe_allow_html=True,
)

# --- LAYOUT THÔNG TIN HỆ THỐNG (SECRETS) ---
API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", os.environ.get("GITHUB_TOKEN", ""))
GITHUB_REPO = st.secrets.get("GITHUB_REPO", os.environ.get("GITHUB_REPO", ""))

CACHE_FILE = Path(__file__).parent / "books_cache.json"


# --- HÀM TƯƠNG TÁC GITHUB ---
def upload_to_github(uploaded_file):
    """Đẩy file ảnh lá số lên GitHub Repository."""
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
            repo.update_file(
                contents.path, commit_message, file_content, contents.sha
            )
        except GithubException:
            repo.create_file(file_path, commit_message, file_content)

        return (
            True,
            f"https://github.com/{GITHUB_REPO}/blob/main/{file_path}",
        )
    except Exception as e:
        return False, str(e)


# --- HÀM XỬ LÝ CACHE SÁCH & CẮT CUNG ---
@st.cache_data(ttl=3600)
def load_cached_data():
    if not CACHE_FILE.exists():
        return ""
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return "\n".join([str(item) for item in data])
            elif isinstance(data, dict):
                return json.dumps(data, ensure_ascii=False)
            return str(data)
    except Exception:
        return ""


def append_pdf_to_cache(pdf_file):
    try:
        reader = PdfReader(pdf_file)
        extracted_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"

        if not extracted_text.strip():
            return False, "Không thể trích xuất văn bản từ PDF này."

        current_data = []
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    current_data = json.load(f)
                    if not isinstance(current_data, list):
                        current_data = [str(current_data)]
            except Exception:
                current_data = []

        book_entry = f"--- SÁCH: {pdf_file.name} ---\n" + extracted_text
        current_data.append(book_entry)

        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)

        load_cached_data.clear()
        return True, f"Đã nạp thành công '{pdf_file.name}' vào kho dữ liệu!"
    except Exception as e:
        return False, f"Lỗi xử lý file PDF: {e}"


def crop_12_cung_overlap(
    img, top_cut=10, bottom_cut=5, side_cut=2, overlap_px=20
):
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

    cropped_cungs = {}
    for cung_name, (col, row) in grid_map.items():
        left = max(0, left_start + col * w_step - overlap_px)
        top = max(0, top_start + row * h_step - overlap_px)
        right = min(width, left_start + (col + 1) * w_step + overlap_px)
        bottom = min(height, top_start + (row + 1) * h_step + overlap_px)
        cropped_cungs[cung_name] = img.crop((left, top, right, bottom))

    return cropped_cungs


# --- TIÊU ĐỀ ỨNG DỤNG ---
st.markdown(
    '<div class="main-header">☯️ TỬ VI ĐẨU SỐ PHÂN TÍCH TOÀN DIỆN</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="sub-header">Hệ thống luận giải thông minh ứng dụng AI Gemini'
    " 2.5</div>",
    unsafe_allow_html=True,
)

# --- SIDEBAR (THANH ĐIỀU HƯỚNG BÊN TRÁI) ---
with st.sidebar:
    st.image(
        "https://img.icons8.com/color/96/yin-yang.png", width=64
    )  # Icon trang trí
    st.title("⚙️ Tùy Chỉnh Luận Giải")

    selected_year = st.number_input(
        "🗓️ Năm luận Tiểu Hạn:", 1950, 2050, 2026, 1
    )
    user_note = st.text_area(
        "📝 Ghi chú / Yêu cầu thêm:",
        value=(
            "Yêu cầu AI phân tích chi tiết, minh bạch quy tắc và không bỏ sót bất"
            " kỳ cung hay tháng nào."
        ),
        height=100,
    )

    st.markdown("---")
    st.subheader("🔌 Trạng Thái Kết Nối")

    # Hiển thị status API Key & GitHub Token
    if API_KEY:
        st.caption("✅ Gemini API: **Đã kết nối**")
    else:
        st.caption("❌ Gemini API: **Chưa có Key**")

    if GITHUB_TOKEN and GITHUB_REPO:
        st.caption(f"🐙 GitHub Repo: `{GITHUB_REPO}`")
    else:
        st.caption("⚠️ GitHub Repo: **Chưa cấu hình**")

# --- DANH SÁCH CÁC TAB CHÍNH ---
tab_main, tab_books, tab_settings = st.tabs(
    ["🔮 Luận Giải Lá Số", "📚 Kho Dữ Liệu Sách", "⚙️ Hướng Dẫn & Secrets"]
)

# ==========================================
# TAB 1: LUẬN GIẢI LÁ SỐ
# ==========================================
with tab_main:
    col_input, col_output = st.columns([1, 1.3], gap="large")

    with col_input:
        st.subheader("📸 Upload & Căn Chỉnh Lá Số")
        uploaded_file = st.file_uploader(
            "Tải lên ảnh lá số:", type=["jpg", "jpeg", "png", "webp"]
        )

        cropped_dict = {}
        if uploaded_file:
            # Tự động đẩy lên GitHub
            if st.session_state.get("last_uploaded") != uploaded_file.name:
                with st.spinner("🐙 Đang sao lưu lá số lên GitHub..."):
                    gh_success, gh_msg = upload_to_github(uploaded_file)
                    if gh_success:
                        st.toast(
                            "🐙 Đã tự động lưu lá số lên GitHub!", icon="✅"
                        )
                    else:
                        st.caption(f"⚠️ Lưu GitHub thất bại: {gh_msg}")
                st.session_state.last_uploaded = uploaded_file.name

            image = Image.open(uploaded_file).convert("RGB")

            # Căn chỉnh lề
            with st.expander("🛠️ Căn chỉnh lề & Vạch ngăn Tuần/Triệt", expanded=False):
                top_val = st.slider("⬆️ Bỏ lề TRÊN (%):", 0, 25, 10, 1)
                bottom_val = st.slider("⬇️ Bỏ lề DƯỚI (%):", 0, 25, 5, 1)
                side_val = st.slider("↔️ Bỏ lề TRÁI/PHẢI (%):", 0, 15, 2, 1)
                overlap_val = st.slider(
                    "🔍 Vùng phủ vạch ngăn (Px):", 5, 40, 20, 5
                )

            st.image(
                image, caption="Lá số đã tải lên", use_container_width=True
            )
            cropped_dict = crop_12_cung_overlap(
                image, top_val, bottom_val, side_val, overlap_val
            )

            with st.expander("🔍 Xem mảnh cắt 12 Cung"):
                cols = st.columns(3)
                for idx, (name, crop_img) in enumerate(cropped_dict.items()):
                    cols[idx % 3].image(
                        crop_img,
                        caption=f"Cung {name}",
                        use_container_width=True,
                    )

        btn_analyze = st.button(
            "🔮 BẮT ĐẦU LUẬN GIẢI", type="primary", use_container_width=True
        )

    with col_output:
        st.subheader("📜 Kết Quả Luận Giải")

        if "analysis_result" not in st.session_state:
            st.session_state.analysis_result = None

        if btn_analyze:
            if not uploaded_file:
                st.warning("⚠️ Vui lòng tải lên ảnh lá số trước!")
            elif not API_KEY:
                st.error(
                    "❌ Chưa phát hiện Gemini API Key! Vui lòng cấu hình"
                    " Secrets."
                )
            else:
                with st.spinner(
                    "⚡ AI Gemini đang phân tích 12 Cung & Lập Bản Luận Giải..."
                ):
                    pdf_text_context = load_cached_data()
                    truncated_context = (
                        pdf_text_context[:300000]
                        if pdf_text_context
                        else "Sử dụng kiến thức Tử Vi Nam Phái, Bắc Phái, Trung Châu Phái."
                    )

                    prompt = f"""
Bạn là Chuyên Gia Tử Vi Đẩu Số hàng đầu. Nhiệm vụ của bạn là đọc hiểu lá số và thực hiện một bản luận giải CỰC KỲ CHI TIẾT.

BẮT BUỘC tuân thủ NGHIÊM NGẶT Quy trình 6 bước dưới đây.
... (Phần Prompt giữ nguyên)...
Năm luận giải: {selected_year}
Ghi chú gia chủ: {user_note}
Dữ liệu sách: {truncated_context}
"""
                    try:
                        client = genai.Client(api_key=API_KEY)
                        content_payload = [image]
                        for cung_name, crop_img in cropped_dict.items():
                            content_payload.append(f"Mảnh cắt Cung {cung_name}:")
                            content_payload.append(crop_img)
                        content_payload.append(prompt)

                        response = client.models.generate_content(
                            model="gemini-2.5-flash", contents=content_payload
                        )

                        if response:
                            st.session_state.analysis_result = response.text
                            st.success(
                                f"✅ Đã phân tích xong lá số cho năm"
                                f" {selected_year}!"
                            )
                    except Exception as e:
                        st.error(f"❌ Lỗi xử lý API: {e}")

        if st.session_state.analysis_result:
            st.markdown(st.session_state.analysis_result)
        else:
            st.info(
                "👈 Nhấn nút **'BẮT ĐẦU LUẬN GIẢI'** ở cột bên trái để xuất kết"
                " quả tại đây."
            )

# ==========================================
# TAB 2: QUẢN LÝ KHO SÁCH
# ==========================================
with tab_books:
    st.subheader("📚 Quản Lý Kho Dữ Liệu Sách Tử Vi (Local Cache)")
    st.caption(f"Vị trí lưu cache: `{CACHE_FILE.resolve()}`")

    col_b1, col_b2 = st.columns([1, 1])

    with col_b1:
        uploaded_pdf = st.file_uploader(
            "Nạp thêm PDF sách Tử Vi vào kho:", type=["pdf"]
        )
        if uploaded_pdf and st.button(
            "📥 Trích xuất & Nạp vào Cache", use_container_width=True
        ):
            with st.spinner("Đang trích xuất dữ liệu PDF..."):
                success, msg = append_pdf_to_cache(uploaded_pdf)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)

    with col_b2:
        pdf_text_context = load_cached_data()
        st.metric(
            "Tổng dung lượng kho sách cache", f"{len(pdf_text_context):,} ký tự"
        )
        if st.button("🗑️ Xóa kho dữ liệu cache"):
            if CACHE_FILE.exists():
                CACHE_FILE.unlink()
                load_cached_data.clear()
                st.rerun()

# ==========================================
# TAB 3: HƯỚNG DẪN & SECRETS
# ==========================================
with tab_settings:
    st.subheader("⚙️ Hướng Dẫn Cấu Hình Streamlit Secrets")
    st.markdown("""
    Để ứng dụng chạy ổn định trên **Streamlit Cloud**, bạn hãy vào **Settings -> Secrets** trên Dashboard của Streamlit và dán cấu hình sau:

    ```toml
    GEMINI_API_KEY = "AIzaSy..."

    # Cấu hình tự động lưu lá số lên GitHub
    GITHUB_TOKEN = "ghp_xxxx..."
    GITHUB_REPO = "user-cua-ban/ten-repo"
    ```
    """)
