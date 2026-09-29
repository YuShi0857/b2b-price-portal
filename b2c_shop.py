import streamlit as st
import requests
import pandas as pd
import urllib.parse
import numpy as np
import json
import os

# ==========================================
# 🌟 頁面設定與純淨視覺 CSS
# ==========================================
st.set_page_config(page_title="沐光金工坊 MU GLOW | 商品展示", page_icon="✨", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
/* 強制白底與乾淨排版 */
.stApp {
    background-color: #FFFFFF;
}
/* 隱藏頂部裝飾條與底部浮水印 */
.st-emotion-cache-1rqebx {display: none;}
footer {visibility: hidden;}

/* 商品標題與重量文字樣式 */
.prod-title {
    text-align: center;
    font-size: 18px;
    font-weight: 600;
    color: #333333;
    margin-top: 10px;
    margin-bottom: 0px;
}
.prod-weight {
    text-align: center;
    font-size: 14px;
    color: #666666;
    margin-bottom: 10px;
}

/* 讓按鈕看起來更像電商網站的質感動作 */
div[data-testid="stButton"] button {
    border-radius: 20px;
    border: 1px solid #B28850;
    color: #B28850;
    background-color: transparent;
    transition: all 0.3s;
}
div[data-testid="stButton"] button:hover {
    background-color: #B28850;
    color: #FFFFFF;
}
</style>
""", unsafe_allow_html=True)

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

if "gold_price" not in st.session_state:
    st.session_state.gold_price = 10000

# ==========================================
# 🌟 連線 Ragic 與準備資料 
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

def is_public_item(item_name):
    settings = prod_settings.get(item_name, {})
    status = settings.get("status", "🆕 未上架")
    restricted_clients = settings.get("allowed_clients", "").strip()
    return status == "✅ 已上架" and not restricted_clients

df_clean["對外公開"] = df_clean["品名款式"].apply(is_public_item)
df_public = df_clean[(df_clean["對外公開"] == True) & (df_clean["目前庫存量"] > 0)].copy()

# ==========================================
# 💎 彈出視窗：點擊查看報價
# ==========================================
@st.dialog("💎 產品詳情與即時報價")
def show_product_price(row):
    st.image(row['產品照片'], use_container_width=True)
    st.markdown(f"<h3 style='text-align: center; color: #333;'>{row['品名款式']}</h3>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center; color: #666;'>黃金重量：{row['黃金重量(錢)']} 錢</p>", unsafe_allow_html=True)
    
    price = int(row['🏪動態零售價'])
    st.markdown(f"<div style='text-align: center; background-color: #FDFBF7; padding: 15px; border-radius: 10px; margin-top: 15px;'><span style='font-size: 16px; color: #888;'>今日售價</span><br><span style='font-size: 28px; font-weight: bold; color: #B28850;'>NT$ {price:,}</span></div>", unsafe_allow_html=True)
    st.caption("※ 金價隨國際市場每日波動，此為當前即時試算報價。")

# ==========================================
# 💎 畫面呈現：商品型錄
# ==========================================
# 1. 置中 Logo
logo_file = "沐光金網站LOGO-removebg-preview.png"
if os.path.exists(logo_file):
    col_l, col_logo, col_r = st.columns([2, 1, 2])
    with col_logo:
        st.image(logo_file, use_container_width=True)
else:
    st.markdown("<h2 style='text-align: center; color: #B28850;'>沐光金工坊</h2>", unsafe_allow_html=True)

st.divider()

# 2. 左側導覽列 (Sidebar)
with st.sidebar:
    st.markdown("### 🔍 商品篩選")
    search_kw = st.text_input("尋找款式 (輸入關鍵字)：")
    
    st.markdown("### ⚖️ 重量篩選 (錢)")
    if not df_public.empty:
        w_min, w_max = float(df_public["黃金重量(錢)"].min()), float(df_public["黃金重量(錢)"].max())
        if w_min == w_max: w_max += 0.01 
        weight_range = st.slider("選擇重量區間", w_min, w_max, (w_min, w_max), step=0.01, label_visibility="collapsed")
    else:
        weight_range = (0.0, 10.0)
        
    st.divider()
    st.caption(f"今日黃金參考牌價：{current_gold} 元/錢")

# 套用篩選
if search_kw:
    df_public = df_public[df_public["品名款式"].str.contains(search_kw, na=False, case=False)]
df_public = df_public[(df_public["黃金重量(錢)"] >= weight_range[0]) & (df_public["黃金重量(錢)"] <= weight_range[1])]

# 3. 右側主畫面 (商品網格)
if df_public.empty:
    st.info("目前沒有符合條件的款式，請調整左側的篩選條件。")
else:
    # 採用 3 欄排版，與參考圖相似的舒適留白
    cols_per_row = 3
    for i in range(0, len(df_public), cols_per_row):
        row_items = df_public.iloc[i:i+cols_per_row]
        cols = st.columns(cols_per_row, gap="large")
        
        for idx, (_, row) in enumerate(row_items.iterrows()):
            with cols[idx]:
                # 乾淨的照片
                if row['產品照片']:
                    st.image(row['產品照片'], use_container_width=True)
                else:
                    st.markdown("<div style='height:250px; display:flex; align-items:center; justify-content:center; background-color:#FAFAFA; color:#CCC;'>商品照準備中</div>", unsafe_allow_html=True)
                
                # 品名與重量
                st.markdown(f"<div class='prod-title'>{row['品名款式']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='prod-weight'>{row['黃金重量(錢)']} 錢</div>", unsafe_allow_html=True)
                
                # 點擊查看價格按鈕
                if st.button("🔍 查看即時報價", key=f"btn_{row['品名款式']}", use_container_width=True):
                    show_product_price(row)
        
        st.write("") # 增加排與排之間的呼吸感留白
        st.write("")
