import streamlit as st
import requests
import pandas as pd
import urllib.parse
import numpy as np
import json
import os
import base64
import re
from datetime import datetime, timedelta, date
from streamlit_drawable_canvas import st_canvas

# ==========================================
# 🌟 路由與動態頁面設定
# ==========================================
is_b2b = st.query_params.get("b2b") == "true"

if is_b2b:
    st.set_page_config(page_title="B2B 批發查價台", layout="wide")
else:
    st.set_page_config(page_title="沐光金工坊 MU GLOW | 官方型錄", page_icon="✨", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# 🌟 系統共用模組與資料庫讀取
# ==========================================
def load_json(file_path, default_data):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default_data

def save_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

DB_FILE = "orders_db.json"
USERS_DB_FILE = "users_db.json"
CARTS_FILE = "carts_db.json" 
SETTINGS_FILE = "product_settings.json" 
CONFIG_FILE = "system_config.json" 
ITEMS_PER_PAGE = 50  

DEFAULT_USERS = {
    "boss": {"password": "123", "role": "admin", "name": "老闆", "is_restricted": False},
    "sales1": {"password": "123", "role": "operator", "name": "現場業務A"},
    "picker1": {"password": "123", "role": "picker", "name": "內部檢貨員A"}
}

orders = load_json(DB_FILE, [])
users_db = load_json(USERS_DB_FILE, DEFAULT_USERS)
if "sales1" not in users_db: 
    users_db["sales1"] = {"password": "123", "role": "operator", "name": "現場業務A"}
    save_json(USERS_DB_FILE, users_db)
all_carts = load_json(CARTS_FILE, {})
prod_settings = load_json(SETTINGS_FILE, {})
sys_config = load_json(CONFIG_FILE, {"gold_price": 10000, "b2b_margin": 35.0})

current_gold = sys_config.get("gold_price", 10000)
current_margin = sys_config.get("b2b_margin", 35.0)

# ==========================================
# 🌟 資安防護：登入憑證即時核對
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if st.session_state.logged_in:
    acc = st.session_state.get("account_id")
    saved_pw = st.session_state.get("session_pw") 
    if acc not in users_db or str(users_db[acc].get("password")) != str(saved_pw):
        st.session_state.logged_in = False
        st.error("⚠️ 您的登入狀態已失效（可能因密碼修改或帳號權限異動），請重新登入！")

# ==========================================
# 🌟 頁碼回呼機制與狀態記憶
# ==========================================
if "client_page" not in st.session_state: st.session_state.client_page = 1
if "admin_page" not in st.session_state: st.session_state.admin_page = 1

if "undo_b2b" not in st.session_state: st.session_state.undo_b2b = {}
if "undo_b2c" not in st.session_state: st.session_state.undo_b2c = {}

# 💡 記錄直播間動態試算賣價的暫存狀態
if "live_temp_prices" not in st.session_state: st.session_state.live_temp_prices = {}
if "current_view_skus" not in st.session_state: st.session_state.current_view_skus = []
if "admin_view_names" not in st.session_state: st.session_state.admin_view_names = []

def reset_client_page(): st.session_state.client_page = 1
def reset_admin_page(): st.session_state.admin_page = 1

def prev_c_page(): st.session_state.client_page -= 1
def next_c_page(): st.session_state.client_page += 1
def prev_a_page(): st.session_state.admin_page -= 1
def next_a_page(): st.session_state.admin_page += 1

# ==========================================
# 🌟 Ragic 資料拉取與基礎運算
# ==========================================
API_KEY = st.secrets["RAGIC_API_KEY"]
API_URL = st.secrets["RAGIC_URL"].replace(".api", "") 

@st.cache_data(ttl=60)
def fetch_ragic_data():
    url = f"{API_URL}?v=3&api=true&APIKey={API_KEY}&limit=10000"
    headers = {"Authorization": f"Basic {API_KEY}"}
    try:
        response = requests.get(url, headers=headers, timeout=15) 
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.RequestException:
        return None
    return None

data = fetch_ragic_data()
if not data or data.get("0") == "ERROR":
    st.error("⚠️ 系統與資料庫連線維護中，或網路不穩定，請稍後再試。")
    st.stop()

records = list(data.values())
df = pd.DataFrame(records)

needed_columns = ["產品照片", "商品專屬編號", "品名款式", "黃金重量(錢)", "盤商收取工資", "定價毛利等級", "手動設定售價(固定商品用)", "目前庫存量", "本件真實總成本"]
df_clean = df[[col for col in needed_columns if col in df.columns]].copy().fillna(0)

if "商品專屬編號" not in df_clean.columns: df_clean["商品專屬編號"] = ""
df_clean["商品專屬編號"] = df_clean["商品專屬編號"].astype(str)

for col in ["黃金重量(錢)", "盤商收取工資", "目前庫存量", "手動設定售價(固定商品用)", "本件真實總成本"]:
    if col in df_clean.columns: df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0)
        
def get_image_url(file_name):
    if not file_name or str(file_name) == "0": return ""
    return f"https://ap15.ragic.com/sims/file.jsp?a=goldselling&f={urllib.parse.quote(str(file_name))}"

if "產品照片" in df_clean.columns:
    df_clean["產品照片"] = df_clean["產品照片"].apply(get_image_url)

