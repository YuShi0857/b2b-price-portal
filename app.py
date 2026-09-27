import streamlit as st
import requests
import pandas as pd
import urllib.parse

st.set_page_config(page_title="B2B 查價台系統", layout="wide")
st.title("📦 B2B 批發查價台 - 老闆專屬後台")

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
    
    st.markdown("### 💰 今日參數設定")
    col1, col2 = st.columns(2)
    with col1:
        today_gold_price = st.number_input("📈 今日黃金牌價 (元/錢)：", min_value=0, value=10000, step=100)
    
    st.divider()
    
    st.markdown("### 🛠️ 批發商品上架中控台")
    
    records = list(data.values())
    df = pd.DataFrame(records)
    
    # 🌟 修正 1：把「本件真實總成本」加回顯示清單中
    needed_columns = ["產品照片", "品名款式", "黃金重量(錢)", "盤商收取工資", "本件真實總成本", "目前庫存量", "定價毛利等級"]
    
    existing_columns = [col for col in needed_columns if col in df.columns]
    df_clean = df[existing_columns].copy()
    df_clean = df_clean.fillna(0)
    
    # 🌟 修正 2：把 Ragic 的「檔名」轉換成真正的「圖片網址」
    def get_image_url(file_name):
        if not file_name or str(file_name) == "0": 
            return ""
        # 組合出 Ragic 專屬的圖片下載網址 (goldselling 是你的資料庫帳號)
        encoded_name = urllib.parse.quote(str(file_name))
        return f"https://ap15.ragic.com/sims/file.jsp?a=goldselling&f={encoded_name}"
        
    if "產品照片" in df_clean.columns:
        df_clean["產品照片"] = df_clean["產品照片"].apply(get_image_url)
    
    # 加入老闆專屬操控欄位
    df_clean.insert(0, "✅ 上架放行", True)
    df_clean.insert(1, "🎯 B2B 利潤設定(%)", 35.0)
    
    # 顯示互動式表格
    edited_df = st.data_editor(
        df_clean,
        use_container_width=True,
        hide_index=True,
        height=700, # 表格稍微拉高一點，讓照片有空間顯示
        column_config={
            "✅ 上架放行": st.column_config.CheckboxColumn("上架放行", help="取消打勾，客戶端就看不到此商品"),
            "🎯 B2B 利潤設定(%)": st.column_config.NumberColumn("利潤設定(%)", min_value=0.0, max_value=100.0, step=5.0),
            "產品照片": st.column_config.ImageColumn("產品照片") # 告訴系統這是一張圖片
        }
    )
    
else:
    st.error("讀取資料失敗，請確認 Ragic 金鑰設定。")
