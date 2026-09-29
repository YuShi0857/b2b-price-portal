import streamlit as st
import requests
import pandas as pd
import urllib.parse
import numpy as np
import json
import os

# 針對零售客人優化頁面設定
st.set_page_config(page_title="線上精選型錄", page_icon="✨", layout="wide")

# ==========================================
# 🌟 基礎設定與資料庫讀取
# ==========================================
SETTINGS_FILE = "product_settings.json" 

def load_json(file_path, default_data):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default_data

prod_settings = load_json(SETTINGS_FILE, {})

# 這裡設定系統預設黃金牌價 (B2C 不提供自行修改，由系統或老闆 B2B 端統一控管)
# 實務上可寫入一個共用的 config.json 讓兩邊讀取，這裡暫以固定值或 Session State 模擬
if "gold_price" not in st.session_state:
    st.session_state.gold_price = 10000

# ==========================================
# 🌟 連線 Ragic 與準備資料 (與 B2B 共用邏輯)
# ==========================================
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
if not data or data.get("0") == "ERROR":
    st.error("系統維護中，無法讀取商品資料，請稍後再試。")
    st.stop()

records = list(data.values())
df = pd.DataFrame(records)
needed_columns = ["產品照片", "品名款式", "黃金重量(錢)", "盤商收取工資", "定價毛利等級", "手動設定售價(固定商品用)", "目前庫存量"]
df_clean = df[[col for col in needed_columns if col in df.columns]].copy().fillna(0)

for col in ["黃金重量(錢)", "盤商收取工資", "目前庫存量", "手動設定售價(固定商品用)"]:
    if col in df_clean.columns: df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0)
        
def get_image_url(file_name):
    if not file_name or str(file_name) == "0": return ""
    return f"https://ap15.ragic.com/sims/file.jsp?a=goldselling&f={urllib.parse.quote(str(file_name))}"

if "產品照片" in df_clean.columns:
    df_clean["產品照片"] = df_clean["產品照片"].apply(get_image_url)

# 計算零售價邏輯
current_gold = st.session_state.gold_price
df_clean["💡今日動態成本"] = np.round((current_gold * df_clean["黃金重量(錢)"]) + df_clean["盤商收取工資"])

def calculate_retail(row):
    level = str(row.get("定價毛利等級", ""))
    cost = row["💡今日動態成本"]
    if "固定價格" in level: return row.get("手動設定售價(固定商品用)", cost)
    elif "B級" in level: return np.round(cost * 1.16 + 500)
    elif "C級" in level: return np.round(cost * 1.20 + 600)
    else: return cost

df_clean["🏪動態零售價"] = df_clean.apply(calculate_retail, axis=1)

# 過濾商品狀態 (隱藏未上架與限制客專屬商品)
def is_public_item(item_name):
    settings = prod_settings.get(item_name, {})
    status = settings.get("status", "🆕 未上架")
    restricted_clients = settings.get("allowed_clients", "").strip()
    # 只有設定為「已上架」且「沒有指定特定帳號」的商品才能對外公開
    return status == "✅ 已上架" and not restricted_clients

df_clean["對外公開"] = df_clean["品名款式"].apply(is_public_item)
df_public = df_clean[(df_clean["對外公開"] == True) & (df_clean["目前庫存量"] > 0)].copy()


# ==========================================
# 💎 畫面呈現：B2C 零售網頁
# ==========================================
st.markdown("<h1 style='text-align: center; color: #D4AF37;'>✨ 本日精選型錄 ✨</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center; color: gray;'>今日黃金參考牌價：{current_gold} 元/錢</p>", unsafe_allow_html=True)
st.divider()

# 搜尋與篩選器
col_search, col_weight = st.columns([1, 1])
with col_search:
    search_kw = st.text_input("🔍 尋找款式 (輸入關鍵字)：")
with col_weight:
    if not df_public.empty:
        w_min, w_max = float(df_public["黃金重量(錢)"].min()), float(df_public["黃金重量(錢)"].max())
        if w_min == w_max: w_max += 0.01 
        weight_range = st.slider("⚖️ 重量區間篩選 (錢)", w_min, w_max, (w_min, w_max), step=0.01)
    else:
        weight_range = (0.0, 10.0)

# 套用篩選
if search_kw:
    df_public = df_public[df_public["品名款式"].str.contains(search_kw, na=False, case=False)]
df_public = df_public[(df_public["黃金重量(錢)"] >= weight_range[0]) & (df_public["黃金重量(錢)"] <= weight_range[1])]

if df_public.empty:
    st.info("目前沒有符合條件的款式，請調整搜尋條件。")
else:
    # 🌟 使用卡片網格佈局 (Grid Layout) 取代原生資料表
    st.markdown("### 🛍️ 最新款式")
    
    # 將商品分群，每排顯示 4 個
    cols_per_row = 4
    for i in range(0, len(df_public), cols_per_row):
        row_items = df_public.iloc[i:i+cols_per_row]
        cols = st.columns(cols_per_row)
        
        for idx, (_, row) in enumerate(row_items.iterrows()):
            with cols[idx]:
                with st.container(border=True):
                    # 照片展示
                    if row['產品照片']:
                        st.image(row['產品照片'], use_container_width=True)
                    else:
                        st.markdown("<div style='height:200px; display:flex; align-items:center; justify-content:center; background-color:#f0f2f6; border-radius:5px;'>無照片</div>", unsafe_allow_html=True)
                    
                    # 商品資訊
                    st.markdown(f"**{row['品名款式']}**")
                    st.caption(f"重量：{row['黃金重量(錢)']} 錢")
                    
                    # 零售價高亮顯示
                    price = int(row['🏪動態零售價'])
                    st.markdown(f"<h3 style='color: #E63946; margin-top: 0px;'>NT$ {price:,}</h3>", unsafe_allow_html=True)
