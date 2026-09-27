import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="B2B 查價台系統", layout="wide")
st.title("📦 B2B 批發查價台 - 老闆專屬後台")

# 讀取金鑰與網址
API_KEY = st.secrets["RAGIC_API_KEY"]
API_URL = st.secrets["RAGIC_URL"].replace(".api", "") 

@st.cache_data(ttl=60)
def fetch_ragic_data():
    url = f"{API_URL}?v=3&api=true&APIKey={API_KEY}"
    headers = {"Authorization": f"Basic {API_KEY}"}
    response = requests.get(url, headers=headers) 
    if response.status_code == 200:
        return response.json()
    return None

data = fetch_ragic_data()

if data and isinstance(data, dict) and data.get("0") != "ERROR":
    
    # --- 1. 每日參數設定區 ---
    st.markdown("### 💰 今日參數設定")
    col1, col2 = st.columns(2)
    with col1:
        # 建立一個金價輸入框，預設先隨便帶個 10000
        today_gold_price = st.number_input("📈 今日黃金牌價 (元/錢)：", min_value=0, value=10000, step=100)
    
    st.divider() # 畫一條分隔線
    
    # --- 2. 資料清理與準備 ---
    st.markdown("### 🛠️ 批發商品上架中控台")
    st.caption("你可以在下方表格直接打勾決定是否上架，或微調個別商品的利潤比例。")
    
    records = list(data.values())
    df = pd.DataFrame(records)
    
    # 挑選我們計算跟顯示需要的欄位 (確保欄位名稱跟 Ragic 一模一樣)
    # 如果 Ragic 上的欄位名稱有變，這裡也要跟著改
    needed_columns = ["產品照片", "品名款式", "黃金重量(錢)", "盤商收取工資", "目前庫存量", "定價毛利等級"]
    
    # 過濾出存在的欄位，避免報錯
    existing_columns = [col for col in needed_columns if col in df.columns]
    df_clean = df[existing_columns].copy()
    
    # 把空值補 0，方便後續計算
    df_clean = df_clean.fillna(0)
    
    # --- 3. 加入老闆專屬操控欄位 ---
    # 在表格最左邊插入「上架放行」開關 (預設打勾)
    df_clean.insert(0, "✅ 上架放行", True)
    # 插入「B2B 利潤設定 %」 (預設 35%)
    df_clean.insert(1, "🎯 B2B 利潤設定(%)", 35.0)
    
    # --- 4. 顯示互動式表格 ---
    # st.data_editor 讓表格變成可以編輯的狀態！
    edited_df = st.data_editor(
        df_clean,
        use_container_width=True,
        hide_index=True,
        height=600,
        column_config={
            "✅ 上架放行": st.column_config.CheckboxColumn("上架放行", help="取消打勾，客戶端就看不到此商品"),
            "🎯 B2B 利潤設定(%)": st.column_config.NumberColumn("利潤設定(%)", min_value=0.0, max_value=100.0, step=5.0),
            "產品照片": st.column_config.ImageColumn("產品照片") # 自動把網址轉成圖片預覽
        }
    )
    
else:
    st.error("讀取資料失敗，請確認 Ragic 金鑰設定。")
