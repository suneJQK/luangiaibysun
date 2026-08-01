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

# --- CẤU HÌNH API & GITHUB ---
API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", os.environ.get("GITHUB_TOKEN", ""))
GITHUB_REPO = st.secrets.get("GITHUB_REPO", os.environ.get("GITHUB_REPO", ""))

st.set_page_config(
    page_title="Tử Vi Đẩu Số - Hệ Thống Luận Giải Toàn Diện & Chuẩn Xác",
    page_icon="☯️",
    layout="wide",
)

# Thư mục lưu cache sách local
CACHE_FILE = Path(__file__).parent / "books_cache.json"


# --- HÀM TƯƠNG TÁC GITHUB (LƯU ÁNH LÁ SỐ) ---
def upload_to_github(uploaded_file):
    """Đẩy file ảnh lá số trực tiếp lên GitHub Repository."""
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


# --- HÀM XỬ LÝ DỮ LIỆU SÁCH & CẮT 12 CUNG ---
@st.cache_data(ttl=3600)
def load_cached_data():
    """Tải và cache dữ liệu sách Tử Vi từ tệp books_cache.json"""
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
    """Đọc file PDF mới upload và nối nội dung vào books_cache.json"""
    try:
        reader = PdfReader(pdf_file)
        extracted_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"

        if not extracted_text.strip():
            return False, "Không thể trích xuất văn bản (Có thể PDF là dạng ảnh quét)."

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
        return True, f"Đã thêm thành công sách '{pdf_file.name}' vào kho dữ liệu!"
    except Exception as e:
        return False, f"Lỗi xử lý file PDF: {e}"


def crop_12_cung_overlap(
    img, top_cut=10, bottom_cut=5, side_cut=2, overlap_px=20
):
    """Cắt 12 Cung mở rộng ranh giới để giữ trọn vạch Tuần/Triệt."""
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


# --- GIAO DIỆN CHÍNH ---
st.title("☯️ TỬ VI ĐẨU SỐ - HỆ THỐNG LUẬN GIẢI CHUẨN XÁC & TOÀN DIỆN")

# --- THANH BÊN (SIDEBAR): QUẢN LÝ SÁCH PDF ---
with st.sidebar:
    st.header("📚 Kho Dữ Liệu Sách Tử Vi (PDF)")
    st.info(f"📍 **Vị trí lưu cache:**\n`{CACHE_FILE.resolve()}`")

    if not CACHE_FILE.exists():
        if st.button("➕ Tạo file kho sách mới"):
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False)
            st.rerun()

    uploaded_pdf = st.file_uploader(
        "Tải lên file PDF sách Tử Vi:", type=["pdf"]
    )
    if uploaded_pdf is not None:
        if st.button("📥 Nạp Sách Vào Kho Dữ Liệu", use_container_width=True):
            with st.spinner("Đang trích xuất văn bản từ PDF..."):
                success, msg = append_pdf_to_cache(uploaded_pdf)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)

    pdf_text_context = load_cached_data()
    st.markdown("---")
    st.metric("Dung lượng Kho Sách Cache", f"{len(pdf_text_context):,} ký tự")

st.markdown("---")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📸 Upload Lá Số Tử Vi")
    uploaded_file = st.file_uploader(
        "Tải lên ảnh lá số:", type=["jpg", "jpeg", "png", "webp"]
    )

    cropped_dict = {}
    if uploaded_file:
        # Tự động lưu lên GitHub nếu là file mới
        if st.session_state.get("last_uploaded") != uploaded_file.name:
            with st.spinner("🐙 Đang lưu lá số vào GitHub Repository..."):
                gh_success, gh_msg = upload_to_github(uploaded_file)
                if gh_success:
                    st.toast("🐙 Đã lưu thành công lá số lên GitHub!", icon="✅")
                else:
                    st.warning(f"⚠️ Lỗi lưu GitHub: {gh_msg}")

            st.session_state.last_uploaded = uploaded_file.name

        image = Image.open(uploaded_file).convert("RGB")

        st.markdown("⚙️ **Căn chỉnh lề & Vạch ngăn Tuần/Triệt:**")
        top_val = st.slider("⬆️ Bỏ lề TRÊN (%):", 0, 25, 10, 1)
        bottom_val = st.slider("⬇️ Bỏ lề DƯỚI (%):", 0, 25, 5, 1)
        side_val = st.slider("↔️ Bỏ lề TRÁI/PHẢI (%):", 0, 15, 2, 1)
        overlap_val = st.slider("🔍 Vùng phủ vạch ngăn (Px):", 5, 40, 20, 5)

        st.image(image, caption="Ảnh Lá Số Gốc", use_container_width=True)
        cropped_dict = crop_12_cung_overlap(
            image, top_val, bottom_val, side_val, overlap_val
        )

        with st.expander("🔍 KIỂM TRA MẢNH CẮT 12 CUNG"):
            cols = st.columns(3)
            idx = 0
            for name, crop_img in cropped_dict.items():
                cols[idx % 3].image(
                    crop_img, caption=f"Cung {name}", use_container_width=True
                )
                idx += 1

    selected_year = st.number_input("Năm luận Tiểu Hạn:", 1950, 2050, 2026, 1)
    user_note = st.text_area(
        "Yêu cầu thêm:",
        value=(
            "Yêu cầu AI phân tích chi tiết, minh bạch quy tắc và không bỏ sót bất"
            " kỳ cung hay tháng nào."
        ),
    )

    btn_analyze = st.button(
        "🔮 BẮT ĐẦU LUẬN GIẢI CHUẨN XÁC", type="primary", use_container_width=True
    )

with col2:
    st.subheader("📜 Bản Luận Giải Chi Tiết")

    if "analysis_result" not in st.session_state:
        st.session_state.analysis_result = None

    if btn_analyze:
        if not uploaded_file:
            st.warning("⚠️ Vui lòng tải lên ảnh lá số trước!")
        elif not API_KEY:
            st.error(
                "❌ Chưa phát hiện Gemini API Key! Vui lòng thêm `GEMINI_API_KEY` vào"
                " mục Secrets."
            )
        else:
            with st.spinner(
                "⚡ AI đang phân tích toàn bộ 12 Cung & Lập Bản Luận Giải Chi"
                " Tiết..."
            ):
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

                    max_retries = 3
                    response = None
                    for attempt in range(max_retries):
                        try:
                            response = client.models.generate_content(
                                model="gemini-3.6-flash",
                                contents=content_payload,
                            )
                            break
                        except Exception as err:
                            if "429" in str(err) and attempt < max_retries - 1:
                                time.sleep(5 * (attempt + 1))
                            else:
                                raise err

                    if response:
                        st.session_state.analysis_result = response.text
                        st.success(
                            f"✅ Đã hoàn thành bản luận giải toàn diện & minh bạch quy tắc"
                            f" cho năm {selected_year}!"
                        )

                except Exception as e:
                    st.error(f"❌ Lỗi khi xử lý API: {e}")

    if st.session_state.analysis_result:
        st.markdown(st.session_state.analysis_result)
