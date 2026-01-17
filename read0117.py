import streamlit as st
import numpy as np
import cv2
import pandas as pd
from PIL import Image
from streamlit_drawable_canvas import st_canvas
import io

st.set_page_config(layout="wide", page_title="答案卡座標擷取系統")

st.title("🗂️ 答案卡區域標記與自動辨識系統")

# 初始化 Session State 用於儲存各區域座標
if "regions" not in st.session_state:
    st.session_state.regions = {"A1": None, "A2": None, "A3": None, "A4": None}

# --- 側邊欄：功能選擇 ---
st.sidebar.header("步驟面板")
uploaded_file = st.sidebar.file_uploader("1. 匯入空白答案卡", type=["png", "jpg", "jpeg"])
target_region = st.sidebar.radio("2. 選擇標示區域", ["定位點 A1", "基本資料 A2", "選擇題 A3", "手寫區 A4"])

# 按鍵對應
region_map = {"定位點 A1": "A1", "基本資料 A2": "A2", "選擇題 A3": "A3", "手寫區 A4": "A4"}

if uploaded_file:
    bg_image = Image.open(uploaded_file)
    w, h = bg_image.size
    # 縮放顯示比例以符合螢幕 (假設寬度限制在 800)
    display_width = 800
    ratio = display_width / w
    display_height = int(h * ratio)

    col1, col2 = st.columns([1, 3])

    with col1:
        st.subheader("控制項")
        if st.button("確認此區域標示"):
            st.success(f"{target_region} 區域已暫存")
        
        start_recognition = st.button("3. 開始辨識並導出數據")

    with col2:
        st.subheader("全版顯示與標記區")
        # 繪圖畫布
        canvas_result = st_canvas(
            fill_color="rgba(255, 165, 0, 0.3)",  # 填充顏色
            stroke_width=3,
            stroke_color="blue",
            background_image=bg_image,
            update_streamlit=True,
            height=display_height,
            width=display_width,
            drawing_mode="rect",
            key=f"canvas_{target_region}",
        )

        # 儲存當前繪製的框到 session_state
        if canvas_result.json_data is not None:
            objects = canvas_result.json_data["objects"]
            if len(objects) > 0:
                # 取得最後一個畫的框
                last_rect = objects[-1]
                st.session_state.regions[region_map[target_region]] = last_rect

    # --- 辨識邏輯 ---
    if start_recognition:
        with st.spinner("辨識中...請稍候"):
            # 轉換影像為 OpenCV 格式
            img_cv = cv2.cvtColor(np.array(bg_image), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            
            results = []

            # 輔助函式：轉換畫布座標回原始影像座標
            def get_orig_coords(rect):
                left = int(rect["left"] / ratio)
                top = int(rect["top"] / ratio)
                width = int(rect["width"] / ratio)
                height = int(rect["height"] / ratio)
                return left, top, width, height

            # (1) A1 定位點辨識 (黑方塊)
            if st.session_state.regions["A1"]:
                l, t, w_a, h_a = get_orig_coords(st.session_state.regions["A1"])
                roi = gray[t:t+h_a, l:l+w_a]
                _, thresh = cv2.threshold(roi, 100, 255, cv2.THRESH_BINARY_INV)
                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                a1_data = []
                # 篩選面積前 4 大的方塊
                contours = sorted(contours, key=cv2.contourArea, reverse=True)[:4]
                for i, cnt in enumerate(contours):
                    x_c, y_c, w_c, h_c = cv2.boundingRect(cnt)
                    # 轉為全圖座標
                    abs_x, abs_y = x_c + l, y_c + t
                    cv2.rectangle(img_cv, (abs_x, abs_y), (abs_x+w_c, abs_y+h_c), (0, 0, 255), 3)
                    a1_data.append({"Type": "A1_Anchor", "ID": i+1, "X": abs_x, "Y": abs_y, "W": w_c, "H": h_c})
                results.extend(a1_data)

            # (2) & (3) A2, A3 圓圈辨識
            for region_key, label in [("A2", "BasicInfo"), ("A3", "MultipleChoice")]:
                if st.session_state.regions[region_key]:
                    l, t, w_a, h_a = get_orig_coords(st.session_state.regions[region_key])
                    roi = gray[t:t+h_a, l:l+w_a]
                    blurred = cv2.medianBlur(roi, 5)
                    circles = cv2.HoughCircles(
                        blurred, cv2.HOUGH_GRADIENT, dp=1, minDist=20,
                        param1=50, param2=20, minRadius=10, maxRadius=30
                    )
                    
                    if circles is not None:
                        circles = np.uint16(np.around(circles))
                        for i, circle in enumerate(circles[0, :]):
                            cx, cy, r = circle
                            abs_cx, abs_cy = cx + l, cy + t
                            cv2.circle(img_cv, (abs_cx, abs_cy), r, (0, 0, 255), 2)
                            results.append({"Type": region_key, "ID": i+1, "CenterX": abs_cx, "CenterY": abs_cy, "Radius": r})

            # (4) A4 區域座標
            if st.session_state.regions["A4"]:
                l, t, w_a, h_a = get_orig_coords(st.session_state.regions["A4"])
                results.append({"Type": "A4_Area", "ID": 1, "Left": l, "Top": t, "Width": w_a, "Height": h_a})

            # 導出 Excel
            df = pd.DataFrame(results)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Sheet1')
            processed_data = output.getvalue()

            st.sidebar.download_button(
                label="📥 下載辨識數據 (Excel)",
                data=processed_data,
                file_name="answer_card_coords.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            # 顯示辨識結果圖 (去除藍框，僅留紅框標示)
            st.subheader("辨識結果 (紅框標示區)")
            st.image(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB), use_container_width=True)

else:
    st.info("請先從左側上傳一張答案卡圖片開始。")
