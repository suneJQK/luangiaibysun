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
    .sub-header {
        font-size: 1rem;
        color: #a0aec0;
        text-align: center;
        margin-bottom: 2rem;
    }
    div[data-testid="stExpander"] {
        background-color: #1a202c;
        border-radius: 10px;
        border: 1px solid #2d3748;
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
    </style>
""",
    unsafe_allow_html=True,
)

# --- LẤY SECRETS ---
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


# --- HÀM ĐỌC CACHE DỮ LIỆU SÁCH ---
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


# --- HÀM CẮT 12 CUNG ---
def crop_12_cung_overlap(
    img, top_cut=0, bottom_cut=3, side_cut=0, overlap_px=15
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
    '<div class="sub-header">Hệ thống luận giải thông minh ứng dụng AI '"</div>",
    unsafe_allow_html=True,
)

# --- SIDEBAR (THANH ĐIỀU HƯỚNG BÊN TRÁI) ---
with st.sidebar:
    st.image("https://img.icons8.com/color/96/yin-yang.png", width=64)
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

    if API_KEY:
        st.caption("✅ Gemini API: **Đã kết nối**")
    else:
        st.caption("❌ Gemini API: **Chưa có Key**")

    if GITHUB_TOKEN and GITHUB_REPO:
        st.caption(f"🐙 GitHub Repo: `{GITHUB_REPO}`")
    else:
        st.caption("⚠️ GitHub Repo: **Chưa cấu hình**")

# --- CHỈ GIỮ LẠI 2 TAB ---
tab_main, tab_books = st.tabs(
    ["🔮 Luận Giải Lá Số", "📚 Kho Dữ Liệu Sách"]
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

            # Căn chỉnh lề cài đặt mặc định theo thông số mới: (Top: 0, Bottom: 3, Side: 0, Overlap: 15)
            with st.expander("🛠️ Căn chỉnh lề & Vạch ngăn Tuần/Triệt", expanded=False):
                top_val = st.slider("⬆️ Bỏ lề TRÊN (%):", 0, 25, 0, 1)
                bottom_val = st.slider("⬇️ Bỏ lề DƯỚI (%):", 0, 25, 3, 1)
                side_val = st.slider("↔️ Bỏ lề TRÁI/PHẢI (%):", 0, 15, 0, 1)
                overlap_val = st.slider(
                    "🔍 Vùng phủ vạch ngăn (Px):", 5, 40, 15, 1
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
Bạn là Chuyên Gia Tử Vi Đẩu Số hàng đầu (kết hợp kiến thức Nam Phái, Bắc Phái và Trung Châu Phái). Nhiệm vụ của bạn là đọc hiểu lá số và thực hiện một bản luận giải CỰC KỲ CHI TIẾT.

BẮT BUỘC tuân thủ NGHIÊM NGẶT Quy trình 6 bước dưới đây. Tại mỗi bước, bạn phải áp dụng đúng Quy tắc phân tích được giao phó. KHÔNG ĐƯỢC làm tắt, KHÔNG ĐƯỢC bỏ sót bất kỳ cung hay tháng nào.

====================================================================
MA TRẬN LUẬN GIẢI: QUY TRÌNH TÍCH HỢP QUY TẮC
====================================================================

[RULE - LUẬN PHỤ TINH & SÁT TINH]:
Mỗi phụ tinh/sát tinh xuất hiện BẮT BUỘC phải có 1 dòng phân tích riêng theo công thức: [Tên Sao] + [Đắc/Hãm] + [Tương tác Cung/Chính tinh] -> [Hành vi/Tai họa/Cát lành cụ thể].

Không được gộp chung kiểu: "Các sao A, B, C giúp giải trừ bệnh tật..." mà phải tách rõ:
- Sao A làm gì?
- Sao B gây ra rắc rối gì cụ thể? (Ví dụ: Hỏa Hãm = nóng nảy, thần kinh; Diêu Hãm = thị phi tình cảm, nghiện ngập).

Nếu có sự xuất hiện của các Bộ Sao Đi Kèm (Ví dụ: Đào + Diêu, Hỏa + Linh, Lộc + Mã...), BẮT BUỘC phải chỉ ra phản ứng hóa học giữa bộ sao đó.

BƯỚC 1: GIẢI MÃ NỀN TẢNG MỆNH BÀN (TỔNG QUAN CUỘC ĐỜI)
[Quy tắc áp dụng]: 
- Xét Âm Dương Nghịch/Thuận Lý (Can Chi năm sinh vs Giới tính).
- Xét Sinh Khắc Mệnh - Cục (Ví dụ: Mệnh sinh Cục, Cục khắc Mệnh...).
- Đánh giá sự đắc vị của Mệnh Chủ, Thân Chủ và vị trí Cung Thân (Thân cư Mệnh, Thân cư Thê, Thân cư Quan, Thân cư Tài, Thân cư Di, Thân cư Phúc).
[Yêu cầu Đầu ra Bước 1]: 
- Viết tóm tắt về "Căn cơ bẩm sinh" và "Nghịch cảnh/Thuận lợi cốt lõi" của đương số dựa trên các quy tắc trên. Đánh giá vị trí Cung Thân (xu hướng vãn niên).

---
BƯỚC 2: MÔ PHỎNG CHI TIẾT 12 CUNG CỐ ĐỊNH (YÊU CẦU ĐỘ DÀI & ĐỘ SÂU ĐỒNG ĐỀU 100%)

⚠️ CẢNH BÁO CẤP CAO DÀNH CHO AI: 
- KHÔNG ĐƯỢC tập trung viết dài Cung Mệnh rồi viết ngắn/tóm tắt các cung khác!
- TẤT CẢ 12 CUNG phải được phân tích theo đúng TIÊU CHUẨN CẤU TRÚC 5 MỤC DƯỚI ĐÂY. 
- Mức độ chi tiết, số lượng từ và độ sâu phân tích của Cung Phụ Mẫu, Phúc Đức, Điền Trạch... BẮT BUỘC PHẢI TƯƠNG ĐƯƠNG Cung Mệnh.

TRÌNH TỰ BẮT BUỘC KHUÔN MẪU TỪNG CUNG (Áp dụng lần lượt cho cả 12 Cung):

MỖI CUNG PHẢI TRÌNH BÀY ĐỦ 5 MỤC NÀY:
1. [Tên Cung] - Cấu Trúc Tinh Hệ & Ngũ Hành:
   - Tọa thủ: Liệt kê Chính tinh (Đắc/Miếu/Vượng/Hãm) và Phụ tinh tại bản cung.
   - Xung chiếu: Các sao từ cung đối diện chiếu về.
   - Tam hợp: Các sao từ 2 cung trong tam hợp chiếu về.
   - Giáp cung: Các sao ở 2 cung kề bên (Giáp Kình Đà, Giáp Lộc, Giáp Hóa...).
   - Đánh giá Ảnh hưởng Tuần/Triệt (nếu có).
2. Phân Tích Bản Chất & Tính Cách / Diện Mạo (Liên quan đến cung đó):
   - Luận giải chi tiết ý nghĩa các Bộ sao tọa thủ và chiếu.
   - Nêu rõ ưu điểm cốt lõi và nhược điểm tiềm ẩn.
3. Luận Giải Cát - Hung & Họa Phúc Thực Tế:
   - Tương tác Cát tinh (Xương Khúc, Tả Hữu, Khôi Việt, Lộc Tồn...): Mang lại thuận lợi, cơ hội gì?
   - Tương tác Sát/Bại tinh (Kình Đà, Hỏa Linh, Không Kiếp, Hao, Hình, Kỵ...): Gây ra rủi ro, tổn thất, áp lực hay tai họa gì?
4. Tương Quan Ngũ Hành Bản Mệnh với Ngũ Hành Cung:
   - So sánh Ngũ Hành của Mệnh đương số với Ngũ Hành Địa Chi của Cung đang luận (Tương sinh, Tương trợ hay Tương khắc). 
   - Đánh giá đương số gánh vác, hưởng lợi hay chịu gánh nặng từ cung này.
5. Đánh Giá Tổng Kết & Lời Khuyên Ứng Xử:
   - Chấm điểm tiềm năng/độ thuận lợi của cung (Thang điểm 10 hoặc đánh giá Đắc địa / Bình hòa / Hung hiểm).
   - Đưa ra 1-2 lời khuyên chiến lược giúp phát huy điểm tốt hoặc né tránh rủi ro.

DANH SÁCH 12 CUNG BẮT BUỘC PHẢI LUẬN ĐỦ (Viết chi tiết chuẩn 5 mục trên cho từng cung):
1. Cung Mệnh | 2. Cung Phụ Mẫu | 3. Cung Phúc Đức | 4. Cung Điền Trạch | 5. Cung Quan Lộc | 6. Cung Nô Bộc | 7. Cung Thiên Di | 8. Cung Tật Ách | 9. Cung Tài Bạch | 10. Cung Tử Tức | 11. Cung Phu Thê | 12. Cung Huynh Đệ

---
BƯỚC 3: PHÂN TÍCH ĐẠI VẬN 10 NĂM HIỆN TẠI
[Quy tắc áp dụng]: 
- Xét Thiên Thời (Hành của Đại Vận so với Hành Bản Mệnh).
- Xét Địa Lợi (Vị trí cung Đại Vận nằm ở vòng Thái Tuế nào: Thái Tuế, Tuế Phá, Tang Môn...).
- Xét Nhân Hòa (Các sao tụ hội tại cung Đại Vận).
[Yêu cầu Đầu ra Bước 3]: 
- Đánh giá tổng quan 10 năm này là Hưng Thịnh, Tích Lũy, Trì Trệ hay Thử Thách. Chấm điểm Đại Vận (trên thang 5 sao ★★★★★).

---
BƯỚC 4: LUẬN TIỂU HẠN & LƯU TỨ HÓA NĂM {selected_year} (TRỌNG TÂM)
[Quy tắc áp dụng]:
- Xác định Thiên Can năm {selected_year} để an Lưu Tứ Hóa (L.Lộc, L.Quyền, L.Khoa, L.Kỵ) vào các Chính tinh tương ứng trên lá số.
- Xét Tương tác bản cung: L.Hóa Lộc mang lại cơ hội ở cung nào? L.Hóa Kỵ gây thắt nút, thị phi ở cung nào?
- Quét các sao Lưu động: L.Thái Tuế, L.Kình Đà, L.Tang Hổ nhập vào cung nào, kích hoạt hung/cát gì với sao Cố định?
[Yêu cầu Đầu ra Bước 4]: 
- Trình bày rõ: Năm {selected_year}, năng lượng Hóa Lộc, Quyền, Khoa, Kỵ rơi vào các sao nào, cung nào. 
- Chỉ ra 3 sự kiện LỚN NHẤT có khả năng xảy ra trong năm nay.

---
BƯỚC 5: LẬP TRÌNH VẬN HẠN 12 THÁNG ÂM LỊCH NĂM {selected_year}
[Quy tắc áp dụng]: 
- Dịch chuyển điểm nhìn theo từng tháng Âm lịch. Áp dụng quy tắc Tam Phương Tứ Chính tại cung của tháng đó.
- Đặc biệt chú ý các tháng có L.Hóa Kỵ, L.Thái Tuế hoặc Sát Tinh tụ hội.
[Yêu cầu Đầu ra Bước 5]: 
- Bắt buộc liệt kê đủ 12 tháng (Từ Tháng 1 đến Tháng 12 Âm lịch). Mỗi tháng viết 1 đoạn ngắn gọn nhưng sắc bén về: Tiền bạc, Công việc, Sức khỏe/Gia đạo. Đánh dấu (Cát), (Hung), hoặc (Bình) cho từng tháng.

---
BƯỚC 6: TỔNG KẾT & PHƯƠNG PHÁP CẢI VẬN
[Quy tắc áp dụng]: Đạo lý "Đức năng thắng số" và nguyên lý cân bằng Ngũ Hành.
[Yêu cầu Đầu ra Bước 6]: 
- Đưa ra 3 lời khuyên cốt lõi nhất để đương số tận dụng L.Hóa Lộc và hóa giải L.Hóa Kỵ trong năm {selected_year}.

--------------------------------------------------------------------
📖 DỮ LIỆU SÁCH / PHÚ TỬ VI TRÍCH XUẤT (PDF CONTEXT):
{truncated_context}

=== YÊU CẦU BỔ SUNG CỦA GIA CHỦ ===
{user_note}
"""
                    try:
                        client = genai.Client(api_key=API_KEY)
                        content_payload = [image]
                        for cung_name, crop_img in cropped_dict.items():
                            content_payload.append(f"Mảnh cắt Cung {cung_name}:")
                            content_payload.append(crop_img)
                        content_payload.append(prompt)

                        response = client.models.generate_content(
                            model="gemini-3.-flash", contents=content_payload
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
# TAB 2: QUẢN LÝ KHO SÁCH (CHỈ HIỂN THỊ DUNG LƯỢNG)
# ==========================================
with tab_books:
    st.subheader("📚 Kho Dữ Liệu Sách Tử Vi (Lưu Trữ Cố Định)")
    pdf_text_context = load_cached_data()
    st.info(f"📍 **File dữ liệu:** `{CACHE_FILE.name}`")
    st.metric(
        "Tổng dung lượng kho sách đang sử dụng",
        f"{len(pdf_text_context):,} ký tự",
    )
