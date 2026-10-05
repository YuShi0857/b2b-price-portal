import streamlit as st
import requests
import pandas as pd
import urllib.parse
import numpy as np
import json
import os
import base64
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
    "picker1": {"password": "123", "role": "picker", "name": "內部檢貨員A"},
    "streamer1": {"password": "123", "role": "broadcaster", "name": "沐光金專用"} # 預設直播間帳號
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
    url = f"{API_URL}?v=3&api=true&APIKey={API_KEY}"
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

df_clean["狀態"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("status", "🆕 未上架"))
df_clean["B2C狀態"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("b2c_status", "❌ 隱藏"))
df_clean["指定帳號"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("allowed_clients", ""))

df_clean["B2B指定利潤"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("b2b_target_profit", 0))
df_clean["B2B防虧底線"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("b2b_min_profit", 0))
df_clean["B2C指定利潤"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("b2c_target_profit", 0))
df_clean["B2C防虧底線"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("b2c_min_profit", 0))

df_clean["💡今日動態成本"] = np.round((current_gold * df_clean["黃金重量(錢)"]) + df_clean["盤商收取工資"])

def calculate_retail(row):
    level = str(row.get("定價毛利等級", ""))
    cost = row["💡今日動態成本"]
    if "B級" in level: return np.round(cost * 1.16 + 500)
    elif "C級" in level: return np.round(cost * 1.20 + 600)
    else: return cost

df_clean["🏪基礎B2C售價"] = df_clean.apply(calculate_retail, axis=1)
df_clean["基礎預期利潤"] = df_clean["🏪基礎B2C售價"] - df_clean["💡今日動態成本"]

df_clean["🏪動態零售價"] = np.where(df_clean["B2C指定利潤"] > 0, df_clean["💡今日動態成本"] + df_clean["B2C指定利潤"], df_clean["🏪基礎B2C售價"])

effective_margin = current_margin
if st.session_state.get("role") == "client":
    custom_m = users_db.get(st.session_state.get("account_id"), {}).get("custom_margin")
    if custom_m not in [None, ""]: effective_margin = float(custom_m)

df_clean["🔥廠商批發價"] = np.where(
    df_clean["B2B指定利潤"] > 0,
    df_clean["💡今日動態成本"] + df_clean["B2B指定利潤"],
    np.round(df_clean["💡今日動態成本"] + (df_clean["基礎預期利潤"] * (effective_margin / 100)))
)

df_clean["💰B2B實賺金額"] = df_clean["🔥廠商批發價"] - df_clean["本件真實總成本"]
df_clean["💰B2C實賺金額"] = df_clean["🏪動態零售價"] - df_clean["本件真實總成本"]
df_clean["📈實賺毛利率(%)"] = np.where(df_clean["🔥廠商批發價"] > 0, (df_clean["💰B2B實賺金額"] / df_clean["🔥廠商批發價"]) * 100, 0)

def calc_hist_retail(row):
    level = str(row.get("定價毛利等級", ""))
    cost = row["本件真實總成本"]
    if cost <= 0: return 0
    if "B級" in level: return np.round(cost * 1.16 + 500)
    elif "C級" in level: return np.round(cost * 1.20 + 600)
    else: return cost

df_clean["📜歷史零售價"] = df_clean.apply(calc_hist_retail, axis=1)
df_clean["📜歷史B2C預期利潤"] = df_clean["📜歷史零售價"] - df_clean["本件真實總成本"]

df_clean["🔒B2B解鎖底線"] = np.where(df_clean["B2B防虧底線"] > 0, df_clean["B2B防虧底線"], np.round(df_clean["📜歷史B2C預期利潤"] * 0.30))
df_clean["🔒B2C解鎖底線"] = np.where(df_clean["B2C防虧底線"] > 0, df_clean["B2C防虧底線"], np.round(df_clean["📜歷史B2C預期利潤"] * 0.50))

df_clean["🔒B2B自動鎖定"] = (df_clean["本件真實總成本"] > 0) & (df_clean["💰B2B實賺金額"] < df_clean["🔒B2B解鎖底線"])
df_clean["🔒B2C自動鎖定"] = (df_clean["本件真實總成本"] > 0) & (df_clean["💰B2C實賺金額"] < df_clean["🔒B2C解鎖底線"])

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

current_acc = st.session_state.get("account_id") if st.session_state.get("logged_in") else None

for acc, cart_items in all_carts.items():
    if acc != current_acc: 
        for name, qty in cart_items.items():
            reserved_stock[name] = reserved_stock.get(name, 0) + qty

df_clean["網頁可用庫存"] = df_clean["目前庫存量"] - df_clean["品名款式"].map(reserved_stock).fillna(0)
my_cart = all_carts.get(current_acc, {})
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
        st.markdown(f"<p style='text-align: center; color: #B28850; font-weight: bold; font-size: 16px;'>⚖️ 黃金重量：{row['黃金重量(錢)']} 錢</p>", unsafe_allow_html=True)
        
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
        st.markdown("<h2 style='text-align: center; color: #B28850;'>沐光金
