# -*- coding: utf-8 -*-
"""Position-aware OCR for Vietnamese Tử Vi charts.

The chart is treated as a 4x4 outer ring around a central square.  Cropping is
controlled by an explicit ROI (x/y percentages) so the user can align the grid
before OCR.  Automatic line detection is optional because text in a chart can
otherwise be mistaken for a border.  OCR keeps text + confidence + normalized
bbox; downstream Python decides what each token means.
"""
from __future__ import annotations
import re
from typing import Dict, List, Tuple
import cv2
import numpy as np
from PIL import Image
import easyocr
import streamlit as st

GRID_MAP = {
    "Hợi": (3, 3), "Tý": (2, 3), "Sửu": (1, 3), "Dần": (0, 3),
    "Mão": (0, 2), "Thìn": (0, 1), "Tỵ": (0, 0), "Ngọ": (1, 0),
    "Mùi": (2, 0), "Thân": (3, 0), "Dậu": (3, 1), "Tuất": (3, 2),
}
MAX_SIDE = 3600
UPSCALE = 2.7


@st.cache_resource(show_spinner="Đang tải bộ quét hình ảnh lần đầu...")
def load_ocr_reader():
    return easyocr.Reader(["vi", "en"], gpu=False, verbose=False, model_storage_directory=".easyocr")


def _resize_full(image: Image.Image) -> Image.Image:
    image = image.convert("RGB")
    w, h = image.size
    scale = min(1.0, MAX_SIDE / max(w, h))
    return image if scale >= 1 else image.resize(
        (max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS
    )


def _line_positions(img: Image.Image) -> Tuple[List[int], List[int]]:
    """Detect long chart borders with Hough; reject short text strokes."""
    a = np.asarray(img.convert("RGB"))
    gray = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    h, w = gray.shape
    min_v = max(80, int(h * 0.45))
    min_h = max(80, int(w * 0.45))
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80,
                            minLineLength=min(min_v, min_h), maxLineGap=12)
    xs, ys = [0, w], [0, h]
    if lines is None:
        return xs, ys
    for line in lines[:, 0]:
        x1, y1, x2, y2 = map(int, line)
        dx, dy = abs(x2 - x1), abs(y2 - y1)
        if dy > max(8, dx * 5) and dy >= min_v:
            xs.append(int(round((x1 + x2) / 2)))
        elif dx > max(8, dy * 5) and dx >= min_h:
            ys.append(int(round((y1 + y2) / 2)))

    def cluster(values, tolerance=8):
        values = sorted(values)
        groups = []
        for v in values:
            if not groups or abs(v - groups[-1][-1]) > tolerance:
                groups.append([v])
            else:
                groups[-1].append(v)
        return [int(round(sum(g) / len(g))) for g in groups]

    return cluster(xs), cluster(ys)


def _quarter_edges(w: int, h: int) -> Tuple[List[int], List[int]]:
    return [0, int(round(w * .25)), int(round(w * .5)), int(round(w * .75)), w], \
           [0, int(round(h * .25)), int(round(h * .5)), int(round(h * .75)), h]


def _valid_edges(xs: List[int], ys: List[int], w: int, h: int) -> bool:
    if len(xs) != 5 or len(ys) != 5:
        return False
    xs, ys = sorted(xs), sorted(ys)
    # A 4x4 chart must have reasonably even cells. This prevents a text line
    # detected near a border from becoming a false grid boundary.
    xg = np.diff(xs); yg = np.diff(ys)
    return (
        min(xg) >= w * .12 and max(xg) <= w * .38 and
        min(yg) >= h * .12 and max(yg) <= h * .38
    )


def crop_12_cung(
    img,
    top_cut=0,
    bottom_cut=0,
    side_cut=0,
    overlap_px=0,
    *,
    x_start=None,
    y_start=None,
    x_end=None,
    y_end=None,
    auto_grid=False,
):
    """Crop the 12 outer palaces.

    New UI uses x_start/y_start/x_end/y_end as percentages of the full image.
    The old top_cut/bottom_cut/side_cut arguments remain supported for backward
    compatibility. By default the selected ROI is divided into equal quarters;
    this is safer than guessing borders from text. auto_grid=True enables Hough
    line detection after the ROI has been selected.
    """
    if img is None:
        return {}
    image = _resize_full(img)
    width, height = image.size

    if x_start is None:
        x_start = side_cut
    if x_end is None:
        x_end = 100 - side_cut
    if y_start is None:
        y_start = top_cut
    if y_end is None:
        y_end = 100 - bottom_cut

    x_start = float(max(0, min(99.9, x_start)))
    y_start = float(max(0, min(99.9, y_start)))
    x_end = float(max(x_start + 0.1, min(100, x_end)))
    y_end = float(max(y_start + 0.1, min(100, y_end)))

    left = int(round(width * x_start / 100))
    top = int(round(height * y_start / 100))
    right = int(round(width * x_end / 100))
    bottom = int(round(height * y_end / 100))
    work = image.crop((left, top, right, bottom))
    w, h = work.size

    if auto_grid:
        xs, ys = _line_positions(work)
        if not _valid_edges(xs, ys, w, h):
            xs, ys = _quarter_edges(w, h)
    else:
        xs, ys = _quarter_edges(w, h)

    out = {}
    for name, (col, row) in GRID_MAP.items():
        l = max(0, xs[col] - int(overlap_px))
        t = max(0, ys[row] - int(overlap_px))
        r = min(w, xs[col + 1] + int(overlap_px))
        b = min(h, ys[row + 1] + int(overlap_px))
        if r > l and b > t:
            out[name] = work.crop((l, t, r, b))
    return out


