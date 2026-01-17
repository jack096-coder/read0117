import streamlit as st
import numpy as np
import cv2
import pandas as pd
from PIL import Image
from streamlit_drawable_canvas import st_canvas
import io

# 設定頁面配置
st.set_page_config(layout="wide", page_title="答案卡辨識系統")

# --- CSS 優化按鍵與標題 ---
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; }
    h1 { color: #2e4053; }
</style>
""", unsafe_allow_html=True)

st.title("📝 答案卡區域標記與自動辨識系統")

# --- Session State 初始化 ---
# 用來儲存各個區域的畫框資料
if "regions" not in st.session_state:
    st.session_state.regions = {
        "A1": None, # 定位點
        "A2": None, # 基本資料
        "A3": None, # 選擇題
        "A4": None  # 手寫區
    }

# 用來記錄目前正在畫哪一區
if "current_mode" not in st.session_state:
    st.session_state.current_mode = "A1"

# --- 側邊欄控制區 ---
with st.sidebar:
    st.header("1. 匯入影像")
    uploaded_file = st.file_uploader("上傳空白答案卡 (JPG/PNG)", type=["png", "jpg", "jpeg"])
    
    st.divider()
    st.header("2. 標示區域 (畫藍框)")
    st.info("請點選下方按鍵切換模式，接著在右圖框選對應範圍。")
    
    # 建立四個按鍵切換模式
    col_b1, col_b2 = st.columns(2)
    if col_b1.button("標示 定位點 A1"): st.session_state.current_mode = "A1"
    if col_b2.button("標示 基本資料 A2"): st.session_state.current_mode = "A2"
    if col_b1.button("標示 選擇題 A3"): st.session_state.current_mode = "A3"
    if col_b2.button("標示 手寫區 A4"): st.session_state.current_mode = "A4"

    # 顯示目前狀態
    mode_names = {
        "A1": "(1) 定位點區域 A1 (4個黑方塊)", 
        "A2": "(2) 基本資料劃記區 A2 (43個圓圈)", 
        "A3": "(3) 選擇題劃記區 A3 (200個圓圈)", 
        "A4": "(4) 手寫非選擇題區域 A4"
    }
    st.success(f"目前模式：{mode_names[st.session_state.current_mode]}")
    
    st.divider()
    st.header("3. 執行辨識")
    start_ocr = st.button("開始辨識 (去除藍框並標記紅框)", type="primary")

# --- 右側主畫面與邏輯 ---
if uploaded_file:
    # 讀取圖片
    image_pil = Image.open(uploaded_file)
    w_orig, h_orig = image_pil.size
    
    # 設定畫布顯示寬度 (模擬全版顯示)
    display_width = 1000
    ratio = display_width / w_orig
    display_height = int(h_orig * ratio)

    col_main, _ = st.columns([10, 1]) # 佔滿右側

    with col_main:
        st.caption(f"請在下方圖中，用滑鼠拖曳畫出【{st.session_state.current_mode}】的藍色粗框。")
        
        # 繪圖畫布
        canvas_result = st_canvas(
            fill_color="rgba(0, 0, 255, 0.1)",  # 淺藍透明填充
            stroke_width=4,                     # 粗線
            stroke_color="#0000FF",             # 藍色邊框
            background_image=image_pil,
            update_streamlit=True,
            height=display_height,
            width=display_width,
            drawing_mode="rect",
            key=f"canvas_{st.session_state.current_mode}", # 切換模式時強制刷新畫布
        )

        # 將畫布上的框儲存到 session_state
        if canvas_result.json_data is not None:
            objects = canvas_result.json_data["objects"]
            if len(objects) > 0:
                # 只取最後一個畫的框
                st.session_state.regions[st.session_state.current_mode] = objects[-1]

    # --- 辨識邏輯 ---
    if start_ocr:
        # 檢查是否所有區域都已標記 (非強制，但建議)
        missing = [k for k, v in st.session_state.regions.items() if v is None]
        if missing:
            st.warning(f"注意：尚未標記區域 {missing}，將只辨識已標記部分。")

        # 準備 OpenCV 影像
        img_cv = cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # 儲存 Excel 數據的列表
        excel_data = []

        # 輔助函式：將畫布座標轉回原始圖片座標
        def get_real_coords(rect_obj):
            l = int(rect_obj["left"] / ratio)
            t = int(rect_obj["top"] / ratio)
            w = int(rect_obj["width"] / ratio)
            h = int(rect_obj["height"] / ratio)
            return l, t, w, h

        # (1) 辨識 A1：定位點 (黑色方塊)
        if st.session_state.regions["A1"]:
            l, t, w, h = get_real_coords(st.session_state.regions["A1"])
            roi = gray[t:t+h, l:l+w]
            # 二值化找黑塊
            _, thresh = cv2.threshold(roi, 100, 255, cv2.THRESH_BINARY_INV)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # 篩選面積較大的前4個
            contours = sorted(contours, key=cv2.contourArea, reverse=True)[:4]
            
            for i, cnt in enumerate(contours):
                x, y, cw, ch = cv2.boundingRect(cnt)
                # 畫紅框 (注意座標要加回 l, t)
                cv2.rectangle(img_cv, (l+x, t+y), (l+x+cw, t+y+ch), (0, 0, 255), 3)
                # 記錄數據
                excel_data.append({
                    "Area": "A1_value", "ID": i+1, 
                    "X": l+x, "Y": t+y, "W": cw, "H": ch, "R": 0
                })

        # (2) & (3) 辨識 A2 (43圓) 與 A3 (200圓)
        for area_name in ["A2", "A3"]:
            if st.session_state.regions[area_name]:
                l, t, w, h = get_real_coords(st.session_state.regions[area_name])
                roi = gray[t:t+h, l:l+w]
                
                # 霍夫圓變換
                # 參數 param1, param2 可能需要依實際圖片微調
                circles = cv2.HoughCircles(
                    roi, cv2.HOUGH_GRADIENT, dp=1, minDist=15,
                    param1=50, param2=18, minRadius=5, maxRadius=30
                )
                
                if circles is not None:
                    circles = np.uint16(np.around(circles))
                    count = 0
                    for i in circles[0, :]:
                        cx, cy, r = i
                        # 畫外切紅框 (圓心 cx, cy, 半徑 r -> 左上角 x, y, 寬高 2r)
                        # 外切正方形: x = cx-r, y = cy-r, w=2r, h=2r
                        abs_cx = l + cx
                        abs_cy = t + cy
                        
                        # 畫圖
                        cv2.rectangle(img_cv, (abs_cx-r, abs_cy-r), (abs_cx+r, abs_cy+r), (0, 0, 255), 2)
                        
                        excel_data.append({
                            "Area": f"{area_name}_value", "ID": count+1, 
                            "X": abs_cx, "Y": abs_cy, "W": 0, "H": 0, "R": r
                        })
                        count += 1
                        
                        # 限制數量 (A2=43, A3=200)，避免雜訊過多
                        limit = 43 if area_name == "A2" else 200
                        if count >= limit:
                            break

        # (4) 辨識 A4：手寫區 (直接記錄四角座標)
        if st.session_state.regions["A4"]:
            l, t, w, h = get_real_coords(st.session_state.regions["A4"])
            # A4 不用畫紅框，但為了視覺確認，我們可以畫一個大的紅框
            cv2.rectangle(img_cv, (l, t), (l+w, t+h), (0, 0, 255), 3)
            excel_data.append({
                "Area": "A4_value", "ID": 1, 
                "X": l, "Y": t, "W": w, "H": h, "R": 0
            })

        # --- 結果展示區 ---
        st.divider()
        st.subheader("4. 辨識結果與下載")
        
        # 顯示處理後的圖片 (去除藍框，只有紅框)
        st.image(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB), caption="紅框標示辨識結果", use_container_width=True)

        # 匯出 Excel
        df = pd.DataFrame(excel_data)
        # 調整欄位順序
        df = df[["Area", "ID", "X", "Y", "W", "H", "R"]]
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='OMR_Data')
        
        st.download_button(
            label="📥 下載 Excel 辨識數據",
            data=output.getvalue(),
            file_name="OMR_Result.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

else:
    st.info("👋 張老師您好，請先從左側上傳一張空白答案卡圖片。")