# ==========================================
# 🛡 讀取所有設定與利潤參數
# ==========================================
my_acc = st.session_state.account_id if st.session_state.get("logged_in") else None
my_user_data = users_db.get(my_acc, {})
effective_margin = current_margin
if st.session_state.get("role") == "client":
    custom_m = my_user_data.get("custom_margin")
    if custom_m not in [None, ""]: effective_margin = float(custom_m)

df_clean["狀態"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("status", "🆕 未上架"))
df_clean["B2C狀態"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("b2c_status", "❌ 隱藏"))
df_clean["指定帳號"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("allowed_clients", ""))

# B2B 參數
df_clean["💰 B2B指定利潤"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("fixed_profit", 0))
def get_min_profit(x):
    s = prod_settings.get(x, {})
    if "min_b2b_profit" in s: return s["min_b2b_profit"]
    if "lock_tolerance" in s: return abs(s["lock_tolerance"]) 
    return 500
df_clean["🛡️ B2B最低保底利潤"] = df_clean["品名款式"].apply(get_min_profit)

# B2C 參數
df_clean["💰 B2C指定利潤"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("fixed_profit_b2c", 0))
df_clean["🛡️ B2C最低保底利潤"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("min_b2c_profit", 1000))

df_clean["💡今日動態成本"] = np.round((current_gold * df_clean["黃金重量(錢)"]) + df_clean["盤商收取工資"])

# ==========================================
# 🛡 B2C 售價與防虧計算
# ==========================================
def calculate_retail(row):
    cost = row["💡今日動態成本"]
    # 優先使用 B2C 指定利潤
    if row.get("💰 B2C指定利潤", 0) > 0:
        return cost + row["💰 B2C指定利潤"]
        
    level = str(row.get("定價毛利等級", ""))
    if "固定價格" in level: return row.get("手動設定售價(固定商品用)", cost)
    elif "B級" in level: return np.round(cost * 1.16 + 500)
    elif "C級" in level: return np.round(cost * 1.20 + 600)
    else: return cost

df_clean["🏪動態零售價"] = df_clean.apply(calculate_retail, axis=1)
df_clean["原本預期利潤"] = df_clean["🏪動態零售價"] - df_clean["💡今日動態成本"]

def calc_hist_retail(row):
    cost = row["本件真實總成本"]
    if cost <= 0: return 0
    if row.get("💰 B2C指定利潤", 0) > 0:
        return cost + row["💰 B2C指定利潤"]

    level = str(row.get("定價毛利等級", ""))
    if "固定價格" in level: return row.get("手動設定售價(固定商品用)", cost)
    elif "B級" in level: return np.round(cost * 1.16 + 500)
    elif "C級" in level: return np.round(cost * 1.20 + 600)
    else: return cost

df_clean["📜歷史零售價"] = df_clean.apply(calc_hist_retail, axis=1)
df_clean["📜歷史B2C預期利潤"] = df_clean["📜歷史零售價"] - df_clean["本件真實總成本"]

df_clean["💰B2C實賺金額"] = df_clean["🏪動態零售價"] - df_clean["本件真實總成本"]
df_clean["📈B2C實賺毛利率(%)"] = np.where(df_clean["🏪動態零售價"] > 0, (df_clean["💰B2C實賺金額"] / df_clean["🏪動態零售價"]) * 100, 0)
df_clean["💰今日動態淨利"] = df_clean["🏪動態零售價"] - df_clean["💡今日動態成本"]
df_clean["📈今日動態淨利率(%)"] = np.where(df_clean["🏪動態零售價"] > 0, (df_clean["💰今日動態淨利"] / df_clean["🏪動態零售價"]) * 100, 0)

df_clean["🔒B2C解鎖利潤"] = np.round(df_clean["📜歷史B2C預期利潤"] * 0.50)

# 🚀 B2C 鎖定邏輯改寫
df_clean["🔒B2C自動鎖定"] = np.where(
    df_clean["💰 B2C指定利潤"] > 0,
    (df_clean["本件真實總成本"] > 0) & ((df_clean["🏪動態零售價"] - df_clean["本件真實總成本"]) < df_clean["🛡️ B2C最低保底利潤"]),
    (df_clean["本件真實總成本"] > 0) & (df_clean["💰B2C實賺金額"] < df_clean["🔒B2C解鎖利潤"])
)

# ==========================================
# 🛡 B2B 售價與防虧計算
# ==========================================
df_clean["💡理想批發值"] = df_clean["本件真實總成本"] + df_clean["💰 B2B指定利潤"]

df_clean["🔥廠商批發價"] = np.where(
    df_clean["💰 B2B指定利潤"] > 0,
    df_clean["💡今日動態成本"] + df_clean["💰 B2B指定利潤"],
    np.round(df_clean["💡今日動態成本"] + (df_clean["原本預期利潤"] * (effective_margin / 100)))
)

df_clean["💰實賺金額(歷史比)"] = df_clean["🔥廠商批發價"] - df_clean["本件真實總成本"]
df_clean["📈實賺毛利率(%)"] = np.where(df_clean["🔥廠商批發價"] > 0, (df_clean["💰實賺金額(歷史比)"] / df_clean["🔥廠商批發價"]) * 100, 0)

df_clean["📜歷史批發價"] = np.where(
    df_clean["💰 B2B指定利潤"] > 0,
    df_clean["💡理想批發值"],  
    np.round(df_clean["本件真實總成本"] + (df_clean["📜歷史B2C預期利潤"] * (effective_margin / 100)))
)
df_clean["📜歷史B2B預期利潤"] = df_clean["📜歷史批發價"] - df_clean["本件真實總成本"]
df_clean["🔒B2B解鎖利潤"] = np.round(df_clean["📜歷史B2C預期利潤"] * 0.30)

