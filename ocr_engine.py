# -*- coding: utf-8 -*-
"""Local Python image scanner for Tử Vi charts.
The scanner never sends image data to Gemini. It uses multiple preprocessing passes.
"""
from __future__ import annotations
import re
from typing import Dict, List, Tuple
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import easyocr
import streamlit as st
GRID_MAP={"Hợi":(3,3),"Tý":(2,3),"Sửu":(1,3),"Dần":(0,3),"Mão":(0,2),"Thìn":(0,1),"Tị":(0,0),"Ngọ":(1,0),"Mùi":(2,0),"Thân":(3,0),"Dậu":(3,1),"Tuất":(3,2)}
MAX_SIDE=2200
@st.cache_resource(show_spinner="Đang tải bộ quét hình ảnh lần đầu...")
def load_ocr_reader(): return easyocr.Reader(["vi","en"],gpu=False,verbose=False,model_storage_directory=".easyocr")
def _resize(image):
    image=image.convert("RGB"); w,h=image.size; scale=min(1.0,MAX_SIDE/max(w,h))
    return image if scale>=1 else image.resize((max(1,int(w*scale)),max(1,int(h*scale))),Image.Resampling.LANCZOS)
def crop_12_cung(img,top_cut=0,bottom_cut=3,side_cut=0,overlap_px=20):
    if img is None:return {}
    width,height=img.size; left=width*side_cut/100; right=width*(1-side_cut/100); top=height*top_cut/100; bottom=height*(1-bottom_cut/100); ws,hs=max(1,right-left)/4,max(1,bottom-top)/4; out={}
    for name,(col,row) in GRID_MAP.items():
        l=max(0,int(left+col*ws-overlap_px)); t=max(0,int(top+row*hs-overlap_px)); r=min(width,int(left+(col+1)*ws+overlap_px)); b=min(height,int(top+(row+1)*hs+overlap_px))
        if r>l and b>t: out[name]=_resize(img.crop((l,t,r,b)))
    return out
def _variants(image):
    gray=ImageOps.autocontrast(ImageOps.grayscale(_resize(image))); contrast=ImageEnhance.Contrast(gray).enhance(1.35); sharp=ImageEnhance.Sharpness(contrast).enhance(1.25); denoise=sharp.filter(ImageFilter.MedianFilter(size=3)); return [np.asarray(contrast),np.asarray(denoise)]
def _clean(text): return re.sub(r"\s+"," ",re.sub(r"[ \t]+"," ",text)).strip()
def _read_one(image)->List[Tuple[str,float]]:
    reader=load_ocr_reader(); candidates={}
    for arr in _variants(image):
        for item in reader.readtext(arr,detail=1,paragraph=False,decoder="greedy",text_threshold=0.50,low_text=0.20,link_threshold=0.20,mag_ratio=1.0,batch_size=1):
            if len(item)<3: continue
            text=_clean(str(item[1]))
            try: conf=float(item[2])
            except Exception: conf=0.0
            if text and conf>=0.20: candidates[text.lower()]=max(candidates.get(text.lower(),(text,0.0)),(text,conf),key=lambda x:x[1])
    return sorted(candidates.values(),key=lambda x:-x[1])
def extract_text_from_cungs(cropped:Dict[str,Image.Image])->Dict[str,List[str]]:
    out={}; progress=st.progress(0,text="Đang quét hình ảnh 12 cung..."); total=max(1,len(cropped))
    for i,(cung,image) in enumerate(cropped.items(),1):
        out[cung]=[f"{text} [conf={conf:.3f}]" for text,conf in _read_one(image)]; progress.progress(i/total,text=f"Đang quét {i}/{total}: {cung}")
    progress.empty(); return out
def extract_chart_text(image,cropped): return {"source":"python_easyocr","image_sent_to_llm":False,"header_text":[],"cung_count":len(cropped),"cungs":extract_text_from_cungs(cropped)}
