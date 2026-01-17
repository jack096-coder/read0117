import streamlit as st
import numpy as np
import cv2
import pandas as pd
from PIL import Image
from streamlit_drawable_canvas import st_canvas
import io

# --- 核心修復補丁：解決 AttributeError: image_to_url ---
# 這段必須放在最前面，確保畫布套件能抓到圖片網址
if not hasattr(st, "image_to_url"):
    def legacy_image_to_url(image, width, clamp, channels, output_format, image_id):
        from streamlit.runtime.media_file_storage import get_instance
        return get_instance().add(image, output_format, image_id)
    st.image_to_url = legacy_image_to_url
# -----------------------------------------------------

st.set_page_config(layout="wide", page_title="答案卡座標擷取系統")

st.title("🗂️ 答案卡區域標記與自動辨識系統")

# 初始化 Session State
if "regions" not in st.session_state:
    st.session_state.regions = {"A1": None, "A2": None, "A3": None, "A4": None}

# 側邊欄：檔案上傳
uploaded_file = st.sidebar.file_uploader("1. 匯入空白答案卡", type=["png", "jpg", "jpeg"])

if uploaded_file:
    bg_image = Image.open(uploaded_file)
    w, h = bg_image.size
    
    # 左右排版：左邊控制，右邊全版顯示
    col_control, col_canvas = st.columns([1, 4])

    with col_control:
        st.subheader("2. 標示區域")
        target_label = st.radio("選擇標記目標：", ["定位點 A1", "基本資料 A2", "選擇題 A3", "手寫區 A4"])
        region_key = {"定位點 A1": "A1", "基本資料 A2": "A2", "選擇題 A3": "A3", "手寫區 A4": "A4"}[target_label]
        
        st.info(f"請在右圖【手動劃記】藍框標出 {target_label} 的範圍。")
        
        if st.button("確認儲存目前框選"):
            st.success(f"{target_label} 區域已記錄！")

        st.divider()
        st.subheader("3. 執行辨識")
        start_btn = st.button("開始辨識並導出數據")

    with col_canvas:
        st.write("### 全版顯示與標記區")
        # 自動計算縮放，讓圖片寬度填滿右側區域 (約 1000 像素)
        canvas_width = 1000
        ratio = canvas_width / w
        canvas_height = int(h * ratio)

        canvas_result = st_canvas(
            fill_color="rgba(0, 0, 255, 0.1)",  # 淺藍填充
            stroke_width=4,
            stroke_color="blue", # 題目要求的藍框
            background_image=bg_image,
            update_streamlit=True,
            height=canvas_height,
            width=canvas_width,
            drawing_mode="rect",
            key=f"canvas_{region_key}",
        )

        # 紀錄座標資料
        if canvas_result.json_data is not None:
            objects = canvas_result.json_data["objects"]
            if len(objects) > 0:
                st.session_state.regions[region_key] = objects[-1]

    # --- 辨識邏輯 ---
    if start_btn:
        with st.spinner("正在辨識標記點並生成報告..."):
            img_cv = cv2.cvtColor(np.array(bg_image), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            results = []

            def to_orig(rect):
                return int(rect["left"]/ratio), int(rect["top"]/ratio), int(rect["width"]/ratio), int(rect["height"]/ratio)

            # A1 定位點 (黑方塊)
            if st.session_state.regions["A1"]:
                l, t, rw, rh = to_orig(st.session_state.regions["A1"])
                roi = gray[t:t+rh, l:l+rw]
                _, th = cv2.threshold(roi, 100, 255, cv2.THRESH_BINARY_INV)
                cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:4]
                for i, c in enumerate(cnts):
                    bx, by, bw, bh = cv2.boundingRect(c)
                    cv2.rectangle(img_cv, (bx+l, by+t), (bx+l+bw, by+t+bh), (0, 0, 255), 3) # 紅框
                    results.append({"Type": "A1", "ID": i+1, "X": bx+l, "Y": by+t, "W": bw, "H": bh})

            # A2, A3 圓圈
            for k, label in [("A2", "Basic"), ("A3", "MCQ")]:
                if st.session_state.regions[k]:
                    l, t, rw, rh = to_orig(st.session_state.regions[k])
                    roi = gray[t:t+rh, l:l+rw]
                    circles = cv2.HoughCircles(cv2.medianBlur(roi, 5), cv2.HOUGH_GRADIENT, 1, 20, param1=50, param2=20, minRadius=8, maxRadius=25)
                    if circles is not None:
                        for i, circle in enumerate(np.uint16(np.around(circles[0, :]))):
                            cx, cy, r = circle
                            cv2.rectangle(img_cv, (cx+l-r, cy+t-r), (cx+l+r, cy+t+r), (0, 0, 255), 2)
                            results.append({"Type": k, "ID": i+1, "CenterX": cx+l, "CenterY": cy+t, "Radius": r})

            # A4 區域
            if st.session_state.regions["A4"]:
                l, t, rw, rh = to_orig(st.session_state.regions["A4"])
                results.append({"Type": "A4", "ID": "Manual_Area", "Left": l, "Top": t, "Width": rw, "Height": rh})

            # 匯出 Excel
            df = pd.DataFrame(results)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            
            st.sidebar.download_button("📥 下載 Excel 座標檔", output.getvalue(), "OMR_Data.xlsx")
            st.subheader("辨識完成預覽 (紅框標註)")
            st.image(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB), use_container_width=True)
else:
    st.warning("👈 請先在左側上傳答案卡圖檔。")
