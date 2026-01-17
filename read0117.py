import streamlit as st
import numpy as np
import cv2
import pandas as pd
from PIL import Image
from streamlit_drawable_canvas import st_canvas
import io

# --- 核心修復補丁：針對 Streamlit 1.30+ 的相容性修正 ---
# 必須在任何 canvas 元件執行前定義
if not hasattr(st, "image_to_url"):
    from streamlit.runtime.media_file_storage import get_instance
    def image_to_url(image, width, clamp, channels, output_format, image_id):
        # 模擬舊版的圖片轉 URL 邏輯
        return get_instance().add(image, output_format, image_id)
    st.image_to_url = image_to_url
# -----------------------------------------------------

st.set_page_config(layout="wide", page_title="答案卡辨識系統")

st.title("🗂️ 答案卡區域標記與自動辨識系統")

# 初始化座標儲存空間
if "regions" not in st.session_state:
    st.session_state.regions = {"A1": None, "A2": None, "A3": None, "A4": None}

# 左側側邊欄：功能控制
with st.sidebar:
    st.header("1. 檔案上傳")
    uploaded_file = st.file_uploader("匯入空白答案卡 (JPG/PNG)", type=["png", "jpg", "jpeg"])
    
    st.divider()
    st.header("2. 標示區域")
    target_label = st.radio("選擇標記目標：", ["定位點 A1", "基本資料 A2", "選擇題 A3", "手寫區 A4"])
    region_key = {"定位點 A1": "A1", "基本資料 A2": "A2", "選擇題 A3": "A3", "手寫區 A4": "A4"}[target_label]
    
    if st.button("確認儲存目前框選區域"):
        st.success(f"已記錄 {target_label} 座標！")
    
    st.divider()
    st.header("3. 執行辨識")
    start_btn = st.button("開始掃描並導出 Excel")

# 右側主畫面：全版顯示與標記
if uploaded_file:
    # 讀取圖片並取得原始尺寸
    img = Image.open(uploaded_file)
    w, h = img.size
    
    # 強制將右側區域寬度設大，以實現「全版顯示」
    canvas_width = 1000 
    ratio = canvas_width / w
    canvas_height = int(h * ratio)

    st.subheader(f"目前正在標記：{target_label}")
    st.caption("使用滑鼠在下方圖片中拖曳，畫出藍色框線。")

    # 執行畫布
    canvas_result = st_canvas(
        fill_color="rgba(0, 0, 255, 0.1)",  # 藍色透明填充
        stroke_width=4,
        stroke_color="blue",               # 藍色邊框
        background_image=img,              # 這是關鍵，補丁修正後此處應可正確顯示
        update_streamlit=True,
        height=canvas_height,
        width=canvas_width,
        drawing_mode="rect",
        key=f"canvas_main_{region_key}",   # 加上 key 確保組件重新渲染
    )

    # 紀錄座標
    if canvas_result.json_data is not None:
        objs = canvas_result.json_data["objects"]
        if len(objs) > 0:
            st.session_state.regions[region_key] = objs[-1]

    # --- 辨識與匯出邏輯 ---
    if start_btn:
        with st.spinner("辨識中..."):
            img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            results = []

            # 座標轉換函式
            def to_orig(rect):
                return int(rect["left"]/ratio), int(rect["top"]/ratio), \
                       int(rect["width"]/ratio), int(rect["height"]/ratio)

            # A1 辨識
            if st.session_state.regions["A1"]:
                l, t, rw, rh = to_orig(st.session_state.regions["A1"])
                roi = gray[t:t+rh, l:l+rw]
                _, th = cv2.threshold(roi, 100, 255, cv2.THRESH_BINARY_INV)
                cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:4]
                for i, c in enumerate(cnts):
                    bx, by, bw, bh = cv2.boundingRect(c)
                    cv2.rectangle(img_cv, (bx+l, by+t), (bx+l+bw, by+t+bh), (0,0,255), 3)
                    results.append({"Type": "A1_Anchor", "ID": i+1, "X": bx+l, "Y": by+t, "W": bw, "H": bh})

            # A2, A3 圓圈辨識
            for k in ["A2", "A3"]:
                if st.session_state.regions[k]:
                    l, t, rw, rh = to_orig(st.session_state.regions[k])
                    roi = gray[t:t+rh, l:l+rw]
                    circles = cv2.HoughCircles(cv2.medianBlur(roi, 5), cv2.HOUGH_GRADIENT, 1, 20, param1=50, param2=20, minRadius=8, maxRadius=25)
                    if circles is not None:
                        for i, circle in enumerate(np.uint16(np.around(circles[0, :]))):
                            cx, cy, r = circle
                            cv2.rectangle(img_cv, (cx+l-r, cy+t-r), (cx+l+r, cy+t+r), (0,0,255), 2)
                            results.append({"Type": k, "ID": i+1, "CenterX": cx+l, "CenterY": cy+t, "Radius": r})

            # 匯出資料
            df = pd.DataFrame(results)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            
            st.sidebar.download_button("📥 下載辨識數據 Excel", output.getvalue(), "OMR_Results.xlsx")
            st.image(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB), caption="掃描結果預覽", use_container_width=True)

else:
    st.info("👋 老師您好！請從左側上傳空白答案卡圖片，系統將自動顯示於此處。")
