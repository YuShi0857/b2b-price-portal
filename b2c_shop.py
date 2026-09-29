import streamlit as st
import requests
import pandas as pd
import urllib.parse
import numpy as np
import json
import os
import base64

# ==========================================
# 🌟 針對零售客人優化頁面設定
# ==========================================
st.set_page_config(page_title="沐光金工坊 MU GLOW | 官方型錄", page_icon="✨", layout="wide")

# ==========================================
# 🎨 品牌視覺與 CSS 樣式注入
# ==========================================
# 1. 載入背景圖
bg_file = "沐光金網站背景圖.jpg"
if os.path.exists(bg_file):
    with open(bg_file, "rb") as f:
        bg_data = f.read()
    bg_b64 = base64.b64encode(bg_data).decode()
    
    # 注入全域 CSS 樣式
    custom_css = f"""
    <style>
    /* 設定全螢幕背景圖 */
    .stApp {{
        background-image: url("data:image/jpeg;base64,{bg_b64}");
        background-size: cover;
        background-attachment: fixed;
        background-position: center;
    }}
    /* 商品卡片加上微透明白底與圓角，提升質感 */
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: rgba(255, 255, 255, 0.75) !important;
        border-radius: 15px !important;
        border: 1px solid rgba(178, 136, 80, 0.3) !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        padding: 10px;
        transition: transform 0.2s;
    }}
    /* 滑鼠游標移過卡片時微微浮起 */
    [data-testid="stVerticalBlockBorderWrapper"]:hover {{
        transform: translateY(-5px);
        box-shadow: 0 8px 15px rgba(0,0,0,0.1);
    }}
    /* 修改頂部進度條顏色為沐光金 */
    .st-emotion-cache-1rqebx {{
        background-color: #B28850;
    }}
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)
else:
    # 找不到圖片時的安全替代方案 (淺奶茶色底)
    st.markdown("""<style>.stApp { background-color: #FDFBF7; }</style>""", unsafe_allow_html=True)

# 2. 顯示頂部 Logo (縮小並放左上角)
logo_file = "沐光金網站LOGO-removebg-preview.png"
if os.path.exists(logo_file):
    # 切割版面：左邊給 1 等份放 Logo，右邊給 7 等份留白
    col_logo, col_space = st.columns([1, 7])
    with col_logo:
        st.image(logo_file, use_container_width=True)
else:
    st.markdown("<h3 style='color: #B28850;'>✨ 沐光金工坊 MU GLOW ✨</h3>", unsafe_allow_html=True)

st.divider()

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
# 💎 畫面呈現：商品型錄展示區
# ==========================================
st.markdown(f"<p style='text-align: center; color: #555555; font-size: 16px; letter-spacing: 2px;'>今日黃金參考牌價：{current_gold} 元/錢</p>", unsafe_allow_html=True)

# 搜尋與篩選器
with st.container():
    col_search, col_weight = st.columns([1, 1])
    with col_search:
        search_kw = st.text_input("🔍 尋找心儀款式 (輸入關鍵字)：")
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

st.write("") # 空白間距

if df_public.empty:
    st.info("目前沒有符合條件的款式，請調整搜尋條件。")
else:
    # 🌟 使用卡片網格佈局 (Grid Layout)
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
                        st.markdown("<div style='height:200px; display:flex; align-items:center; justify-content:center; background-color:#f0f2f6; border-radius:10px;'>商品照準備中</div>", unsafe_allow_html=True)
                    
                    # 商品資訊
                    st.markdown(f"<p style='font-size: 16px; font-weight: bold; margin-bottom: 0px;'>{row['品名款式']}</p>", unsafe_allow_html=True)
                    st.caption(f"重量：{row['黃金重量(錢)']} 錢")
                    
                    # 零售價 (使用沐光金專屬色 #B28850)
                    price = int(row['🏪動態零售價'])
                    st.markdown(f"<h3 style='color: #B28850; margin-top: 5px; font-weight: 800;'>NT$ {price:,}</h3>", unsafe_allow_html=True)
