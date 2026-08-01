#!/usr/bin/env python3
import json
import os
from pathlib import Path
import streamlit as st
from google import genai
from PIL import Image
from pypdf import PdfReader

# --- CẤU HÌNH BẢO MẬT API KEY ---
API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))

st.set_page_config(
    page_title="Tử Vi Đẩu Số - Hệ Thống Luận Giải Toàn Diện & Khoa Học",
    page_icon="☯️",
    layout="wide"
)

# Thư mục lưu cache sách
CACHE_FILE = Path(__file__).parent / "books_cache.json"

# --- HÀM XỬ LÝ DỮ LIỆU SÁCH & PDF ---
def load_cached_data():
    """Tải dữ liệu sách Tử Vi từ tệp books_cache.json"""
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
            
        return True, f"Đã thêm thành công sách '{pdf_file.name}' vào kho dữ liệu!"
    except Exception as e:
        return False, f"Lỗi xử lý file PDF: {e}"

def crop_12_cung_overlap(img, top_cut=10, bottom_cut=5, side_cut=2, overlap_px=20):
    """Cắt 12 Cung mở rộng ranh giới để giữ trọn Tuần/Triệt."""
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
        "Mùi": (2, 0), "Thân": (3, 0), "Dậu": (3, 1), "Tuất": (3, 2)
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
st.title("☯️ TỬ VI ĐẨU SỐ - BỘ QUY TẮC LUẬN GIẢI CHUẨN XÁC & HOÀN CHỈNH")

# --- THANH BÊN (SIDEBAR): QUẢN LÝ SÁCH PDF ---
with st.sidebar:
    st.header("📚 Kho Dữ Liệu Sách Tử Vi (PDF)")
    st.info(f"📍 **Vị trí lưu cache:**\n`{CACHE_FILE.resolve()}`")

    if not CACHE_FILE.exists():
        if st.button("➕ Tạo file kho sách mới"):
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False)
            st.rerun()

    uploaded_pdf = st.file_uploader("Tải lên file PDF sách Tử Vi:", type=["pdf"])
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
    uploaded_file = st.file_uploader("Tải lên ảnh lá số:", type=["jpg", "jpeg", "png", "webp"])
    
    cropped_dict = {}
    if uploaded_file:
        image = Image.open(uploaded_file)
        
        st.markdown("⚙️ **Căn chỉnh lề & Vạch ngăn Tuần/Triệt:**")
        top_val = st.slider("⬆️ Bỏ lề TRÊN (%):", 0, 25, 10, 1)
        bottom_val = st.slider("⬇️ Bỏ lề DƯỚI (%):", 0, 25, 5, 1)
        side_val = st.slider("↔️ Bỏ lề TRÁI/PHẢI (%):", 0, 15, 2, 1)
        overlap_val = st.slider("🔍 Vùng phủ vạch ngăn (Px):", 5, 40, 20, 5)
        
        st.image(image, caption="Ảnh Lá Số Gốc", use_container_width=True)
        cropped_dict = crop_12_cung_overlap(image, top_val, bottom_val, side_val, overlap_val)
        
        with st.expander("🔍 KIỂM TRA MẢNH CẮT 12 CUNG"):
            cols = st.columns(3)
            idx = 0
            for name, crop_img in cropped_dict.items():
                cols[idx % 3].image(crop_img, caption=f"Cung {name}", use_container_width=True)
                idx += 1

    selected_year = st.number_input("Năm luận Tiểu Hạn:", 1950, 2050, 2026, 1)
    user_note = st.text_area("Yêu cầu thêm:", value="Áp dụng nghiêm ngặt Bộ Quy Tắc Luận Giải Hoàn Chỉnh, quét sạch 100% phụ tinh, đánh giá hành Tam hợp cục và tương tác liên cung.")

    btn_analyze = st.button("🔮 BẮT ĐẦU LUẬN GIẢI THEO BỘ QUY TẮC HOÀN CHỈNH", type="primary", use_container_width=True)

