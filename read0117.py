import streamlit as st
import numpy as np
import cv2
import pandas as pd
from PIL import Image
from streamlit_drawable_canvas import st_canvas
import io

# --- 🚀 萬能修復補丁：解決畫布圖片顯示問題 ---
if not hasattr(st, "image_to_url"):
    try:
        # 針對較新版 Streamlit
        from streamlit.runtime.media_file_proxy import get_image_url
        st.image_to_url = get_image_url
    except ImportError:
        try:
            # 針對穩定版 Streamlit
            from streamlit.elements.image import image_to_url
            st.image_to_url = image_to_url
        except ImportError:
            # 最終備案：手動對接 runtime 存儲
            from streamlit.runtime.media_file_storage import get_instance
            def legacy_image_to_url(image, width, clamp, channels, output_format, image_id):
                return get_instance().add(image, output_format, image_id)
            st.image_to_url = legacy_image_to_url
# -----------------------------------------------------

st.set_page_config(layout="wide", page_title="答案卡辨識系統")

st.title("🗂️ 答案卡區域標記與自動辨識系統")

# 初始化 session 狀態
if "regions" not in st.session_state:
    st.session_state.regions = {"A1": None, "A2": None, "A3": None, "A4": None}

with st.sidebar:
    st.header("1. 檔案上傳")
    uploaded_file = st.file_uploader("匯入空白答案卡", type=["png", "jpg", "jpeg"])
    
    st.divider()
    st.header("2. 標示區域")
    target_label = st.radio("選擇標記目標：", ["定位點 A1", "基本資料 A2", "選擇題 A3", "手寫區 A4"])
    region_key = {"定位點 A1": "A1", "基本資料 A2": "A2", "選擇題 A3": "A3", "手寫區 A4": "A4"}[target_label]
    
    if st.button("確認儲存目前框選"):
        st.success(f"已記錄 {target_label}！")
    
    st.divider()
    if st.button("3. 開始辨識並導出數據"):
        st.session_state.run_ocr = True

# --- 右側全版顯示區 ---
if uploaded_file:
    img = Image.open(uploaded_file)
    w, h = img.size
    
    # 強制放大顯示比例 (寬度 1100px)
    canvas_width = 1100 
    ratio = canvas_width / w
    canvas_height = int(h * ratio)

    st.subheader(f"正在標記：{target_label}")
    
    # 執行畫布：加入 rerender_on_update 確保圖片刷出
    canvas_result = st_canvas(
        fill_color="rgba(0, 0, 255, 0.2)", 
        stroke_width=3,
        stroke_color="blue",
        background_image=img,
        update_streamlit=True,
        height=canvas_height,
        width=canvas_width,
        drawing_mode="rect",
        key=f"canvas_{region_key}", # 區域切換時強制刷新畫布
    )

    if canvas_result.json_data:
        objs = canvas_result.json_data["objects"]
        if objs:
            st.session_state.regions[region_key] = objs[-1]
else:
    st.info("👋 老師您好！請從左側上傳答案卡，圖片會自動在右側顯示。")
