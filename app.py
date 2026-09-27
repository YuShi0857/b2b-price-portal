import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="B2B 查價台系統", layout="wide")
st.title("📦 B2B 批發查價台 - 老闆專屬後台 (開發中)")

# 讀取金鑰與網址
API_KEY = st.secrets["RAGIC_API_KEY"]
API_URL = st.secrets["RAGIC_URL"].replace(".api", "") 

@st.cache_data(ttl=60)
def fetch_ragic_data():
    # 關鍵修改：直接把 APIKey 綁在網址上，絕對不會被系統弄丟
    url = f"{API_URL}?v=3&api=true&APIKey={API_KEY}"
    response = requests.get(url) 
    
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"連線失敗，錯誤代碼：{response.status_code}")
        return None

# 執行抓取
data = fetch_ragic_data()

if data:
    # 攔截 Ragic 的自訂錯誤訊息
    if isinstance(data, dict) and data.get("0") == "ERROR":
        st.error(f"⚠️ Ragic 拒絕存取，請檢查保險箱的金鑰是否貼錯：{data.get('1')}")
    else:
        st.success("🎉 成功抓取到 Ragic 商品資料！")
        
        if isinstance(data, dict):
            # 把 Ragic 亂七八糟的格式轉換成乾淨的列表
            records = list(data.values())
            df = pd.DataFrame(records)
            
            # 顯示成漂亮的互動式表格
            st.write("### 你的原始商品資料庫")
            st.dataframe(df)
        else:
            st.write(data)
