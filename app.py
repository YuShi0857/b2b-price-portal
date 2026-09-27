import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="B2B 查價台系統", layout="wide")
st.title("📦 B2B 批發查價台 - 老闆專屬後台 (開發中)")

API_KEY = st.secrets["RAGIC_API_KEY"]
# 程式自動把網址修正為正確抓取資料的格式
API_URL = st.secrets["RAGIC_URL"].replace(".api", "") 

headers = {
    "Authorization": f"Basic {API_KEY}"
}

@st.cache_data(ttl=60)
def fetch_ragic_data():
    # 加上 api=true 參數，告訴 Ragic 我們要真正的商品資料
    response = requests.get(f"{API_URL}?v=3&api=true", headers=headers) 
    
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"連線失敗，錯誤代碼：{response.status_code}")
        return None

# 執行抓取
data = fetch_ragic_data()

if data:
    st.success("成功抓取到 Ragic 商品資料！")
    
    # Ragic 回傳的是字典格式，我們把它轉成好閱讀的表格 (DataFrame)
    if isinstance(data, dict):
        # 將字典轉換為列表
        records = list(data.values())
        df = pd.DataFrame(records)
        
        # 在網頁上顯示成互動式表格
        st.write("### 你的原始商品資料庫")
        st.dataframe(df)
    else:
        st.write(data)
