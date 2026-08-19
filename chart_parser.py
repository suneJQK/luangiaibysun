# -*- coding: utf-8 -*-
"""Convert normalized OCR into a stable chart JSON contract."""

def build_chart_json(processed):
    cungs={}
    for name, items in processed.get("cungs", {}).items():
        cungs[name]={"name":name,"items":items,"stars":[x["canonical"] for x in items if x.get("status") != "low_confidence"],"review_items":[x for x in items if x.get("status") != "accepted"]}
    return {"schema_version":"1.0","source":"python_ocr","image_sent_to_llm":False,"header":processed.get("header_text",[]),"cungs":cungs}