df_clean["🔒B2B自動鎖定"] = np.where(
    df_clean["💰 B2B指定利潤"] > 0,
    (df_clean["本件真實總成本"] > 0) & ((df_clean["🔥廠商批發價"] - df_clean["本件真實總成本"]) < df_clean["🛡️ B2B最低保底利潤"]),
    (df_clean["本件真實總成本"] > 0) & (df_clean["💰實賺金額(歷史比)"] < df_clean["🔒B2B解鎖利潤"])
)

def get_lock_status(row):
    msgs = []
    if row.get("🔒B2B自動鎖定"): msgs.append("🚫 B2B鎖定")
    if row.get("🔒B2C自動鎖定"): msgs.append("🚫 B2C鎖定")
    if not msgs: return "✅ 正常"
    return " + ".join(msgs)

df_clean["防虧狀態"] = df_clean.apply(get_lock_status, axis=1)

# ==========================================
# 📦 全域可用庫存計算
# ==========================================
reserved_stock = {}
for o in orders:
    if o.get("狀態") in ["待派單", "待檢貨", "待出貨"]:
        for item in o.get("購買明細", []):
            name = item.get("品名款式", "")
            if name: reserved_stock[name] = reserved_stock.get(name, 0) + item.get("數量", 0)

for acc, cart_items in all_carts.items():
    if acc != my_acc: 
        for name, qty in cart_items.items():
            reserved_stock[name] = reserved_stock.get(name, 0) + qty

df_clean["網頁可用庫存"] = df_clean["目前庫存量"] - df_clean["品名款式"].map(reserved_stock).fillna(0)
my_cart = all_carts.get(my_acc, {})
df_clean["🛒 我的購物車"] = df_clean["品名款式"].apply(lambda x: my_cart.get(x, 0))

