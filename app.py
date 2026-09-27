import streamlit as st
import requests

st.set_page_config(page_title="B2B 查價台測試", layout="wide")
st.title("連線測試區")

# 1. 從 secrets 中讀取你的 Ragic 憑證
API_KEY = st.secrets["RAGIC_API_KEY"]
API_URL = st.secrets["RAGIC_URL"]

# 2. 設定 API 請求的 Headers (告訴 Ragic 你的身分)
headers = {
    "Authorization": f"Basic {API_KEY}"
}

# 3. 發送請求撈取資料
@st.cache_data(ttl=60) # 快取 60 秒，避免一直重複戳 API
def fetch_ragic_data():
    # v=3 代表使用 Ragic 最新的 API 格式
    response = requests.get(f"{API_URL}?v=3", headers=headers) 
    
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"連線失敗，錯誤代碼：{response.status_code}")
        return None

# 4. 執行並顯示結果
data = fetch_ragic_data()

if data:
    st.success("成功連上 Ragic！")
    # 將抓到的原始 JSON 資料直接印在網頁上看看長怎樣
    st.json(data)
