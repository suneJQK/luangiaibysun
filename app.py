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
    .stApp { background-color: #0e1117; }
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
        margin-bottom: 15px;
        display: flex;
        align-items: center;
        gap: 10px;
        border-bottom: 1px solid #30363d;
        padding-bottom: 10px;
    }
    .scrollable-result-container {
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 20px;
        background-color: #161b22;
        max-height: 800px;
        overflow-y: auto;
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

API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", os.environ.get("GITHUB_TOKEN", ""))
GITHUB_REPO = st.secrets.get("GITHUB_REPO", os.environ.get("GITHUB_REPO", ""))

BASE_DIR = Path(__file__).parent
ENGINE_FILE = BASE_DIR / "tu_vi_engine.json"
BOOKS_FILE = BASE_DIR / "books_cache.json"
PROMPT_DIR = BASE_DIR / "system_prompts"

@st.cache_resource
def get_gemini_client(api_key):
    return genai.Client(api_key=api_key)

@st.cache_data(ttl=3600)
def load_system_prompt():
    if not PROMPT_DIR.exists():
        return "Bạn là chuyên gia Tử Vi Đẩu Số cao cấp.", f"Không tìm thấy thư mục {PROMPT_DIR.name}"
    
    txt_files = list(PROMPT_DIR.glob("*.txt"))
    if not txt_files:
        return "Bạn là chuyên gia Tử Vi Đẩu Số cao cấp.", "Thư mục system_prompts trống."
    
    target_file = txt_files[0]
    try:
        with open(target_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
        return content, None
    except Exception as e:
        return "", f"Lỗi đọc file {target_file.name}: {str(e)}"

@st.cache_data(ttl=3600)
def load_engine_rules():
    if not ENGINE_FILE.exists():
        return None, f"Không tìm thấy file quy tắc: {ENGINE_FILE.name}"
    try:
        with open(ENGINE_FILE, "r", encoding="utf-8") as f:
            return json.load(f), None
    except Exception as e:
        return None, f"Lỗi cấu trúc file {ENGINE_FILE.name}: {str(e)}"

@st.cache_data(ttl=3600)
def load_books_reference():
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

st.markdown('<div class="main-header">☯️ TỬ VI ĐẨU SỐ LUẬN GIẢI TỰ ĐỘNG</div>', unsafe_allow_html=True)

main_system_prompt, prompt_err = load_system_prompt()
engine_data, engine_err = load_engine_rules()
books_text, books_err = load_books_reference()

with st.sidebar:
    st.image("https://img.icons8.com/color/96/yin-yang.png", width=64)
    st.title("⚙️ Thông Tin Hệ Thống")
    if API_KEY:
        st.caption("✅ Gemini API: **Đã kết nối**")
    else:
        st.caption("❌ Gemini API: **Chưa cấu hình KEY**")

    if not prompt_err:
        st.caption("📜 System Prompt: **Đã nạp ngầm**")
    if engine_data:
        st.caption("📜 Quy tắc chính: **Đã nạp ngầm**")
    if books_text:
        st.caption("📚 Kho tham khảo: **Đã nạp ngầm**")

# Giao diện chính chia làm 2 cột độc lập
col_input, col_output = st.columns([1, 1.5], gap="large")

with col_input:
    st.subheader("📸 Tải Lên & Cấu Hình Lá Số")
    uploaded_file = st.file_uploader("Tải lên ảnh lá số:", type=["jpg", "jpeg", "png", "webp"])
    cropped_dict = {}

    selected_year = st.number_input("📅 Năm luận Tiểu Hạn:", 1950, 2050, 2026, 1)
    user_note = st.text_area(
        "📝 Ghi chú / Yêu cầu thêm:",
        value="Yêu cầu AI áp dụng nghiêm ngặt quy tắc trong tu_vi_engine.json và dẫn chứng thêm câu phú từ kho sách.",
        height=80,
    )

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

    btn_main_analyze = st.button("🔮 BẮT ĐẦU LUẬN GIẢI", type="primary", use_container_width=True)

    st.markdown("---")
    st.subheader("💬 Trò chuyện & Hỏi đáp với AI")
    
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_question = st.chat_input("Nhập câu hỏi về lá số (Ví dụ: Hạn năm nay cần lưu ý gì?)...")
    if user_question:
        if not API_KEY:
            st.error("❌ Chưa cấu hình GEMINI_API_KEY!")
        else:
            st.session_state.chat_messages.append({"role": "user", "content": user_question})
            with st.chat_message("user"):
                st.markdown(user_question)

            with st.chat_message("assistant"):
                with st.spinner("🔮 AI đang suy luận câu trả lời..."):
                    try:
                        client = get_gemini_client(API_KEY)
                        analysis_context = st.session_state.get("analysis_result", "Chưa có bài luận giải chi tiết.")
                        engine_json_chat_str = json.dumps(engine_data, ensure_ascii=False, indent=2)[:100000] if engine_data else ""

                        chat_system_instruction = f"{main_system_prompt}\n\nDưới đây là BÀI LUẬN GIẢI GỐC của lá số này:\n--- START ANALYSIS ---\n{analysis_context}\n--- END ANALYSIS ---\n\nBỘ QUY TẮC CỐT LÕI (tu_vi_engine.json):\n```json\n{engine_json_chat_str}\n```\n\nHãy trả lời câu hỏi của người dùng một cách chính xác, bám sát bài luận giải gốc và quy tắc Tử Vi."

                        conversation = [f"{'Người dùng' if m['role']=='user' else 'AI'}: {m['content']}" for m in st.session_state.chat_messages]
                        chat_prompt = "\n".join(conversation)

                        chat_response = client.models.generate_content(
                            model="gemini-3.6-flash",
                            contents=chat_prompt,
                            config=types.GenerateContentConfig(
                                system_instruction=chat_system_instruction,
                                temperature=0.3
                            )
                        )

                        if chat_response and chat_response.text:
                            reply = chat_response.text
                            st.markdown(reply)
                            st.session_state.chat_messages.append({"role": "assistant", "content": reply})
                        else:
                            st.error("Không nhận được phản hồi từ AI.")
                    except Exception as e:
                        st.error(f"❌ Lỗi khi gửi câu hỏi: {e}")

with col_output:
    if "analysis_result" not in st.session_state:
        st.session_state.analysis_result = None

    if btn_main_analyze:
        if not uploaded_file:
            st.warning("⚠️ Vui lòng tải lên ảnh lá số trước!")
        elif not API_KEY:
            st.error("❌ Chưa cấu hình GEMINI_API_KEY trong Secrets!")
        elif not engine_data:
            st.error("❌ Ứng dụng không thể chạy do thiếu file quy tắc `tu_vi_engine.json`!")
        else:
            with st.spinner("⚡ AI đang nạp system prompt & tu_vi_engine.json để thực thi..."):
                try:
                    client = get_gemini_client(API_KEY)
                    engine_json_str = json.dumps(engine_data, ensure_ascii=False, indent=2)[:100000] if engine_data else ""
                    
                    combined_system_instruction = f"{main_system_prompt}\n\n=== BỘ QUY TẮC BẮT BUỘC THỰC THI (tu_vi_engine.json) ===\n```json\n{engine_json_str}\n```"

                    ref_books_context = ""
                    if books_text:
                        ref_books_context = f"\n\nKHO SÁCH & PHÚ THAM KHẢO BỔ SUNG (BOOKS REFERENCE):\n{books_text[:100000]}"

                    user_prompt = f"Hãy đọc lá số Tử Vi từ các hình ảnh được cung cấp.\n- Năm luận Tiểu Hạn: {selected_year}\n- Yêu cầu thêm từ người dùng: {user_note}\n\n{ref_books_context}\n\nHãy tiến hành nhận diện 12 cung, lập ma trận sao và xuất báo cáo luận giải chi tiết theo đúng định dạng được quy định."

                    content_payload = [image]
                    for cung_name, crop_img in cropped_dict.items():
                        content_payload.append(f"Mảnh cắt Cung {cung_name}:")
                        content_payload.append(crop_img)
                    content_payload.append(user_prompt)

                    # Cơ chế thử lại tối đa 3 lần nếu gặp lỗi quá tải 503
                    response = None
                    for attempt in range(3):
                        try:
                            response = client.models.generate_content(
                                model="gemini-3.6-flash",
                                contents=content_payload,
                                config=types.GenerateContentConfig(
                                    system_instruction=combined_system_instruction,
                                    temperature=0.15
                                )
                            )
                            break
                        except Exception as api_err:
                            if "503" in str(api_err) and attempt < 2:
                                time.sleep(3) # Chờ 3 giây rồi thử lại
                                continue
                            else:
                                raise api_err

                    if response and response.text:
                        st.session_state.analysis_result = response.text
                        st.session_state.chat_messages = []
                        st.success("✅ Đã hoàn tất luận giải!")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Lỗi xử lý AI Engine: {e}")

    st.markdown('<div class="analysis-header-title">📜 Kết Quả Luận Giải Tự Động (Cố Định Khung)</div>', unsafe_allow_html=True)
    
    # Khung cố định kết quả luận giải tách biệt hoàn toàn
    st.markdown('<div class="scrollable-result-container">', unsafe_allow_html=True)
    if st.session_state.get("analysis_result"):
        st.markdown(f'<div class="scrollable-result-content">{st.session_state.analysis_result}</div>', unsafe_allow_html=True)
        if st.button("🧹 Xóa kết quả"):
            st.session_state.analysis_result = None
            st.rerun()
    else:
        st.info("👈 Hãy tải lên ảnh lá số và nhấn nút 'BẮT ĐẦU LUẬN GIẢI' ở cột bên trái để hiển thị kết quả tại đây.")
    st.markdown('</div>', unsafe_allow_html=True)