# ==========================================
# 💎 路由：B2C 官方型錄 (給消費者看)
# ==========================================
if not is_b2b:
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
        [data-testid="stSidebar"] {{ background-color: transparent !important; }}
        [data-testid="stSidebar"] > div:first-child {{
            background-color: rgba(255, 255, 255, 0.4) !important;
            backdrop-filter: blur(15px);
            border-right: 1px solid rgba(255, 255, 255, 0.4);
        }}
        [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label, [data-testid="stSidebar"] div {{
            color: #333333 !important;
        }}
        [data-testid="stTextInput"] div[data-baseweb="input"] {{
            background-color: rgba(255, 255, 255, 0.8) !important;
            color: #333333 !important;
        }}
        """
    else:
        bg_css = ".stApp { background-color: #FFFFFF; }"

    st.markdown(f"""
    <style>
    {bg_css}
    .st-emotion-cache-1rqebx {{display: none;}}
    footer {{visibility: hidden;}}
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: rgba(255, 255, 255, 0.95) !important;
        border-radius: 15px !important;
        border: 1px solid rgba(178, 136, 80, 0.2) !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        padding: 10px;
    }}
    .prod-title {{ text-align: center; font-size: 18px; font-weight: 600; color: #333333; margin-top: 10px; margin-bottom: 0px; }}
    .prod-weight {{ text-align: center; font-size: 14px; color: #666666; margin-bottom: 10px; }}
    div[data-testid="stButton"] button {{
        border-radius: 20px; border: 1px solid #B28850; color: #B28850; background-color: rgba(255,255,255,0.8); transition: all 0.3s;
    }}
    div[data-testid="stButton"] button:hover {{ background-color: #B28850; color: #FFFFFF; }}
    div[data-testid="stButton"] button[disabled] {{
        border: 1px solid #CCCCCC !important; color: #999999 !important; background-color: #F0F0F0 !important;
    }}
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <a href="https://line.me/R/ti/p/@815ikjjr" target="_blank" style="position: fixed; bottom: 30px; right: 30px; z-index: 9999; transition: transform 0.3s;" onmouseover="this.style.transform='scale(1.1)'" onmouseout="this.style.transform='scale(1)'">
        <img src="https://upload.wikimedia.org/wikipedia/commons/4/41/LINE_logo.svg" width="60" height="60" style="filter: drop-shadow(2px 4px 6px rgba(0,0,0,0.3));">
    </a>
    """, unsafe_allow_html=True)

    def is_public_item(row):
        item_name = row["品名款式"]
        settings = prod_settings.get(item_name, {})
        b2c_status = str(settings.get("b2c_status", "❌ 隱藏"))
        is_locked = row.get("🔒B2C自動鎖定", False)
        has_stock = row.get("網頁可用庫存", 0) > 0  
        return ("✅ 顯示" in b2c_status) and not is_locked and has_stock

    df_clean["對外公開"] = df_clean.apply(is_public_item, axis=1)
    df_public = df_clean[df_clean["對外公開"] == True].copy()

    @st.dialog("✨ 產品詳情與專屬報價")
    def show_product_price(row):
        st.image(row['產品照片'], use_container_width=True)
        st.markdown(f"<h3 style='text-align: center; color: #333;'>{row['品名款式']}</h3>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align: center; color: #B28850; font-weight: bold; font-size: 16px;'>⚖ 黃金重量：{row['黃金重量(錢)']} 錢</p>", unsafe_allow_html=True)
        
        st.markdown(f"<div style='text-align: center; background-color: #FDFBF7; padding: 15px; border-radius: 10px; margin-top: 15px;'><span style='font-size: 18px; font-weight: bold; color: #B28850;'>✨ 歡迎截圖私訊客服取得即時報價</span></div>", unsafe_allow_html=True)
        
        st.markdown("""
        <div style="margin-top: 20px; text-align: center; padding: 15px; background-color: #f0fdf4; border: 1px solid #06C755; border-radius: 10px;">
            <p style="color: #06C755; font-weight: bold; margin-bottom: 5px; font-size: 16px;">🛒 如何購買此商品？</p>
            <p style="color: #555; font-size: 14px; margin-bottom: 12px;">請直接<b>截圖此畫面</b>，點擊下方按鈕傳送給官方 LINE 客服，即可為您保留結帳！</p>
            <a href="https://line.me/R/ti/p/@815ikjjr" target="_blank" style="text-decoration: none;">
                <div style="background-color: #06C755; color: white; padding: 10px 20px; border-radius: 20px; font-weight: bold; display: inline-block;">
                    💬 傳送截圖給客服 (@815ikjjr)
                </div>
            </a>
        </div>
        """, unsafe_allow_html=True)
        
        st.caption("※ 金價隨國際市場每日波動，為保障您的權益，請以客服當下報價為準。")

    logo_file = "沐光金網站LOGO-removebg-preview.png"
    if os.path.exists(logo_file):
        col_l, col_logo, col_r = st.columns([2, 1, 2])
        with col_logo: st.image(logo_file, use_container_width=True)
    else:
        st.markdown("<h2 style='text-align: center; color: #B28850;'>沐光金工坊</h2>", unsafe_allow_html=True)
    st.divider()

    with st.sidebar:
        st.markdown("### 🔍 商品篩選")
        search_kw = st.text_input("尋找款式 (輸入關鍵字)：")
        st.markdown("### ⚖ 重量篩選 (錢)")
        if not df_public.empty:
            w_min, w_max = float(df_public["黃金重量(錢)"].min()), float(df_public["黃金重量(錢)"].max())
            if w_min == w_max: w_max += 0.01 
            weight_range = st.slider("選擇重量區間", w_min, w_max, (w_min, w_max), step=0.01, label_visibility="collapsed")
        else:
            weight_range = (0.0, 10.0)
        st.divider()
        st.markdown(f"<div style='color: #333333; font-size: 14px;'>今日黃金參考牌價：<br><b>{current_gold} 元/錢</b></div>", unsafe_allow_html=True)
        st.write("")
        if st.button("🔄 同步最新商品", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    if search_kw:
        df_public = df_public[df_public["品名款式"].str.contains(search_kw, na=False, case=False)]
    df_public = df_public[(df_public["黃金重量(錢)"] >= weight_range[0]) & (df_public["黃金重量(錢)"] <= weight_range[1])]

    if df_public.empty:
        st.info("目前沒有符合條件的款式。如果老闆剛剛有調整設定，請點擊左側『🔄 同步最新商品』。")
    else:
        cols_per_row = 3
        for i in range(0, len(df_public), cols_per_row):
            row_items = df_public.iloc[i:i+cols_per_row]
            cols = st.columns(cols_per_row, gap="large")
            for idx, (row_idx, row) in enumerate(row_items.iterrows()):
                with cols[idx]:
                    with st.container(border=True):
                        if row['產品照片']: st.image(row['產品照片'], use_container_width=True)
                        else: st.markdown("<div style='height:250px; display:flex; align-items:center; justify-content:center; background-color:#FAFAFA; color:#CCC;'>商品照準備中</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='prod-title'>{row['品名款式']}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='prod-weight'>{row['黃金重量(錢)']} 錢</div>", unsafe_allow_html=True)
                        
                        if st.button("🔍 查看商品詳情", key=f"btn_b2c_{row_idx}_{row['品名款式']}", use_container_width=True): show_product_price(row)
            st.write(""); st.write("")
    
    st.stop() # 阻斷 B2C 頁面往下讀取 B2B 程式碼

# ==========================================
# 🛑 路由：B2B 後台管理系統 (需要登入)
# ==========================================

@st.dialog("⚙️ 修改系統全域參數")
def edit_global_params_dialog():
    st.warning("請注意：金價修改將同步影響 B2B 與 B2C 系統的所有即時報價！")
    new_g = st.number_input("📈 新的黃金牌價：", min_value=0, value=current_gold, step=100)
    new_m = st.number_input("🎯 新的預設 B2B 利潤 (%)：", min_value=0.0, value=current_margin, step=1.0)
    admin_pw = st.text_input("🔑 輸入老闆密碼以確認：", type="password")
    
    if st.button("💾 確認並套用", type="primary", use_container_width=True):
        if str(admin_pw) == str(users_db.get(st.session_state.account_id, {}).get("password")):
            sys_config["gold_price"] = new_g
            sys_config["b2b_margin"] = new_m
            save_json(CONFIG_FILE, sys_config)
            st.success("全域參數更新成功！")
            st.rerun()
        else:
            st.error("密碼錯誤，操作無效。")

@st.dialog("📈 更新系統黃金牌價")
def edit_gold_price_dialog():
    st.warning("請注意：修改金價將即時同步更新全站報價！")
    new_g = st.number_input("📈 新的黃金牌價：", min_value=0, value=current_gold, step=100)
    user_pw = st.text_input("🔑 輸入您的密碼以確認：", type="password")
    
    if st.button("💾 確認並套用", type="primary", use_container_width=True):
        if str(user_pw) == str(users_db.get(st.session_state.account_id, {}).get("password")):
            sys_config["gold_price"] = new_g
            save_json(CONFIG_FILE, sys_config)
            st.success("金價更新成功！")
            st.rerun()
        else:
            st.error("密碼錯誤，操作無效。")

@st.dialog("🔑 修改帳號密碼")
def password_modal():
    all_usernames = list(users_db.keys())
    target_user = st.selectbox("選擇要修改密碼的帳號：", all_usernames, format_func=lambda x: f"{x} ({users_db[x]['name']})")
    new_pw = st.text_input("輸入新密碼：", type="password")
    if st.button("💾 儲存修改", type="primary", use_container_width=True):
        if not new_pw: st.warning("❌ 密碼不能為空！")
        else:
            users_db[target_user]["password"] = str(new_pw)
            save_json(USERS_DB_FILE, users_db)
            st.success(f"✅ 已成功將 {target_user} 的密碼更新！若該帳號目前在線上，將被強制登出。")
            st.rerun()

@st.dialog("🎯 設定客戶專屬利潤")
def custom_margin_dialog():
    clients = [k for k, v in users_db.items() if v["role"] == "client"]
    if not clients:
        st.warning("目前沒有客戶可設定。")
        return
    target_user = st.selectbox("選擇客戶：", clients, format_func=lambda x: f"{x} ({users_db[x]['name']})")
    curr_margin = users_db[target_user].get("custom_margin", "")
    new_margin_str = st.text_input("設定專屬利潤 % (留空代表『取消專屬』)：", value=str(curr_margin))
    
    if st.button("💾 儲存利潤設定", type="primary", use_container_width=True):
        if new_margin_str.strip() == "":
            if "custom_margin" in users_db[target_user]: del users_db[target_user]["custom_margin"]
        else:
            try: users_db[target_user]["custom_margin"] = float(new_margin_str)
            except ValueError: st.error("請輸入有效的數字！"); return
        save_json(USERS_DB_FILE, users_db)
        st.success(f"✅ {target_user} 的專屬利潤設定成功！")
        st.rerun()

@st.dialog("🗑 刪除帳號確認")
def delete_account_dialog():
    deletable_users = [k for k, v in users_db.items() if v["role"] != "admin"]
    if not deletable_users: st.info("目前沒有可刪除的帳號。"); return
    target_user = st.selectbox("選擇要刪除的帳號：", deletable_users, format_func=lambda x: f"{x} ({users_db[x]['name']})")
    admin_pw = st.text_input("🔑 輸入老闆密碼以確認：", type="password")
    if st.button("🚨 強制刪除帳號", type="primary", use_container_width=True):
        if str(admin_pw) == str(users_db.get(st.session_state.account_id, {}).get("password")):
            del users_db[target_user]
            save_json(USERS_DB_FILE, users_db)
            settings_changed = False
            for p_name, p_settings in prod_settings.items():
                if p_settings.get("allowed_clients"):
                    allowed_list = [acc.strip() for acc in p_settings["allowed_clients"].split(",")]
                    if target_user in allowed_list:
                        allowed_list.remove(target_user)
                        p_settings["allowed_clients"] = ",".join(allowed_list)
                        settings_changed = True
            if settings_changed: save_json(SETTINGS_FILE, prod_settings)
            st.success(f"✅ 帳號 {target_user} 已徹底刪除！若其在線上將被強制登出。"); st.rerun()
        else: st.error("密碼錯誤。")

@st.dialog("🗑️ 取消訂單確認")
def delete_order_dialog(order_id):
    st.error(f"確定要取消訂單單號：{order_id} 嗎？\n取消後庫存將被釋放回系統，客人也會看到此訂單已取消。")
    admin_pw = st.text_input("🔑 輸入老闆密碼以確認：", type="password", key=f"pw_del_{order_id}")
    if st.button("🚨 確認取消", type="primary", use_container_width=True):
        if str(admin_pw) == str(users_db.get(st.session_state.account_id, {}).get("password")):
            global orders
            for o in orders:
                if o["訂單編號"] == order_id:
                    o["狀態"] = "已取消"
            save_json(DB_FILE, orders)
            st.success("✅ 訂單已移至「已取消」紀錄中！"); st.rerun()
        else: st.error("密碼錯誤。")

@st.dialog("🔥 永久刪除訂單確認")
def hard_delete_order_dialog(order_id):
    st.error(f"即將徹底銷毀訂單單號：{order_id}，此動作無法復原！")
    admin_pw = st.text_input("🔑 輸入老闆密碼以確認：", type="password", key=f"pw_hard_del_{order_id}")
    if st.button("🚨 確認強制刪除", type="primary", use_container_width=True):
        if str(admin_pw) == str(users_db.get(st.session_state.account_id, {}).get("password")):
            global orders
            orders = [o for o in orders if o["訂單編號"] != order_id]
            save_json(DB_FILE, orders)
            st.success("✅ 訂單已徹底從資料庫刪除！"); st.rerun()
        else: st.error("密碼錯誤。")

if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>🔐 B2B 批發查價系統</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            input_user = st.text_input("👤 帳號 (Username)", autocomplete="off")
            input_pwd = st.text_input("🔑 密碼 (Password)", type="password", autocomplete="new-password")
            if st.button("🚀 登入系統", use_container_width=True):
                if input_user in users_db and str(users_db[input_user]["password"]) == str(input_pwd):
                    st.session_state.logged_in = True
                    st.session_state.role = users_db[input_user]["role"]
                    st.session_state.user_name = users_db[input_user]["name"]
                    st.session_state.account_id = input_user 
                    st.session_state.session_pw = str(input_pwd)
                    st.rerun() 
                else:
                    st.error("❌ 帳號或密碼錯誤。")
    st.stop()

with st.sidebar:
    st.success(f"歡迎回來！\n👤 **{st.session_state.user_name}**")
    if st.button("🚪 登出系統", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()
    st.divider()

my_acc = st.session_state.account_id
my_user_data = users_db.get(my_acc, {})
effective_margin = current_margin
if st.session_state.role == "client":
    custom_m = my_user_data.get("custom_margin")
    if custom_m not in [None, ""]: effective_margin = float(custom_m)

df_clean["狀態"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("status", "🆕 未上架"))
df_clean["B2C狀態"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("b2c_status", "❌ 隱藏"))
df_clean["指定帳號"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("allowed_clients", ""))

# B2B 參數
df_clean["💰 B2B指定利潤"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("fixed_profit", 0))
def get_min_profit(x):
    s = prod_settings.get(x, {})
    if "min_b2b_profit" in s: return s["min_b2b_profit"]
    if "lock_tolerance" in s: return abs(s["lock_tolerance"]) 
    return 500
df_clean["🛡️ B2B最低保底利潤"] = df_clean["品名款式"].apply(get_min_profit)

# B2C 參數
df_clean["💰 B2C指定利潤"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("fixed_profit_b2c", 0))
df_clean["🛡️ B2C最低保底利潤"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("min_b2c_profit", 1000))

df_clean["💡今日動態成本"] = np.round((current_gold * df_clean["黃金重量(錢)"]) + df_clean["盤商收取工資"])

# ==========================================
# 🛡 B2C 售價與防虧計算
# ==========================================
def calculate_retail(row):
    cost = row["💡今日動態成本"]
    # 優先使用 B2C 指定利潤
    if row.get("💰 B2C指定利潤", 0) > 0:
        return cost + row["💰 B2C指定利潤"]
        
    level = str(row.get("定價毛利等級", ""))
    if "固定價格" in level: return row.get("手動設定售價(固定商品用)", cost)
    elif "B級" in level: return np.round(cost * 1.16 + 500)
    elif "C級" in level: return np.round(cost * 1.20 + 600)
    else: return cost

df_clean["🏪動態零售價"] = df_clean.apply(calculate_retail, axis=1)
df_clean["原本預期利潤"] = df_clean["🏪動態零售價"] - df_clean["💡今日動態成本"]

def calc_hist_retail(row):
    cost = row["本件真實總成本"]
    if cost <= 0: return 0
    if row.get("💰 B2C指定利潤", 0) > 0:
        return cost + row["💰 B2C指定利潤"]

    level = str(row.get("定價毛利等級", ""))
    if "固定價格" in level: return row.get("手動設定售價(固定商品用)", cost)
    elif "B級" in level: return np.round(cost * 1.16 + 500)
    elif "C級" in level: return np.round(cost * 1.20 + 600)
    else: return cost

df_clean["📜歷史零售價"] = df_clean.apply(calc_hist_retail, axis=1)
df_clean["📜歷史B2C預期利潤"] = df_clean["📜歷史零售價"] - df_clean["本件真實總成本"]

df_clean["💰B2C實賺金額"] = df_clean["🏪動態零售價"] - df_clean["本件真實總成本"]
df_clean["📈B2C實賺毛利率(%)"] = np.where(df_clean["🏪動態零售價"] > 0, (df_clean["💰B2C實賺金額"] / df_clean["🏪動態零售價"]) * 100, 0)
df_clean["💰今日動態淨利"] = df_clean["🏪動態零售價"] - df_clean["💡今日動態成本"]
df_clean["📈今日動態淨利率(%)"] = np.where(df_clean["🏪動態零售價"] > 0, (df_clean["💰今日動態淨利"] / df_clean["🏪動態零售價"]) * 100, 0)

df_clean["🔒B2C解鎖利潤"] = np.round(df_clean["📜歷史B2C預期利潤"] * 0.50)

# 🚀 B2C 鎖定邏輯改寫
df_clean["🔒B2C自動鎖定"] = np.where(
    df_clean["💰 B2C指定利潤"] > 0,
    (df_clean["本件真實總成本"] > 0) & ((df_clean["🏪動態零售價"] - df_clean["本件真實總成本"]) < df_clean["🛡️ B2C最低保底利潤"]),
    (df_clean["本件真實總成本"] > 0) & (df_clean["💰B2C實賺金額"] < df_clean["🔒B2C解鎖利潤"])
)

# ==========================================
# 🛡 B2B 售價與防虧計算
# ==========================================
df_clean["💡理想批發值"] = df_clean["本件真實總成本"] + df_clean["💰 B2B指定利潤"]

df_clean["🔥廠商批發價"] = np.where(
    df_clean["💰 B2B指定利潤"] > 0,
    df_clean["💡今日動態成本"] + df_clean["💰 B2B指定利潤"],
    np.round(df_clean["💡今日動態成本"] + (df_clean["原本預期利潤"] * (effective_margin / 100)))
)

df_clean["💰實賺金額(歷史比)"] = df_clean["🔥廠商批發價"] - df_clean["本件真實總成本"]
df_clean["📈實賺毛利率(%)"] = np.where(df_clean["🔥廠商批發價"] > 0, (df_clean["💰實賺金額(歷史比)"] / df_clean["🔥廠商批發價"]) * 100, 0)

df_clean["📜歷史批發價"] = np.where(
    df_clean["💰 B2B指定利潤"] > 0,
    df_clean["💡理想批發值"],  
    np.round(df_clean["本件真實總成本"] + (df_clean["📜歷史B2C預期利潤"] * (effective_margin / 100)))
)
df_clean["📜歷史B2B預期利潤"] = df_clean["📜歷史批發價"] - df_clean["本件真實總成本"]
df_clean["🔒B2B解鎖利潤"] = np.round(df_clean["📜歷史B2C預期利潤"] * 0.30)

df_clean["🔒B2B自動鎖定"] = np.where(
    df_clean["💰 B2B指定利潤"] > 0,
    (df_clean["本件真實總成本"] > 0) & ((df_clean["🔥廠商批發價"] - df_clean["本件真實總成本"]) < df_clean["🛡️ B2B最低保底利潤"]),
    (df_clean["本件真實總成本"] > 0) & (df_clean["💰實賺金額(歷史比)"] < df_clean["🔒B2B解鎖利潤"])
)

def get_lock_status(row):
    msgs = []
    if row.get("🔒B2B自動鎖定"): msgs.append("🚫 B2B鎖定")
    if row.get("🔒B2C自動鎖定"): msgs.append("🚫 B2C鎖定")
    if not msgs: return "✅ 正常"
    return " + ".join(msgs)

df_clean["防虧狀態"] = df_clean.apply(get_lock_status, axis=1)

# ==========================================
# 📦 全域可用庫存計算
# ==========================================
reserved_stock = {}
for o in orders:
    if o.get("狀態") in ["待派單", "待檢貨", "待出貨"]:
        for item in o.get("購買明細", []):
            name = item.get("品名款式", "")
            if name: reserved_stock[name] = reserved_stock.get(name, 0) + item.get("數量", 0)

for acc, cart_items in all_carts.items():
    if acc != my_acc: 
        for name, qty in cart_items.items():
            reserved_stock[name] = reserved_stock.get(name, 0) + qty

df_clean["網頁可用庫存"] = df_clean["目前庫存量"] - df_clean["品名款式"].map(reserved_stock).fillna(0)
my_cart = all_carts.get(my_acc, {})
df_clean["🛒 我的購物車"] = df_clean["品名款式"].apply(lambda x: my_cart.get(x, 0))

# ==========================================
# 💎 路由：B2C 官方型錄 (給消費者看)
# ==========================================
if not is_b2b:
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
        [data-testid="stSidebar"] {{ background-color: transparent !important; }}
        [data-testid="stSidebar"] > div:first-child {{
            background-color: rgba(255, 255, 255, 0.4) !important;
            backdrop-filter: blur(15px);
            border-right: 1px solid rgba(255, 255, 255, 0.4);
        }}
        [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label, [data-testid="stSidebar"] div {{
            color: #333333 !important;
        }}
        [data-testid="stTextInput"] div[data-baseweb="input"] {{
            background-color: rgba(255, 255, 255, 0.8) !important;
            color: #333333 !important;
        }}
        """
    else:
        bg_css = ".stApp { background-color: #FFFFFF; }"

    st.markdown(f"""
    <style>
    {bg_css}
    .st-emotion-cache-1rqebx {{display: none;}}
    footer {{visibility: hidden;}}
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: rgba(255, 255, 255, 0.95) !important;
        border-radius: 15px !important;
        border: 1px solid rgba(178, 136, 80, 0.2) !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        padding: 10px;
    }}
    .prod-title {{ text-align: center; font-size: 18px; font-weight: 600; color: #333333; margin-top: 10px; margin-bottom: 0px; }}
    .prod-weight {{ text-align: center; font-size: 14px; color: #666666; margin-bottom: 10px; }}
    div[data-testid="stButton"] button {{
        border-radius: 20px; border: 1px solid #B28850; color: #B28850; background-color: rgba(255,255,255,0.8); transition: all 0.3s;
    }}
    div[data-testid="stButton"] button:hover {{ background-color: #B28850; color: #FFFFFF; }}
    div[data-testid="stButton"] button[disabled] {{
        border: 1px solid #CCCCCC !important; color: #999999 !important; background-color: #F0F0F0 !important;
    }}
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <a href="https://line.me/R/ti/p/@815ikjjr" target="_blank" style="position: fixed; bottom: 30px; right: 30px; z-index: 9999; transition: transform 0.3s;" onmouseover="this.style.transform='scale(1.1)'" onmouseout="this.style.transform='scale(1)'">
        <img src="https://upload.wikimedia.org/wikipedia/commons/4/41/LINE_logo.svg" width="60" height="60" style="filter: drop-shadow(2px 4px 6px rgba(0,0,0,0.3));">
    </a>
    """, unsafe_allow_html=True)

    def is_public_item(row):
        item_name = row["品名款式"]
        settings = prod_settings.get(item_name, {})
        b2c_status = str(settings.get("b2c_status", "❌ 隱藏"))
        is_locked = row.get("🔒B2C自動鎖定", False)
        has_stock = row.get("網頁可用庫存", 0) > 0  
        return ("✅ 顯示" in b2c_status) and not is_locked and has_stock

    df_clean["對外公開"] = df_clean.apply(is_public_item, axis=1)
    df_public = df_clean[df_clean["對外公開"] == True].copy()

    @st.dialog("✨ 產品詳情與專屬報價")
    def show_product_price(row):
        st.image(row['產品照片'], use_container_width=True)
        st.markdown(f"<h3 style='text-align: center; color: #333;'>{row['品名款式']}</h3>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align: center; color: #B28850; font-weight: bold; font-size: 16px;'>⚖ 黃金重量：{row['黃金重量(錢)']} 錢</p>", unsafe_allow_html=True)
        
        st.markdown(f"<div style='text-align: center; background-color: #FDFBF7; padding: 15px; border-radius: 10px; margin-top: 15px;'><span style='font-size: 18px; font-weight: bold; color: #B28850;'>✨ 歡迎截圖私訊客服取得即時報價</span></div>", unsafe_allow_html=True)
        
        st.markdown("""
        <div style="margin-top: 20px; text-align: center; padding: 15px; background-color: #f0fdf4; border: 1px solid #06C755; border-radius: 10px;">
            <p style="color: #06C755; font-weight: bold; margin-bottom: 5px; font-size: 16px;">🛒 如何購買此商品？</p>
            <p style="color: #555; font-size: 14px; margin-bottom: 12px;">請直接<b>截圖此畫面</b>，點擊下方按鈕傳送給官方 LINE 客服，即可為您保留結帳！</p>
            <a href="https://line.me/R/ti/p/@815ikjjr" target="_blank" style="text-decoration: none;">
                <div style="background-color: #06C755; color: white; padding: 10px 20px; border-radius: 20px; font-weight: bold; display: inline-block;">
                    💬 傳送截圖給客服 (@815ikjjr)
                </div>
            </a>
        </div>
        """, unsafe_allow_html=True)
        
        st.caption("※ 金價隨國際市場每日波動，為保障您的權益，請以客服當下報價為準。")

    logo_file = "沐光金網站LOGO-removebg-preview.png"
    if os.path.exists(logo_file):
        col_l, col_logo, col_r = st.columns([2, 1, 2])
        with col_logo: st.image(logo_file, use_container_width=True)
    else:
        st.markdown("<h2 style='text-align: center; color: #B28850;'>沐光金工坊</h2>", unsafe_allow_html=True)
    st.divider()

    with st.sidebar:
        st.markdown("### 🔍 商品篩選")
        search_kw = st.text_input("尋找款式 (輸入關鍵字)：")
        st.markdown("### ⚖ 重量篩選 (錢)")
        if not df_public.empty:
            w_min, w_max = float(df_public["黃金重量(錢)"].min()), float(df_public["黃金重量(錢)"].max())
            if w_min == w_max: w_max += 0.01 
            weight_range = st.slider("選擇重量區間", w_min, w_max, (w_min, w_max), step=0.01, label_visibility="collapsed")
        else:
            weight_range = (0.0, 10.0)
        st.divider()
        st.markdown(f"<div style='color: #333333; font-size: 14px;'>今日黃金參考牌價：<br><b>{current_gold} 元/錢</b></div>", unsafe_allow_html=True)
        st.write("")
        if st.button("🔄 同步最新商品", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    if search_kw:
        df_public = df_public[df_public["品名款式"].str.contains(search_kw, na=False, case=False)]
    df_public = df_public[(df_public["黃金重量(錢)"] >= weight_range[0]) & (df_public["黃金重量(錢)"] <= weight_range[1])]

    if df_public.empty:
        st.info("目前沒有符合條件的款式。如果老闆剛剛有調整設定，請點擊左側『🔄 同步最新商品』。")
    else:
        cols_per_row = 3
        for i in range(0, len(df_public), cols_per_row):
            row_items = df_public.iloc[i:i+cols_per_row]
            cols = st.columns(cols_per_row, gap="large")
            for idx, (row_idx, row) in enumerate(row_items.iterrows()):
                with cols[idx]:
                    with st.container(border=True):
                        if row['產品照片']: st.image(row['產品照片'], use_container_width=True)
                        else: st.markdown("<div style='height:250px; display:flex; align-items:center; justify-content:center; background-color:#FAFAFA; color:#CCC;'>商品照準備中</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='prod-title'>{row['品名款式']}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='prod-weight'>{row['黃金重量(錢)']} 錢</div>", unsafe_allow_html=True)
                        
                        if st.button("🔍 查看商品詳情", key=f"btn_b2c_{row_idx}_{row['品名款式']}", use_container_width=True): show_product_price(row)
            st.write(""); st.write("")
    
    st.stop() # 阻斷 B2C 頁面往下讀取 B2B 程式碼

# ==========================================
# 🛑 路由：B2B 後台管理系統 (需要登入)
# ==========================================

@st.dialog("⚙️ 修改系統全域參數")
def edit_global_params_dialog():
    st.warning("請注意：金價修改將同步影響 B2B 與 B2C 系統的所有即時報價！")
    new_g =
