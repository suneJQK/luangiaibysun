# -*- coding: utf-8 -*-
"""Local OCR pipeline for Tử Vi charts.

The image is processed locally with EasyOCR. Only structured OCR text is
returned to the LLM; the original image and cropped images are never sent to
Gemini.
"""
from __future__ import annotations

import re
from typing import Dict, List

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

import streamlit as st
import easyocr

GRID_MAP = {
    "Hợi": (3, 3), "Tý": (2, 3), "Sửu": (1, 3), "Dần": (0, 3),
    "Mão": (0, 2), "Thìn": (0, 1), "Tị": (0, 0), "Ngọ": (1, 0),
    "Mùi": (2, 0), "Thân": (3, 0), "Dậu": (3, 1), "Tuất": (3, 2),
}

@st.cache_resource(show_spinner="Đang tải mô hình OCR Python...")
def load_ocr_reader():
    return easyocr.Reader(["vi", "en"], gpu=False, verbose=False)


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
            result[name] = img.crop((left, top, right, bottom))
    return result


def _preprocess(image: Image.Image) -> np.ndarray:
    image = image.convert("RGB")
    image = ImageOps.grayscale(image)
    image = ImageEnhance.Contrast(image).enhance(1.35)
    image = ImageEnhance.Sharpness(image).enhance(1.25)
    image = ImageOps.autocontrast(image)
    return np.asarray(image)


def _normalize_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text_from_cungs(cropped: Dict[str, Image.Image]) -> Dict[str, List[str]]:
    reader = load_ocr_reader()
    extracted: Dict[str, List[str]] = {}
    for cung, image in cropped.items():
        arr = _preprocess(image)
        results = reader.readtext(
            arr,
            detail=1,
            paragraph=False,
            decoder="greedy",
            text_threshold=0.55,
            low_text=0.25,
            link_threshold=0.25,
            mag_ratio=1.5,
        )
        rows = []
        for item in results:
            if len(item) >= 3:
                text = _normalize_text(str(item[1]))
                try:
                    confidence = float(item[2])
                except Exception:
                    confidence = 0.0
                if text and confidence >= 0.20:
                    rows.append((text, round(confidence, 3)))
        rows.sort(key=lambda x: x[0])
        extracted[cung] = [f"{text} [conf={confidence}]" for text, confidence in rows]
    return extracted


def build_processed_dataset(extracted: Dict[str, List[str]]) -> Dict[str, object]:
    """Create the only image-derived payload allowed to reach the LLM."""
    return {
        "source": "python_easyocr",
        "image_sent_to_llm": False,
        "cung_count": len(extracted),
        "cungs": extracted,
    }
