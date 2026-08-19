# OCR upgrade

Baseline: 62c53f2f320e08eca564a6723105eb5ccdd79859

The chart image is processed locally by `ocr_engine.py` using EasyOCR.
Gemini receives only `processed_data` JSON/text. `app.py` never places image
bytes or cropped images into Gemini request contents.

Pipeline:
1. Upload image to Streamlit.
2. Crop 12 cung locally.
3. Python/EasyOCR reads header and each cung.
4. Build JSON-safe OCR dataset with confidence values.
5. Gemini receives only that dataset plus engine/prompt/book text.
