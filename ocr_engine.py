# -*- coding: utf-8 -*-
"""Local Python OCR for Tử Vi charts.

Performance-safe pipeline: one cached EasyOCR reader, resized crops, and no
OCR pass over the full original image. Gemini never receives image data.
"""
from __future__ import annotations

import re
from typing import Dict, List

import numpy as np
from PIL import Image, ImageEnhance, ImageOps
import easyocr
import streamlit as st

GRID_MAP = {
    "Hợi": (3, 3), "Tý": (2, 3), "Sửu": (1, 3), "Dần": (0, 3),
    "Mão": (0, 2), "Thìn": (0, 1), "Tị": (0, 0), "Ngọ": (1, 0),
    "Mùi": (2, 0), "Thân": (3, 0), "Dậu": (3, 1), "Tuất": (3, 2),
}

MAX_SIDE = 1600


@st.cache_resource(show_spinner="Đang tải mô hình OCR Python lần đầu...")
def load_ocr_reader():
    # Model is loaded exactly once per Streamlit process.
    return easyocr.Reader(["vi", "en"], gpu=False, verbose=False, model_storage_directory=".easyocr")


def _resize(image: Image.Image) -> Image.Image:
    image = image.convert("RGB")
    w, h = image.size
    scale = min(1.0, MAX_SIDE / max(w, h))
    if scale < 1.0:
        image = image.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
    return image


def crop_12_cung(img: Image.Image, top_cut=0, bottom_cut=3, side_cut=0, overlap_px=15):
    if img is None:
        return {}
    width, height = img.size
    left_start = width * side_cut / 100.0
    right_end = width * (1.0 - side_cut / 100.0)
    top_start = height * top_cut / 100.0
    bottom_end = height * (1.0 - bottom_cut / 100.0)
    w_step = max(1.0, right_end - left_start) / 4.0
    h_step = max(1.0, bottom_end - top_start) / 4.0
    result = {}
    for name, (col, row) in GRID_MAP.items():
        left = max(0, int(left_start + col * w_step - overlap_px))
        top = max(0, int(top_start + row * h_step - overlap_px))
        right = min(width, int(left_start + (col + 1) * w_step + overlap_px))
        bottom = min(height, int(top_start + (row + 1) * h_step + overlap_px))
        if right > left and bottom > top:
            result[name] = _resize(img.crop((left, top, right, bottom)))
    return result


def _preprocess(image: Image.Image) -> np.ndarray:
    image = _resize(image)
    image = ImageOps.grayscale(image)
    image = ImageEnhance.Contrast(image).enhance(1.25)
    image = ImageEnhance.Sharpness(image).enhance(1.15)
    return np.asarray(ImageOps.autocontrast(image))


def _normalize_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _read(image: Image.Image) -> List[str]:
    reader = load_ocr_reader()
    rows = []
    for item in reader.readtext(
        _preprocess(image),
        detail=1,
        paragraph=False,
        decoder="greedy",
        text_threshold=0.60,
        low_text=0.30,
        link_threshold=0.30,
        mag_ratio=1.0,
        batch_size=1,
    ):
        if len(item) < 3:
            continue
        text = _normalize_text(str(item[1]))
        try:
            confidence = float(item[2])
        except Exception:
            confidence = 0.0
        if text and confidence >= 0.25:
            rows.append((text, round(confidence, 3)))
    return [f"{text} [conf={confidence}]" for text, confidence in rows]


def extract_text_from_cungs(cropped: Dict[str, Image.Image]) -> Dict[str, List[str]]:
    """OCR only the 12 cropped cells; never OCR the full source image."""
    reader = load_ocr_reader()
    out: Dict[str, List[str]] = {}
    progress = st.progress(0, text="Đang OCR 12 cung...")
    total = max(1, len(cropped))
    for index, (cung, image) in enumerate(cropped.items(), start=1):
        out[cung] = _read(image)
        progress.progress(index / total, text=f"OCR {index}/{total}: {cung}")
    progress.empty()
    return out


def extract_chart_text(image: Image.Image, cropped: Dict[str, Image.Image]) -> Dict[str, object]:
    """Return only JSON-safe OCR data. The original image is discarded."""
    cungs = extract_text_from_cungs(cropped)
    return {
        "source": "python_easyocr",
        "image_sent_to_llm": False,
        "header_text": [],
        "cung_count": len(cungs),
        "cungs": cungs,
    }
