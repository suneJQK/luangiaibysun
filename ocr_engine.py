# -*- coding: utf-8 -*-
"""Local Python OCR for Tử Vi charts.

The engine keeps text, confidence and normalized bounding boxes.  It uses
multiple image variants to improve recognition of small colored labels in
Tử Vi screenshots; no image is sent to the LLM.
"""
from __future__ import annotations
import re
from typing import Dict, List
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import easyocr
import streamlit as st

GRID_MAP={"Hợi":(3,3),"Tý":(2,3),"Sửu":(1,3),"Dần":(0,3),"Mão":(0,2),"Thìn":(0,1),"Tị":(0,0),"Ngọ":(1,0),"Mùi":(2,0),"Thân":(3,0),"Dậu":(3,1),"Tuất":(3,2)}
MAX_SIDE=3000

@st.cache_resource(show_spinner="Đang tải bộ quét hình ảnh lần đầu...")
def load_ocr_reader():
    return easyocr.Reader(["vi","en"],gpu=False,verbose=False,model_storage_directory=".easyocr")

def _resize(image):
    image=image.convert("RGB");w,h=image.size
    scale=min(1.0,MAX_SIDE/max(w,h))
    return image if scale>=1 else image.resize((max(1,int(w*scale)),max(1,int(h*scale))),Image.Resampling.LANCZOS)

def crop_12_cung(img,top_cut=0,bottom_cut=3,side_cut=0,overlap_px=28):
    if img is None:return {}
    width,height=img.size;left=width*side_cut/100;right=width*(1-side_cut/100);top=height*top_cut/100;bottom=height*(1-bottom_cut/100)
    ws,hs=max(1,right-left)/4,max(1,bottom-top)/4;out={}
    for name,(col,row) in GRID_MAP.items():
        l=max(0,int(left+col*ws-overlap_px));t=max(0,int(top+row*hs-overlap_px));r=min(width,int(left+(col+1)*ws+overlap_px));b=min(height,int(top+(row+1)*hs+overlap_px))
        if r>l and b>t:out[name]=_resize(img.crop((l,t,r,b)))
    return out

def _variants(image):
    """Return complementary variants: grayscale/contrast, threshold and sharp.
    Keeping several passes matters because the chart uses black/red/green text.
    """
    rgb=_resize(image)
    gray=ImageOps.grayscale(rgb)
    auto=ImageOps.autocontrast(gray)
    contrast=ImageEnhance.Contrast(auto).enhance(1.55)
    sharp=ImageEnhance.Sharpness(contrast).enhance(1.6)
    denoise=sharp.filter(ImageFilter.MedianFilter(size=3))
    # Otsu-like fixed threshold is intentionally conservative for screenshot text.
    arr=np.asarray(denoise)
    threshold=np.where(arr>178,255,0).astype(np.uint8)
    return [np.asarray(contrast),np.asarray(sharp),threshold]

def _clean(text):
    return re.sub(r"\s+"," ",str(text)).strip()

def _key(text):
    return re.sub(r"[^0-9a-zA-ZÀ-ỹĐđ]+","",text).lower()

def _read_one(image)->List[dict]:
    reader=load_ocr_reader();candidates={};w,h=image.size
    # More permissive first pass catches small labels; duplicate results are merged.
    for arr in _variants(image):
        for item in reader.readtext(arr,detail=1,paragraph=False,decoder="greedy",text_threshold=0.35,low_text=0.10,link_threshold=0.10,mag_ratio=1.35,batch_size=1):
            if len(item)<3:continue
            bbox,text,conf=item[0],_clean(item[1]),float(item[2])
            if not text or conf<0.12:continue
            nb=[[round(float(x)/max(1,w),6),round(float(y)/max(1,h),6)] for x,y in bbox]
            key=_key(text)
            if not key:continue
            candidate={"text":text,"confidence":round(conf,4),"bbox":nb}
            old=candidates.get(key)
            if old is None or conf>old["confidence"]:candidates[key]=candidate
    return sorted(candidates.values(),key=lambda x:(sum(p[1] for p in x["bbox"])/len(x["bbox"]),sum(p[0] for p in x["bbox"])/len(x["bbox"])))

def extract_text_from_cungs(cropped:Dict[str,Image.Image])->Dict[str,List[dict]]:
    out={};progress=st.progress(0,text="Đang quét hình ảnh 12 cung...");total=max(1,len(cropped))
    for i,(cung,image) in enumerate(cropped.items(),1):
        out[cung]=_read_one(image);progress.progress(i/total,text=f"Đang quét {i}/{total}: {cung}")
    progress.empty();return out

def extract_chart_text(image,cropped):
    return {"source":"python_easyocr_multiview","image_sent_to_llm":False,"header_text":[],"cung_count":len(cropped),"cungs":extract_text_from_cungs(cropped)}
