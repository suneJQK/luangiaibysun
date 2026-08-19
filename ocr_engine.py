# -*- coding: utf-8 -*-
"""Position-aware local OCR for Tử Vi charts.

The chart is a 4x4 outer-ring grid around a central square.  This engine is
optimized for that layout: each palace is upscaled before OCR and is scanned
with grayscale, dark-text and colour-text variants.  OCR output keeps bbox and
confidence; downstream Python code decides what is a star or metadata.  No
image is sent to an LLM.
"""
from __future__ import annotations
import re
from typing import Dict, List, Tuple
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import easyocr
import streamlit as st

GRID_MAP={"Hợi":(3,3),"Tý":(2,3),"Sửu":(1,3),"Dần":(0,3),"Mão":(0,2),"Thìn":(0,1),"Tỵ":(0,0),"Ngọ":(1,0),"Mùi":(2,0),"Thân":(3,0),"Dậu":(3,1),"Tuất":(3,2)}
MAX_SIDE=3600
UPSCALE=2.7

@st.cache_resource(show_spinner="Đang tải bộ quét hình ảnh lần đầu...")
def load_ocr_reader():
    return easyocr.Reader(["vi","en"],gpu=False,verbose=False,model_storage_directory=".easyocr")

def _resize_full(image):
    image=image.convert("RGB");w,h=image.size
    scale=min(1.0,MAX_SIDE/max(w,h))
    return image if scale>=1 else image.resize((max(1,int(w*scale)),max(1,int(h*scale))),Image.Resampling.LANCZOS)

def _detect_edges(img: Image.Image) -> Tuple[List[int],List[int]]:
    """Find the four near-quarter grid lines; fall back to equal quarters."""
    a=np.asarray(img.convert("RGB")); g=cv2.cvtColor(a,cv2.COLOR_RGB2GRAY)
    vd=(255-g).mean(axis=0); hd=(255-g).mean(axis=1)
    w,h=img.size
    xs=[0,w]; ys=[0,h]
    for expected,span,signal,target in [(w*.25,w*.07,vd,xs),(w*.50,w*.07,vd,xs),(w*.75,w*.07,vd,xs)]:
        lo=max(0,int(expected-span));hi=min(w-1,int(expected+span));target.append(int(lo+np.argmax(signal[lo:hi+1])))
    for expected,span,signal,target in [(h*.25,h*.07,hd,ys),(h*.50,h*.07,hd,ys),(h*.75,h*.07,hd,ys)]:
        lo=max(0,int(expected-span));hi=min(h-1,int(expected+span));target.append(int(lo+np.argmax(signal[lo:hi+1])))
    return sorted(set(xs)),sorted(set(ys))

def crop_12_cung(img,top_cut=0,bottom_cut=1,side_cut=0,overlap_px=8):
    if img is None:return {}
    img=_resize_full(img);width,height=img.size
    left=int(width*side_cut/100);right=int(width*(1-side_cut/100));top=int(height*top_cut/100);bottom=int(height*(1-bottom_cut/100))
    work=img.crop((left,top,right,bottom)); w,h=work.size
    xs,ys=_detect_edges(work)
    # Equal-quarter fallback is safer if a screenshot has decorative lines.
    if len(xs)!=5:xs=[0,int(w*.25),int(w*.5),int(w*.75),w]
    if len(ys)!=5:ys=[0,int(h*.25),int(h*.5),int(h*.75),h]
    out={}
    for name,(col,row) in GRID_MAP.items():
        l=max(0,xs[col]-overlap_px);t=max(0,ys[row]-overlap_px);r=min(w,xs[col+1]+overlap_px);b=min(h,ys[row+1]+overlap_px)
        if r>l and b>t:out[name]=work.crop((l,t,r,b))
    return out

def _upscale(image):
    w,h=image.size
    return image.resize((max(1,int(w*UPSCALE)),max(1,int(h*UPSCALE))),Image.Resampling.LANCZOS)

def _variants(image):
    """Create variants targeted at black, red/green/orange and small gray text."""
    rgb=np.asarray(_upscale(image).convert("RGB"))
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    # Preserve black/gray text.
    clahe=cv2.createCLAHE(clipLimit=2.2,tileGridSize=(8,8)).apply(gray)
    sharp=cv2.GaussianBlur(clahe,(0,0),1.0)
    sharp=cv2.addWeighted(clahe,1.65,sharp,-0.65,0)
    # Adaptive threshold handles the slightly gray chart background.
    adaptive=cv2.adaptiveThreshold(sharp,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,31,7)
    # Saturation highlights coloured stars that can become too faint in gray.
    hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
    sat=hsv[:,:,1]
    sat=cv2.normalize(sat,None,0,255,cv2.NORM_MINMAX)
    sat=cv2.createCLAHE(clipLimit=2.0,tileGridSize=(8,8)).apply(sat)
    # Dark ink mask, useful for black text on the light background.
    dark=cv2.inRange(gray,0,150)
    dark=cv2.morphologyEx(dark,cv2.MORPH_OPEN,np.ones((2,2),np.uint8))
    return [gray,sharp,adaptive,sat,dark]

def _clean(text):return re.sub(r"\s+"," ",str(text)).strip()
def _key(text):return re.sub(r"[^0-9a-zA-ZÀ-ỹĐđ]+","",text).lower()

def _read_one(image)->List[dict]:
    reader=load_ocr_reader();candidates={}
    # Work in original crop coordinates after normalizing bbox from each upscaled variant.
    for arr in _variants(image):
        for item in reader.readtext(
            arr,detail=1,paragraph=False,decoder="greedy",
            text_threshold=0.28,low_text=0.08,link_threshold=0.08,
            mag_ratio=1.0,contrast_ths=0.04,adjust_contrast=0.75,
            width_ths=0.55,height_ths=0.55,add_margin=0.04,min_size=5,batch_size=1
        ):
            if len(item)<3:continue
            bbox,text,conf=item[0],_clean(item[1]),float(item[2])
            if not text or conf<0.08:continue
            # bbox is on the upscaled array; normalize it so parser coordinates remain 0..1.
            ah,aw=arr.shape[:2]
            nb=[[round(float(x)/max(1,aw),6),round(float(y)/max(1,ah),6)] for x,y in bbox]
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
    return {"source":"python_easyocr_tuvi_layout_v2","image_sent_to_llm":False,"header_text":[],"cung_count":len(cropped),"cungs":extract_text_from_cungs(cropped)}
