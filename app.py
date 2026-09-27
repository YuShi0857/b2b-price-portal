import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="B2B 查價台系統", layout="wide")
st.title("📦 B2B 批發查價台 - 老闆專屬後台 (開發中)")

# 讀取金鑰與網址
API_KEY = st.secrets["RAGIC_API_KEY"]
API_URL = st.secrets["RAGIC_URL"].replace(".api", "") 

# === 🕵️ 抓漏偵錯區塊 ===
st.info(f"系統檢查：目前讀取到的金鑰前 3 個字是 👉 『{API_KEY[:3]}』")

if "這" in API_KEY or "貼" in API_KEY or "填" in API_KEY:
    st.error("🚨 抓到了！你的保險箱裡面還是中文的提示字，沒有換成你真正的 Ragic 英文數字金鑰！請回到 Streamlit 後台修改 Secrets。")
    st.stop() # 停止執行
# =========================

@st.cache_data(ttl=60)
def fetch_ragic_data():
    # 雙管齊下：把金鑰同時放在 URL 參數與 Header 裡面，確保 Ragic 一定收得到
    url = f"{API_URL}?v=3&api=true&APIKey={API_KEY}"
    headers = {"Authorization": f"Basic {API_KEY}"}
    
    response = requests.get(url, headers=headers) 
    
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"連線失敗，錯誤代碼：{response.status_code}")
        return None

# 執行抓取
data = fetch_ragic_data()

if data:
    if isinstance(data, dict) and data.get("0") == "ERROR":
        st.error(f"⚠️ Ragic 拒絕存取，請確認 Ragic 後台產生的金鑰是否正確：{data.get('1')}")
    else:
        st.success("🎉 成功抓取到 Ragic 商品資料！")
        
        if isinstance(data, dict):
            # 轉換成乾淨的列表
            records = list(data.values())
            df = pd.DataFrame(records)
            
            # 顯示成互動式表格
            st.write("### 你的原始商品資料庫")
            st.dataframe(df)
        else:
            st.write(data)
