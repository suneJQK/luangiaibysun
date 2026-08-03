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
    page_title="Tử Vi Đẩu Số - Luận Giải & Cách Cục",
    page_icon="☯️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- TUỲ CHỈNH GIAO DIỆN & CẤU TRÚC CSS (ẨN THANH STREAMLIT AN TOÀN) ---
st.markdown(
    """
    <style>
    /* 1. ẨN AN TOÀN HEADER, TOOLBAR, FOOTER VÀ MENU STREAMLIT */
    header[data-testid="stHeader"] {
        visibility: hidden !important;
        height: 0px !important;
        min-height: 0px !important;
    }

    div[data-testid="stToolbar"] {
        visibility: hidden !important;
        height: 0px !important;
    }

    footer {
        visibility: hidden !important;
        height: 0px !important;
    }

    #MainMenu {
        visibility: hidden !important;
    }

    /* 2. CHỈNH TỐI ƯU KHOẢNG TRẮNG ĐẦU TRANG */
    .main .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
    }

    /* 3. MÀU NỀN TỔNG THỂ & SIDEBAR */
    .stApp, [data-testid="stAppViewContainer"] {
        background-color: #0e1117 !important;
    }

    [data-testid="stSidebar"] {
        background-color: #161b22 !important;
    }

    /* 4. KIỂU DÁNG TIÊU ĐỀ & NÚT BẤM */
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

# --- LẤY SECRETS & CẤU HÌNH MẶC ĐỊNH ---
API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", os.environ.get("GITHUB_TOKEN", ""))
GITHUB_REPO = st.secrets.get("GITHUB_REPO", os.environ.get("GITHUB_REPO", ""))

CACHE_FILE = Path(__file__).parent / "books_cache.json"


# --- HÀM TƯƠNG TÁC GITHUB ---
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


# --- HÀM ĐỌC CACHE DỮ LIỆU SÁCH JSON ---
@st.cache_data(ttl=3600)
def load_cached_data():
    if not CACHE_FILE.exists():
        return ""
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return "\n\n".join([str(item) for item in data])
            elif isinstance(data, dict):
                return json.dumps(data, ensure_ascii=False, indent=2)
            return str(data)
    except Exception:
        return ""


def get_book_list_info():
    if not CACHE_FILE.exists():
        return []
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            titles = []
            if isinstance(data, list):
                for idx, item in enumerate(data):
                    if isinstance(item, dict) and "title" in item:
                        titles.append(
                            f"{idx+1}. {item['title']} (Tác giả: {item.get('author', 'N/A')})"
                        )
                    elif isinstance(item, str):
                        first_line = item.strip().split("\n")[0][:80]
                        titles.append(f"{idx+1}. {first_line}...")
            return titles
    except Exception:
        return []


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
        left = int(max(0, left_start + col * w_step - overlap_px))
        top = int(max(0, top_start + row * h_step - overlap_px))
        right = int(min(width, left_start + (col + 1) * w_step + overlap_px))
        bottom = int(min(height, top_start + (row + 1) * h_step + overlap_px))
        cropped_cungs[cung_name] = img.crop((left, top, right, bottom))

    return cropped_cungs


# --- TIÊU ĐỀ ỨNG DỤNG ---
st.markdown(
    '<div class="main-header">☯️ TỬ VI ĐẨU SỐ PHÂN TÍCH TOÀN DIỆN</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="sub-header">Hệ thống luận giải thông minh tích hợp Luận Cách Cục & Tam Hợp</div>',
    unsafe_allow_html=True,
)

# --- TAB CHÍNH (ĐÃ XÓA TAB LIÊN HỆỞ TRÊN) ---
tab_main, tab_books = st.tabs(
    [
        "🔮 Luận Giải Lá Số",
        "📚 Kho Dữ Liệu Sách & Trích Dẫn",
    ]
)

# TAB 1: LUẬN GIẢI
with tab_main:
    col_input, col_output = st.columns([1, 1.3], gap="large")

    with col_input:
        st.subheader("📸 Upload & Căn Chỉnh Lá Số")
        uploaded_file = st.file_uploader(
            "Tải lên ảnh lá số:", type=["jpg", "jpeg", "png", "webp"]
        )

        cropped_dict = {}
        if uploaded_file:
            if st.session_state.get("last_uploaded") != uploaded_file.name:
                with st.spinner("🐙 Đang tải lá số ..."):
                    gh_success, gh_msg = upload_to_github(uploaded_file)
                    if gh_success:
                        st.toast("🐙 Đã lưu lá số !", icon="✅")
                    else:
                        st.caption(f"⚠️ Lưu GitHub thất bại: {gh_msg}")
                st.session_state.last_uploaded = uploaded_file.name

            image = Image.open(uploaded_file).convert("RGB")

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

        st.markdown("---")

        # TÙY CHỈNH LUẬN GIẢI
        st.subheader("⚙️ Tùy Chỉnh Luận Giải")

        selected_year = st.number_input(
            "🗓️ Năm luận Tiểu Hạn:", 1950, 2050, 2026, 1
        )

        user_note = st.text_area(
            "📝 Ghi chú / Yêu cầu thêm:",
            value=(
                "Cục (Thành cách/Pha cách), Tam Hợp chiếu, minh bạch quy tắc và"
                " không bỏ sót bất kỳ cung hay tháng nào."
            ),
            height=120,
        )

        btn_main_analyze = st.button(
            "🔮 BẮT ĐẦU LUẬN GIẢI",
            type="primary",
            key="btn_main",
            use_container_width=True,
        )

        st.markdown("---")

        # MỤC LIÊN HỆ & HỖ TRỢ BÊN DƯỚI NÚT LUẬN GIẢI
        st.subheader("🔗 Liên Hệ & Hỗ Trợ")
        st.caption("Mọi góp ý, báo lỗi hoặc hỗ trợ vui lòng truy cập:")
        st.markdown(
            "👉 **[Kênh Hỗ Trợ TikTok](https://www.tiktok.com/@tieuyet11)**"
        )

    with col_output:
        st.subheader("📜 Kết Quả Luận Giải")

        if "analysis_result" not in st.session_state:
            st.session_state.analysis_result = None

        if btn_main_analyze:
            if not uploaded_file:
                st.warning("⚠️ Vui lòng tải lên ảnh lá số trước!")
            elif not API_KEY:
                st.error(
                    "❌ Chưa phát hiện Gemini API Key! Vui lòng cấu hình Secrets."
                )
            else:
                with st.spinner(
                    "⚡ AI đang phân tích Cách Cục, Tam Hợp & Đánh giá Kho Sách..."
                ):
                    pdf_text_context = load_cached_data()
                    truncated_context = (
                        pdf_text_context[:300000]
                        if pdf_text_context
                        else "Sử dụng kiến thức Tử Vi."
                    )

                    prompt = f"""
Bạn là Chuyên Gia Tử Vi Đẩu Số hàng đầu . Nhiệm vụ của bạn là đọc hiểu lá số và thực hiện một bản luận giải CỰC KỲ CHI TIẾT.
-*** Nói đúng chuyên môn không nói giảm nói tránh các yếu tố xấu ***
====================================================================
📖 ĐẶC BIỆT LƯU Ý VỀ DỮ LIỆU SÁCH & PHÚ TỬ VI (BOOKS_CACHE.JSON):
====================================================================
- Dữ liệu bên dưới chứa các bộ sách và câu phú Tử Vi được trích xuất từ `books_cache.json`.
- BẮT BUỘC bạn phải tra cứu và áp dụng các câu phú, lý thuyết có trong phần DỮ LIỆU SÁCH này để luận giải lá số.
- Khi đưa ra đánh giá, nhận định về tinh hệ, chính tinh, sát tinh hay cách cục, bạn PHẢI trích dẫn cụ thể theo định dạng: 
  👉 `[Trích sách: <Tên sách / Tên tác giả> - <Câu phú hoặc lý thuyết tương ứng>]`
====================================================================
MA TRẬN LUẬN GIẢI CHI TIẾT
====================================================================

[RULE - LUẬN PHỤ TINH & SÁT TINH]:
Mỗi phụ tinh/sát tinh xuất hiện BẮT BUỘC phải phân tích riêng theo công thức: 
[Tên Sao] + [Đắc/Hãm] + [Tương tác Cung/Chính tinh/Sao chiếu] -> [Hành vi/Tai họa/Cát lành Đặc điểm ảnh hưởng cụ thể] + [Trích sách: ... (nếu có trong dữ liệu)].

---
BƯỚC 1: GIẢI MÃ NỀN TẢNG MỆNH BÀN (TỔNG QUAN CUỘC ĐỜI)
[Quy tắc áp dụng]: 
- Xét Âm Dương Nghịch/Thuận Lý (Can Chi năm sinh vs Giới tính).
- Xét Sinh Khắc Mệnh - Cục.
- Đánh giá vị trí Mệnh Chủ, Thân Chủ và vị trí Cung Thân (Thân cư Mệnh, Thân cư Thê, Thân cư Quan, Thân cư Tài, Thân cư Di, Thân cư Phúc). Đối chiếu các câu phú về Thân/Mệnh.

---
BƯỚC 2: PHÂN TÍCH CÁCH CỤC LÁ SỐ & THẾ TAM HỢP
[Quy tắc áp dụng]:
1. Nhận diện Cách Cục Chính của Mệnh - Tài - Quan:
   - Xác định bộ chính tinh chủ đạo: Tử Phủ Vũ Tướng Liêm, Cự Nhật, Cơ Cự Đồng Lương, Sát Phá Tham, hay Nhật Nguyệt...
   - Phân tích tên gọi Cách Cục cụ thể (Ví dụ: Cự Nhật Mão Dần, Tử Phủ Đồng Cung, Thất Sát Triều Đẩu, Tham Vũ Đồng Hành, Cự Cơ Mão Dậu...). Trích dẫn câu phú/sách nói về cách cục này.
   - Luôn xét tam hợp và xung chiếu ở tất cả các cung để luận giải một cách tổng quan nhất 
   - **Khi xét các cách cục luôn xét xem nó có được trợ lực bởi các bộ sao không ví dụ( xương khúc , khôi việt ,khoa quền lộc kỵ,tả hữu ,thai tọa..).
   - **hoặc có bị phá bởi sát tinh (không kiếp kình đà linh hỏa )tác động bởi sát tinh lên cung đó là gì tốt hay xấu .
2. Phân tích Đỉnh Cao Cách Cục (Thành Cách hay Pha Cách):
   - **Thành Cách:** Đạt được nhờ hội các Cát tinh/Quyền tinh nào? (Khôi Việt, Tả Hữu, Xương Khúc, Lộc Tồn, Tứ Hóa...).
   - **Pha Cách / Chiết Giảm:** Bị tổn hại, suy giảm uy lực bởi các Sát tinh/Bại tinh nào? (Kình Đà, Hỏa Linh, Không Kiếp, Kỵ, Hình...).
3. Phân tích Bộ Tam Hợp (Hợi-Mão-Mùi, Dần-Ngọ-Tuất, Tị-Dậu-Sửu, Thân-Tý-Thìn):
   - Đương số thuộc Tam Hợp nào? Ngũ hành Tam Hợp tương sinh, tương hòa hay tương khắc với Ngũ Hành Bản Mệnh?
   - Đánh giá lực chiếu của các Sao Xung Chiếu và Tam Hợp Chiếu lên Mệnh/Thân.

---
BƯỚC 3: MÔ PHỎNG CHI TIẾT 12 CUNG CỐ ĐỊNH (ÁP DỤNG ĐỒNG ĐỀU 100% CHO 12 CUNG)

⚠️ CẢNH BÁO CẤP CAO DÀNH CHO AI: 
- KHÔNG ĐƯỢC tập trung viết dài Cung Mệnh rồi viết ngắn/tóm tắt các cung khác!
- TẤT CẢ 12 CUNG phải được phân tích theo đúng TIÊU CHUẨN CẤU TRÚC 5 MỤC DƯỚI ĐÂY.

TRÌNH TỰ BẮT BUỘC KHUÔN MẪU TỪNG CUNG (Áp dụng lần lượt cho cả 12 Cung):
MỖI CUNG PHẢI TRÌNH BÀY ĐỦ 5 MỤC NÀY:
1. [Tên Cung] - Cấu Trúc Tinh Hệ, Ngũ Hành & Thế Tam Hợp:
   - Tọa thủ: Liệt kê Chính tinh (Đắc/Miếu/Vượng/Hãm) và TOÀN BỘ Phụ tinh tại bản cung.
   - Thế Tam Hợp & Sao Chiếu: Xác định cung thuộc Bộ Tam Hợp nào, các sao từ Cung Xung Chiếu và 2 Cung Tam Hợp chiếu về.
   - Giáp cung: Các sao ở 2 cung kề bên.
   - Đánh giá Ảnh hưởng Tuần/Triệt (nếu có).
2. Phân Tích Bản Chất & Tính Cách / Diện Mạo.
3. Luận Giải Chi Tiết Từng Phụ Tinh & Cát - Hung Thực Tế (Bắt buộc kèm trích dẫn câu phú từ kho sách nếu có).
4. Tương Quan Ngũ Hành Bản Mệnh với Ngũ Hành Cung & Hành Tam Hợp.
5. Đánh Giá Tổng Kết & Lời Khuyên Ứng Xử.

DANH SÁCH 12 CUNG BẮT BUỘC PHẢI LUẬN ĐỦ:
1. Cung Mệnh | 2. Cung Phụ Mẫu | 3. Cung Phúc Đức | 4. Cung Điền Trạch | 5. Cung Quan Lộc | 6. Cung Nô Bộc | 7. Cung Thiên Di | 8. Cung Tật Ách | 9. Cung Tài Bạch | 10. Cung Tử Tức | 11. Cung Phu Thê | 12. Cung Huynh Đệ
2. Cung mệnh có nhữn đặc điểm gì nổi bật ngoại hình tính cách bị ảnh hưởng bởi những sao gì...
3. Tam hợp cung gồm có (Mệnh -Tài -Quan , Phụ - Tử - Nô , Phúc - Phối - Di ,Điền - Tật - Huynh).
4. Xung chiếu gồm ( Mệnh - DI ,Phụ -Tật , Phúc - Tài ,Điền- Tử ,Quan - Phối,Nô - Huynh).
---
BƯỚC 4: PHÂN TÍCH ĐẠI VẬN 10 NĂM HIỆN TẠI
- Được kí hiêu số ở góc trên bên phải mỗi cung
- Xét Thiên Thời, Địa Lợi, Nhân Hòa và Chấm điểm Đại Vận (thang 5 sao ★★★★★).

---
BƯỚC 5: LUẬN TIỂU HẠN & LƯU TỨ HÓA NĂM {selected_year} (TRỌNG TÂM)
-** Năm tiểu hạn đực kí hiệu là Tí Sữu Giần Mão...Hợi ở góc dưới trái mỗi cung 
- Năng lượng Hóa Lộc, Quyền, Khoa, Kỵ rơi vào các sao nào, cung nào. 3 sự kiện LỚN NHẤT năm.
- Xét các sao lưu của năm như lưu lộc tồn ,lưu kình dương , lưu đà la , lưu đào, lưu hồng, lưu thiên mã,lưu khốc,lươi hư.
---
BƯỚC 6: LẬP TRÌNH VẬN HẠN 12 THÁNG ÂM LỊCH NĂM {selected_year}
- Bắt buộc đủ 12 tháng có kí hiệu ở mỗi cung là T1 đến T12 ở góc dười bên phải (Tháng 1 đến Tháng 12 Âm lịch) 
- Nêu tháng 1,2,3..12 ở cung nào có sao gì diễn biến của tháng đó như thế nào và vẫn phải dựa vào cung tiểu hạn của năm đó.
---
BƯỚC 7: TỔNG KẾT, PHƯƠNG PHÁP CẢI VẬN & DANH SÁCH TRÍCH DẪN
-** Lập bảng tổng kết cách cục của toàn bộ lá số điểm tốt điểm xấu 
-** Xét bản mệnh lá số so với các cung lục thân quan hệ với tuyến phụ mẫu nô bộc con cái và đặc biệt tuyến phu thê
-** Đưa ra lời khuyên cải vận tổng thể.
--------------------------------------------------------------------
📚 NỘI DUNG TỪ KHO DỮ LIỆU SÁCH (BOOKS_CACHE.JSON CONTEXT):
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
                            model="gemini-3.6-flash", contents=content_payload
                        )

                        if response:
                            st.session_state.analysis_result = response.text
                            st.success(
                                f"✅ Đã phân tích xong lá số & Cách cục cho năm {selected_year}!"
                            )
                    except Exception as e:
                        st.error(f"❌ Lỗi xử lý API: {e}")

        if st.session_state.analysis_result:
            st.markdown(st.session_state.analysis_result)
        else:
            st.info(
                "👈 Nhấn nút **'BẮT ĐẦU LUẬN GIẢI'** ở bảng tùy chỉnh bên trái"
                " để xuất kết quả tại đây."
            )

# TAB 2: QUẢN LÝ KHO SÁCH
with tab_books:
    st.subheader("📚 Kho Dữ Liệu Sách & Phú Tử Vi (JSON Cache)")
    pdf_text_context = load_cached_data()
    st.info(f"📍 **File dữ liệu lưu trữ:** `{CACHE_FILE.name}`")

    col_m1, col_m2 = st.columns([1, 1])

    with col_m1:
        st.metric(
            "Tổng dung lượng kho sách đang sử dụng",
            f"{len(pdf_text_context):,} ký tự",
        )

    with col_m2:
        book_titles = get_book_list_info()
        st.metric("Tổng số mục / Tác phẩm", f"{len(book_titles)} mục")

    st.markdown("---")
    st.subheader("📑 Danh Sách Các Tài Liệu Đang Có Trong Kho JSON:")

    if book_titles:
        for title in book_titles:
            st.markdown(f"- **{title}**")
    else:
        st.caption("Chưa phát hiện danh sách tên cụ thể.")
