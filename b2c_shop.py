import streamlit as st
import requests
import pandas as pd
import urllib.parse
import numpy as np
import json
import os
import base64

# ==========================================
# 🌟 頁面設定與純淨視覺 CSS
# ==========================================
st.set_page_config(page_title="沐光金工坊 MU GLOW | 商品展示", page_icon="✨", layout="wide", initial_sidebar_state="expanded")

# 🌟 1. 背景處理：保留大理石背景，側邊欄加半透明底
bg_file = "沐光金網站背景圖.jpg"
bg_css = ""
if os.path.exists(bg_file):
    with open(bg_file, "rb") as f:
        bg_data = f.read()
    bg_b64 = base64.b64encode(bg_data).decode()
    bg_css = f"""
    .stApp {{
        background-image: url("data:image/jpeg;base64,{bg_b64}");
        background-size: cover;
        background-attachment: fixed;
        background-position: center;
    }}
    /* 側邊欄加上微透明底 */
    [data-testid="stSidebar"] {{
        background-color: rgba(255, 255, 255, 0.85);
    }}
    """
else:
    bg_css = ".stApp { background-color: #FFFFFF; }"

st.markdown(f"""
<style>
{bg_css}
/* 隱藏頂部裝飾條與底部浮水印 */
.st-emotion-cache-1rqebx {{display: none;}}
footer {{visibility: hidden;}}

/* 🌟 2. 乾淨白卡片排版：商品卡片使用高透明度白底，遮掉多餘的紋理讓商品突出 */
[data-testid="stVerticalBlockBorderWrapper"] {{
    background-color: rgba(255, 255, 255, 0.95) !important;
    border-radius: 15px !important;
    border: 1px solid rgba(178, 136, 80, 0.2) !important;
    box-shadow: 0 4px 10px rgba(0,0,0,0.05);
    padding: 10px;
}}

/* 商品標題與重量文字樣式 */
.prod-title {{
    text-align: center;
    font-size: 18px;
    font-weight: 600;
    color: #333333;
    margin-top: 10px;
    margin-bottom: 0px;
}}
.prod-weight {{
    text-align: center;
    font-size: 14px;
    color: #666666;
    margin-bottom: 10px;
}}

/* 查看價格的按鈕樣式 */
div[data-testid="stButton"] button {{
    border-radius: 20px;
    border: 1px solid #B28850;
    color: #B28850;
    background-color: rgba(255,255,255,0.8);
    transition: all 0.3s;
}}
div[data-testid="stButton"] button:hover {{
    background-color: #B28850;
    color: #FFFFFF;
}}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🌟 基礎設定與資料庫讀取
# ==========================================
SETTINGS_FILE = "product_settings.json" 
CONFIG_FILE = "system_config.json" # 🌟 新增：讀取老闆在 B2B 設定的金價

def load_json(file_path, default_data):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default_data

prod_settings = load_json(SETTINGS_FILE, {})
sys_config = load_json(CONFIG_FILE, {"gold_price": 10000})
current_gold = sys_config.get("gold_price", 10000)

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

df_clean["💡今日動態成本"] = np.round((current_gold * df_clean["黃金重量(錢)"]) + df_clean["盤商收取工資"])

def calculate_retail(row):
    level = str(row.get("定價毛利等級", ""))
    cost = row["💡今日動態成本"]
    if "固定價格" in level: return row.get("手動設定售價(固定商品用)", cost)
    elif "B級" in level: return np.round(cost * 1.16 + 500)
    elif "C級" in level: return np.round(cost * 1.20 + 600)
    else: return cost

df_clean["🏪動態零售價"] = df_clean.apply(calculate_retail, axis=1)

# 🌟 透過老闆後台設定決定是否於 B2C 顯示
def is_public_item(item_name):
    settings = prod_settings.get(item_name, {})
    b2c_status = settings.get("b2c_status", "❌ 隱藏")
    return b2c_status == "✅ 顯示"

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
    st.caption(f"※ 今日金價基準：{current_gold} 元/錢。金價隨國際市場每日波動，此為當前即時試算報價。")

# ==========================================
# 💎 畫面呈現：商品型錄
# ==========================================
# 置中放置去背 Logo
logo_file = "沐光金網站LOGO-removebg-preview.png"
if os.path.exists(logo_file):
    col_l, col_logo, col_r = st.columns([2, 1, 2])
    with col_logo:
        st.image(logo_file, use_container_width=True)
else:
    st.markdown("<h2 style='text-align: center; color: #B28850;'>沐光金工坊</h2>", unsafe_allow_html=True)

st.divider()

# 左側導覽列 (Sidebar)
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

# 右側主畫面 (乾淨的商品網格)
if df_public.empty:
    st.info("目前沒有符合條件的款式，請調整左側的篩選條件。")
else:
    cols_per_row = 3
    for i in range(0, len(df_public), cols_per_row):
        row_items = df_public.iloc[i:i+cols_per_row]
        cols = st.columns(cols_per_row, gap="large")
        
        for idx, (_, row) in enumerate(row_items.iterrows()):
            with cols[idx]:
                with st.container(border=True):
                    # 照片
                    if row['產品照片']:
                        st.image(row['產品照片'], use_container_width=True)
                    else:
                        st.markdown("<div style='height:250px; display:flex; align-items:center; justify-content:center; background-color:#FAFAFA; color:#CCC;'>商品照準備中</div>", unsafe_allow_html=True)
                    
                    # 乾淨的品名與重量
                    st.markdown(f"<div class='prod-title'>{row['品名款式']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='prod-weight'>{row['黃金重量(錢)']} 錢</div>", unsafe_allow_html=True)
                    
                    # 獨立的查看按鈕
                    if st.button("🔍 查看即時報價", key=f"btn_{row['品名款式']}", use_container_width=True):
                        show_product_price(row)
        
        st.write("") 
        st.write("")