with col2:
    st.subheader("📜 Bản Luận Giải Chi Tiết")

    if "analysis_result" not in st.session_state:
        st.session_state.analysis_result = None

    if btn_analyze:
        if not uploaded_file:
            st.warning("⚠️ Vui lòng tải lên ảnh lá số trước!")
        elif not API_KEY:
            st.error("❌ Chưa phát hiện Gemini API Key! Vui lòng thêm `GEMINI_API_KEY` vào mục Secrets.")
        else:
            with st.spinner("⚡ Đang quét lá số, áp dụng Bộ Quy Tắc Luận Tử Vi Hoàn Chỉnh..."):
                
                truncated_context = pdf_text_context[:25000] if pdf_text_context else "Dùng kiến thức Phú Tử Vi Chuẩn từ các bộ sách Nam Phái, Bắc Phái, Trung Châu Phái."
                
                prompt = f"""
Bạn là Chuyên gia Tử Vi Đẩu Số cao cấp với hơn 30 năm kinh nghiệm.
Dưới đây là **ẢNH LÁ SỐ TỬ VI TOÀN CẢNH** cùng các **ẢNH CẮT CHI TIẾT CỦA 12 CUNG (ĐIỆN)**.

====================================================================
📜 BỘ QUY TẮC LUẬN GIẢI TỬ VI HOÀN CHỈNH (NGHIÊM CẤM VI PHẠM)
====================================================================

📌 QUY TẮC 1: TỔNG QUAN NỀN TẢNG (MỆNH BÀN & ÂM DƯƠNG NGŨ HÀNH)
1. Xác định **Âm Dương Thuận/Nghịch Lý**:
   - Nam Dương / Nữ Âm (Dương Nam, Âm Nữ) đóng ở Cung Dương = Thuận Lý (Dễ thành công, mưu sự thuận lợi).
   - Âm Nam / Dương Nữ đóng lệch hoặc Âm Dương Trái Cửa = Nghịch Lý (Cuộc đời phải nỗ lực vượt khó gấp đôi).
2. Tương quan **Mệnh & Cục**:
   - Cục Sinh Mệnh > Mệnh Cục Tương Hòa > Mệnh Khắc Cục > Cục Khắc Mệnh (Xếp thứ tự độ thuận lợi cuộc đời).
3. **Mệnh Chủ & Thân Chủ**: Xác định vai trò quản hộ và giai đoạn phát huy tác dụng.
4. **Vị Trí Cung Thân**: Đóng ở Mệnh (Tự lực), Thê/Phu (Nhờ/phụ thuộc người phối ngẫu), Tài (Trọng tiền), Quan (Trọng sự nghiệp), Di (Sướng ngoài đường/hay đi), Phúc Đức (Hưởng gia phúc/gánh nghĩa vụ họ hàng).

--------------------------------------------------------------------
📌 QUY TẮC 2: QUY TẮC TAM HỢP (TAM PHƯƠNG) & NGŨ HÀNH CỤC
Mỗi cung đều nằm trong 1 trong 4 Bộ Tam Hợp Địa Chi. BẮT BUỘC xác định Ngũ Hành Cục của Tam Hợp và so sánh với Ngũ Hành Bản Mệnh:
- **Hợi - Mão - Mùi**: Thuộc **Mộc Cục**.
- **Tị - Dậu - Sửu**: Thuộc **Kim Cục**.
- **Dần - Ngọ - Tuất**: Thuộc **Hỏa Cục**.
- **Thân - Tý - Thìn**: Thuộc **Thủy Cục**.

👉 **Tương Tác Ngũ Hành**:
- Tam Hợp Cung **Sinh** Bản Mệnh: Đắc lực, hoàn cảnh nâng đỡ.
- Tam Hợp Cung **Đồng Hành** Bản Mệnh: Được thế, vững vàng.
- Bản Mệnh **Khắc** Tam Hợp Cung: Phải lao tâm khổ tứ vất vả mới đạt được.
- Tam Hợp Cung **Khắc** Bản Mệnh: Bị hoàn cảnh đè nén, hay gặp trở lực.
- Bản Mệnh **Sinh** Tam Hợp Cung (Tự xuất lực): Dễ bị hao tổn năng lượng, xả thân vì công việc.

--------------------------------------------------------------------
📌 QUY TẮC 3: CẤU TRÚC TAM PHƯƠNG TỨ CHÍNH KHI LUẬN TỪNG CUNG
Khi luận giải bất kỳ cung nào trong 12 Cung, BẮT BUỘC thực hiện đủ 4 bước:
1. **Tọa Thủ**: Phân tích Chính tinh (Đắc/Miếu/Vượng/Hãm) và TOÀN BỘ Phụ tinh nằm trực tiếp tại cung.
2. **Xung Chiếu (Tứ Chính)**: Xét cung đối diện chiếu trực diện sang (Mệnh - Di, Thê - Quan, Tài - Phúc, Tử - Điền, Nô - Huynh, Tật - Phụ).
3. **Tam Hợp (Tam Phương)**: Xét 2 cung hội tụ tạo thế tam hợp địa chi, phân tích các sao chiếu về và tác dụng lực đẩy/kéo.
4. **Giáp Cung**: Phân tích thế kẹp từ 2 cung liền kề (Giáp Lộc Tồn, Giáp Kình Đà, Giáp Xương Khúc, Giáp Âm Dương, Giáp Không Kiếp...).

--------------------------------------------------------------------
📌 QUY TẮC 4: BẮT BUỘC QUÉT VÀ GIẢI MÃ 100% PHỤ TINH (KHÔNG BỎ SÓT NÀO)
Khi luận từng cung, KHÔNG CHỈ LIỆT KÊ TÊN SAO mà PHẢI GIẢI MÃ ĐẶC ĐIỂM & TÁC ĐỘNG THỰC TẾ của từng sao:
- **Tứ Hóa**: Hóa Lộc (May mắn, tiền bạc, duyên), Hóa Quyền (Chủ quyền, quyết đoán, danh vị), Hóa Khoa (Giải hạn, bằng cấp, danh tiếng), Hóa Kỵ (Cản trở, thị phi, ám ảnh, mắc kẹt).
- **Lục Cát Tinh & Trợ Tinh**: Văn Xương, Văn Khúc, Tả Phụ, Hữu Bật, Thiên Khôi, Thiên Việt, Ân Quang, Thiên Quý, Long Trì, Phượng Các, Tam Thai, Bát Tọa, Phong Cáo, Quốc Ấn, Thiên Phúc, Thiên Quan, Đào Hoa, Hồng Loan, Thiên Hỷ.
- **Lục Sát Tinh**: Kình Dương (Chung đụng mổ xẻ, va chạm), Đà La (Kéo dài, âm thầm bế tắc), Hỏa Tinh, Linh Tinh (Nóng nảy, bất ngờ, biến cố phát nhanh), Địa Không, Địa Kiếp (Bất ngờ mất mát, phá vỡ quy chuẩn, rủi ro lớn nhưng đột phá).
- **Bại Tinh & Tạp Tinh**: Đại Hao, Tiểu Hao (Hao tốn, biến động tài chính/nhà cửa), Thiên Khốc, Thiên Hư (U buồn, tiếng khóc, hao sức), Kiếp Sát, Phá Toái, Thiên Không (Làm nhiều hưởng ít, ảo tưởng rồi sụp đổ), Cô Thần, Quả Tú (Cô đơn, khó tính), Phục Binh (Rình rập, nói sau lưng), Bệnh Phù, Tử Phù, Trực Phù (Hao tổn sức khỏe, chịu thiệt).
- **Vòng Thái Tuế (12 Sao)**: Thái Tuế, Thiếu Dương, Tang Môn, Thiếu Âm, Quan Phù, Tử Phù, Tuế Phá, Long Đức, Bạch Hổ, Phúc Đức, Điếu Khách, Trực Phù -> Đánh giá tư thế ứng xử đối với đời.
- **Vòng Tràng Sinh (12 Trạng Thái)**: Tràng Sinh, Mộc Dục, Quan Đới, Lâm Quan, Đế Vượng, Suy, Bệnh, Tử, Mộ, Tuyệt, Thai, Dưỡng -> Đánh giá nội lực sinh khí của cung.
- **Thần Sát Không Vong**: Tuần Trung Không Vong & Triệt Lộ Không Vong (Chủ về cản trở ban đầu/suốt đời, làm đảo ngược tính chất Cát/Hung của sao).

--------------------------------------------------------------------
📌 QUY TẮC 5: MÔ HÌNH GIÁP CUNG CHUẨN XÁC
- Cung MỆNH: Giáp Phụ Mẫu & Huynh Đệ.
- Cung PHỤ MẪU: Giáp Phúc Đức & Mệnh.
- Cung PHÚC ĐỨC: Giáp Điền Trạch & Phụ Mẫu.
- Cung ĐIỀN TRẠCH: Giáp Quan Lộc & Phúc Đức.
- Cung QUAN LỘC: Giáp Nô Bộc & Điền Trạch.
- Cung NÔ BỘC: Giáp Thiên Di & Quan Lộc.
- Cung THIÊN DI: Giáp Tật Ách & Nô Bộc.
- Cung TẬT ÁCH: Giáp Tài Bạch & Thiên Di.
- Cung TÀI BẠCH: Giáp Tử Tức & Tật Ách.
- Cung TỬ TỨC: Giáp Phu Thê & Tài Bạch.
- Cung PHU THÊ: Giáp Huynh Đệ & Tử Tức.
- Cung HUYNH ĐỆ: Giáp Mệnh & Phu Thê.

--------------------------------------------------------------------
📖 DỮ LIỆU SÁCH / PHÚ TỬ VI TRÍCH XUẤT (PDF CONTEXT):
{truncated_context}

====================================================================
📋 QUY TRÌNH LUẬN GIẢI BẮT BUỘC THEO 8 GIAI ĐOẠN CHI TIẾT
====================================================================

#### GIAI ĐOẠN 1 – PHÂN TÍCH MỆNH BÀN & DIỆN MẠO CỐT LÕI
- Âm Dương, Ngũ Hành, Mệnh Cục, Mệnh Chủ, Thân Chủ, Vị trí Thân.
- Đánh giá Cục Tam Hợp của Cung Mệnh tương quan với Ngũ Hành Bản Mệnh.
- Luận chi tiết 5 mặt thực tế: (1) Diện mạo/Tướng hình, (2) Tính cách cốt lõi, (3) Phương thức hành sự, (4) Đường tình duyên, (5) Kiểu người hay gặp trong đời.
- Luận Tam Phương Tứ Chính Cung Mệnh + Giáp Cung Mệnh + Nêu ĐẶC ĐIỂM CHI TIẾT toàn bộ phụ tinh tại Mệnh.

#### GIAI ĐOẠN 2 – PHÂN TÍCH 12 CUNG (ĐỦ 100% PHỤ TINH, BỘ TAM HỢP & GIÁP CUNG)
Lần lượt 12 Cung: Mệnh, Phụ Mẫu, Phúc Đức, Điền Trạch, Quan Lộc, Nô Bộc, Thiên Di, Tật Ách, Tài Bạch, Tử Tức, Phu Thê, Huynh Đệ.
Mỗi cung BẮT BUỘC viết theo khung chuẩn:
1. **Chính Tinh & Phụ Tinh Tọa Thủ**: Liệt kê và GIẢI MÃ TÁC ĐỘNG thực tế của từng phụ tinh/tạp tinh.
2. **Cung Xung Chiếu (Tứ Chính)**: Các sao từ cung đối diện tác động sang.
3. **Cung Tam Hợp (Tam Phương)**: Xác định Cục Tam Hợp (Hợi-Mão-Mùi / Tị-Dậu-Sửu / Dần-Ngọ-Tuất / Thân-Tý-Thìn), Ngũ hành Tam hợp và các sao chiếu về.
4. **Giáp Cung**: Ảnh hưởng từ 2 cung liền kề.
5. **Tổng Luận 5 Mặt Thực Tế** + Chấm điểm (1-10) + Cách hóa giải góc tối.

#### GIAI ĐOẠN 3 – LUẬN ĐẠI VẬN 10 NĂM (Xếp hạng ★★★★★)
- Đánh giá Đại vận hiện tại và các Đại vận quan trọng trong đời. Tương quan Ngũ Hành Cung Đại Vận với Mệnh.

#### GIAI ĐOẠN 4 – LUẬN TIỂU HẠN NĂM {selected_year}
- Vị trí Cung Tiểu Hạn, Lưu Tứ Hóa (Lộc, Quyền, Khoa, Kỵ) và các Lưu Phụ Tinh (Lưu Thái Tuế, Lưu Kình, Lưu Đà, Lưu Mã, Lưu Lộc Tồn...).

#### GIAI ĐOẠN 5 – PHÂN TÍCH TƯƠNG TÁC TỔNG HỢP LIÊN CUNG
- Nhị hợp, Lục hại, Tương xung giữa các cung then chốt (Mệnh - Di, Tài - Phúc, Quan - Thê...).

#### GIAI ĐOẠN 6 – DỰ ĐOÁN XÁC SUẤT KHOA HỌC (Rất thấp -> Rất cao)
- Đánh giá xác suất rủi ro và cơ hội ở các mảng: Sức khỏe, Tài chính, Sự nghiệp, Hôn nhân.

#### GIAI ĐOẠN 7 – CÁC MỐC THỜI GIAN CẦN CHÚ Ý TRONG NĂM {selected_year}
- Luận giải chi tiết các tháng Âm lịch quan trọng.

#### GIAI ĐOẠN 8 – KHUYẾN NGHỊ VÀ HÓA GIẢI KHOA HỌC
- Định hướng hành động thực tế, phong thủy ứng xử và tinh thần để cải biến vận mệnh.

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

                    try:
                        response = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=content_payload
                        )
                    except Exception:
                        response = client.models.generate_content(
                            model='gemini-2.5-pro',
                            contents=content_payload
                        )

                    st.session_state.analysis_result = response.text
                    st.success(f"✅ Đã hoàn thành luận giải theo Bộ Quy Tắc Hoàn Chỉnh cho năm {selected_year}!")

                except Exception as e:
                    st.error(f"❌ Lỗi khi xử lý API: {e}")

    if st.session_state.analysis_result:
        st.markdown(st.session_state.analysis_result)