def get_grid_preview(img, *, x_start=0, y_start=0, x_end=100, y_end=100, auto_grid=False):
    """Return ROI and grid coordinates in original-image pixels for UI preview."""
    image = _resize_full(img)
    width, height = image.size
    left = int(round(width * max(0, min(100, x_start)) / 100))
    top = int(round(height * max(0, min(100, y_start)) / 100))
    right = int(round(width * max(0, min(100, x_end)) / 100))
    bottom = int(round(height * max(0, min(100, y_end)) / 100))
    work = image.crop((left, top, right, bottom))
    w, h = work.size
    if auto_grid:
        xs, ys = _line_positions(work)
        if not _valid_edges(xs, ys, w, h):
            xs, ys = _quarter_edges(w, h)
    else:
        xs, ys = _quarter_edges(w, h)
    return work, xs, ys


def _upscale(image):
    w, h = image.size
    return image.resize((max(1, int(w * UPSCALE)), max(1, int(h * UPSCALE))), Image.Resampling.LANCZOS)


def _variants(image):
    rgb = np.asarray(_upscale(image).convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8)).apply(gray)
    blur = cv2.GaussianBlur(clahe, (0, 0), 1.0)
    sharp = cv2.addWeighted(clahe, 1.65, blur, -0.65, 0)
    adaptive = cv2.adaptiveThreshold(sharp, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 31, 7)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    sat = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(hsv[:, :, 1])
    dark = cv2.inRange(gray, 0, 150)
    dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    return [gray, sharp, adaptive, sat, dark]


def _clean(text):
    return re.sub(r"\s+", " ", str(text)).strip()


def _key(text):
    return re.sub(r"[^0-9a-zA-ZÀ-ỹĐđ]+", "", text).lower()


def _read_one(image) -> List[dict]:
    reader = load_ocr_reader()
    candidates = {}
    for arr in _variants(image):
        for item in reader.readtext(
            arr, detail=1, paragraph=False, decoder="greedy",
            text_threshold=0.28, low_text=0.08, link_threshold=0.08,
            mag_ratio=1.0, contrast_ths=0.04, adjust_contrast=0.75,
            width_ths=0.55, height_ths=0.55, add_margin=0.04,
            min_size=5, batch_size=1
        ):
            if len(item) < 3:
                continue
            bbox, text, conf = item[0], _clean(item[1]), float(item[2])
            if not text or conf < 0.08:
                continue
            ah, aw = arr.shape[:2]
            nb = [[round(float(x) / max(1, aw), 6), round(float(y) / max(1, ah), 6)] for x, y in bbox]
            key = _key(text)
            if not key:
                continue
            candidate = {"text": text, "confidence": round(conf, 4), "bbox": nb}
            old = candidates.get(key)
            if old is None or conf > old["confidence"]:
                candidates[key] = candidate
    return sorted(
        candidates.values(),
        key=lambda x: (
            sum(p[1] for p in x["bbox"]) / len(x["bbox"]),
            sum(p[0] for p in x["bbox"]) / len(x["bbox"]),
        ),
    )


def extract_text_from_cungs(cropped: Dict[str, Image.Image]) -> Dict[str, List[dict]]:
    out = {}
    progress = st.progress(0, text="Đang quét hình ảnh 12 cung...")
    total = max(1, len(cropped))
    for i, (cung, image) in enumerate(cropped.items(), 1):
        out[cung] = _read_one(image)
        progress.progress(i / total, text=f"Đang quét {i}/{total}: {cung}")
    progress.empty()
    return out


def extract_chart_text(image, cropped):
    return {
        "source": "python_easyocr_tuvi_layout_v3",
        "image_sent_to_llm": False,
        "header_text": [],
        "cung_count": len(cropped),
        "cungs": extract_text_from_cungs(cropped),
    }
