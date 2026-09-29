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
# 判斷網址是否有 /?b2b=true
is_b2b = st.query_params.get("b2b") == "true"

if is_b2b:
    st.set_page_config(page_title="B2B 批發查價台", layout="wide")
else:
    st.set_page_config(page_title="沐光金工坊 MU GLOW | 官方型錄", page_icon="✨", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# 🌟 系統共用模組與資料讀取
# ==========================================
def load_json(file_path, default_data):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default_data

def save_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

SETTINGS_FILE = "product_settings.json" 
CONFIG_FILE = "system_config.json" 
prod_settings = load_json(SETTINGS_FILE, {})
sys_config = load_json(CONFIG_FILE, {"gold_price": 10000, "b2b_margin": 35.0})

current_gold = sys_config.get("gold_price", 10000)
current_margin = sys_config.get("b2b_margin", 35.0)

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

# 準備基礎資料
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

df_clean["💡今日動態成本"] = np.round((current_gold * df_clean["黃金重量(錢)"]) + df_clean["盤商收取工資"])

def calculate_retail(row):
    level = str(row.get("定價毛利等級", ""))
    cost = row["💡今日動態成本"]
    if "固定價格" in level: return row.get("手動設定售價(固定商品用)", cost)
    elif "B級" in level: return np.round(cost * 1.16 + 500)
    elif "C級" in level: return np.round(cost * 1.20 + 600)
    else: return cost

df_clean["🏪動態零售價"] = df_clean.apply(calculate_retail, axis=1)
df_clean["原本預期利潤"] = df_clean["🏪動態零售價"] - df_clean["💡今日動態成本"]

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

    def is_public_item(item_name):
        settings = prod_settings.get(item_name, {})
        b2c_status = str(settings.get("b2c_status", "❌ 隱藏"))
        return "✅ 顯示" in b2c_status

    df_clean["對外公開"] = df_clean["品名款式"].apply(is_public_item)
    df_public = df_clean[df_clean["對外公開"] == True].copy()

    @st.dialog("💎 產品詳情與即時報價")
    def show_product_price(row):
        st.image(row['產品照片'], use_container_width=True)
        st.markdown(f"<h3 style='text-align: center; color: #333;'>{row['品名款式']}</h3>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align: center; color: #666;'>黃金重量：{row['黃金重量(錢)']} 錢</p>", unsafe_allow_html=True)
        price = int(row['🏪動態零售價'])
        st.markdown(f"<div style='text-align: center; background-color: #FDFBF7; padding: 15px; border-radius: 10px; margin-top: 15px;'><span style='font-size: 16px; color: #888;'>今日試算售價</span><br><span style='font-size: 28px; font-weight: bold; color: #B28850;'>NT$ {price:,}</span></div>", unsafe_allow_html=True)
        st.caption(f"※ 今日金價基準：{current_gold} 元/錢。金價隨國際市場每日波動，此為當前即時試算報價。")

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
        st.markdown("### ⚖️ 重量篩選 (錢)")
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
            for idx, (_, row) in enumerate(row_items.iterrows()):
                with cols[idx]:
                    with st.container(border=True):
                        if row['產品照片']: st.image(row['產品照片'], use_container_width=True)
                        else: st.markdown("<div style='height:250px; display:flex; align-items:center; justify-content:center; background-color:#FAFAFA; color:#CCC;'>商品照準備中</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='prod-title'>{row['品名款式']}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='prod-weight'>{row['黃金重量(錢)']} 錢</div>", unsafe_allow_html=True)
                        
                        stock = int(row['目前庫存量'])
                        if stock > 0:
                            if st.button("🔍 查看即時報價", key=f"btn_{row['品名款式']}", use_container_width=True): show_product_price(row)
                        else:
                            st.button("🚫 目前缺貨中", key=f"btn_out_{row['品名款式']}", disabled=True, use_container_width=True)
            st.write(""); st.write("")
    
    st.stop()

# ==========================================
# 🛑 路由：B2B 後台管理系統 (需要登入)
# ==========================================
DB_FILE = "orders_db.json"
USERS_DB_FILE = "users_db.json"
CARTS_FILE = "carts_db.json" 
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

if "logged_in" not in st.session_state:
    saved_user = st.query_params.get("user")
    if saved_user and saved_user in users_db:
        st.session_state.logged_in = True
        st.session_state.role = users_db[saved_user]["role"]
        st.session_state.user_name = users_db[saved_user]["name"]
        st.session_state.account_id = saved_user
    else:
        st.session_state.logged_in = False

if "client_page" not in st.session_state: st.session_state.client_page = 1
if "admin_page" not in st.session_state: st.session_state.admin_page = 1

def reset_client_page(): st.session_state.client_page = 1
def reset_admin_page(): st.session_state.admin_page = 1

@st.dialog("⚙️ 修改系統全域參數")
def edit_global_params_dialog():
    st.warning("請注意：金價修改將同步影響 B2B 與 B2C 系統的所有即時報價！")
    new_g = st.number_input("📈 新的黃金牌價：", min_value=0, value=current_gold, step=100)
    new_m = st.number_input("🎯 新的預設 B2B 利潤 (%)：", min_value=0.0, value=current_margin, step=1.0)
    admin_pw = st.text_input("🔑 輸入老闆密碼以確認：", type="password")
    
    if st.button("💾 確認並套用", type="primary", use_container_width=True):
        if admin_pw == users_db.get(st.session_state.account_id, {}).get("password"):
            sys_config["gold_price"] = new_g
            sys_config["b2b_margin"] = new_m
            save_json(CONFIG_FILE, sys_config)
            st.success("全域參數更新成功！")
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
            users_db[target_user]["password"] = new_pw
            save_json(USERS_DB_FILE, users_db)
            st.success(f"✅ 已成功將 {target_user} 的密碼更新！")
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

@st.dialog("🗑️ 刪除帳號確認")
def delete_account_dialog():
    deletable_users = [k for k, v in users_db.items() if v["role"] != "admin"]
    if not deletable_users: st.info("目前沒有可刪除的帳號。"); return
    target_user = st.selectbox("選擇要刪除的帳號：", deletable_users, format_func=lambda x: f"{x} ({users_db[x]['name']})")
    admin_pw = st.text_input("🔑 輸入老闆密碼以確認：", type="password")
    if st.button("🚨 強制刪除帳號", type="primary", use_container_width=True):
        if admin_pw == users_db.get(st.session_state.account_id, {}).get("password"):
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
            st.success(f"✅ 帳號 {target_user} 已徹底刪除！"); st.rerun()
        else: st.error("密碼錯誤。")

@st.dialog("🗑️ 刪除訂單確認")
def delete_order_dialog(order_id):
    st.error(f"即將徹底銷毀訂單單號：{order_id}，此動作無法復原！")
    admin_pw = st.text_input("🔑 輸入老闆密碼以確認：", type="password", key=f"pw_del_{order_id}")
    if st.button("🚨 確認強制刪除", type="primary", use_container_width=True):
        if admin_pw == users_db.get(st.session_state.account_id, {}).get("password"):
            global orders
            orders = [o for o in orders if o["訂單編號"] != order_id]
            save_json(DB_FILE, orders)
            st.success("✅ 訂單已徹底刪除！"); st.rerun()
        else: st.error("密碼錯誤。")

if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>🔐 B2B 批發查價系統</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            input_user = st.text_input("👤 帳號 (Username)", autocomplete="off")
            input_pwd = st.text_input("🔑 密碼 (Password)", type="password", autocomplete="new-password")
            if st.button("🚀 登入系統", use_container_width=True):
                if input_user in users_db and users_db[input_user]["password"] == input_pwd:
                    st.session_state.logged_in = True
                    st.session_state.role = users_db[input_user]["role"]
                    st.session_state.user_name = users_db[input_user]["name"]
                    st.session_state.account_id = input_user 
                    st.query_params["user"] = input_user 
                    st.rerun() 
                else:
                    st.error("❌ 帳號或密碼錯誤。")
    st.stop()

with st.sidebar:
    st.success(f"歡迎回來！\n👤 **{st.session_state.user_name}**")
    if st.button("🚪 登出系統", use_container_width=True):
        st.session_state.logged_in = False
        if "user" in st.query_params: del st.query_params["user"]
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
df_clean["👁️ 指定帳號"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("allowed_clients", ""))
df_clean["💰 手動批發價"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("fixed_price", 0))

df_clean["🔥廠商批發價"] = np.where(
    df_clean["💰 手動批發價"] > 0,
    df_clean["💰 手動批發價"],
    np.round(df_clean["💡今日動態成本"] + (df_clean["原本預期利潤"] * (effective_margin / 100)))
)
df_clean["💰實賺金額(歷史比)"] = df_clean["🔥廠商批發價"] - df_clean["本件真實總成本"]
df_clean["📈實賺毛利率(%)"] = np.where(df_clean["🔥廠商批發價"] > 0, (df_clean["💰實賺金額(歷史比)"] / df_clean["🔥廠商批發價"]) * 100, 0)

reserved_stock = {}
for o in orders:
    if o["狀態"] in ["待派單", "待檢貨", "待出貨"]:
        for item in o["購買明細"]:
            name = item["品名款式"]
            reserved_stock[name] = reserved_stock.get(name, 0) + item["數量"]
for acc, cart_items in all_carts.items():
    if acc != my_acc: 
        for name, qty in cart_items.items():
            reserved_stock[name] = reserved_stock.get(name, 0) + qty

df_clean["網頁可用庫存"] = df_clean["目前庫存量"] - df_clean["品名款式"].map(reserved_stock).fillna(0)
my_cart = all_carts.get(my_acc, {})
df_clean["🛒 我的購物車"] = df_clean["品名款式"].apply(lambda x: my_cart.get(x, 0))

# 畫面 B2B 前台 (Client)
if st.session_state.role == "client":
    tab1, tab2, tab3 = st.tabs(["🛍️ 線上批發型錄", "🛒 我的購物車與結帳", "📜 歷史結案明細"])
    with tab1:
        col_info, col_btn = st.columns([4, 1])
        with col_info:
            st.info(f"📈 今日系統黃金牌價： **{current_gold}** 元/錢" + (f" (專屬利潤計算)" if my_user_data.get("custom_margin") not in [None, ""] else ""))
        with col_btn:
            if st.button("🔄 抓取最新庫存", use_container_width=True, type="primary"): st.rerun()
                
        df_client_view = df_clean[df_clean["網頁可用庫存"] > 0].copy()
        
        with st.expander("🔍 搜尋與篩選", expanded=False):
            search_kw = st.text_input("🔑 關鍵字搜尋：", on_change=reset_client_page)
            if not df_client_view.empty:
                w_min, w_max = float(df_client_view["黃金重量(錢)"].min()), float(df_client_view["黃金重量(錢)"].max())
                if w_min == w_max: w_max += 0.01 
                weight_range = st.slider("⚖️ 重量區間 (錢)", w_min, w_max, (w_min, w_max), step=0.01, on_change=reset_client_page)
            else: weight_range = (0.0, 10.0)

        def can_see(row):
            user = st.session_state.account_id
            is_restricted = users_db.get(user, {}).get("is_restricted", False)
            status = row["狀態"]
            allowed_str = str(row["👁️ 指定帳號"]).strip()
            if status == "🗑️ 隱藏": return False
            if not is_restricted: return status == "✅ 已上架"
            else: return user in [acc.strip() for acc in allowed_str.split(",")] if allowed_str else False

        if not df_client_view.empty:
            df_client_view = df_client_view[df_client_view.apply(can_see, axis=1)]
            df_client_view = df_client_view[(df_client_view["黃金重量(錢)"] >= weight_range[0]) & (df_client_view["黃金重量(錢)"] <= weight_range[1])]
            if search_kw: 
                df_client_view = df_client_view[df_client_view["品名款式"].str.contains(search_kw, na=False, case=False) | df_client_view["商品專屬編號"].str.contains(search_kw, na=False, case=False)]
        
        if not df_client_view.empty:
            client_display = df_client_view[["🛒 我的購物車", "產品照片", "商品專屬編號", "品名款式", "網頁可用庫存", "黃金重量(錢)", "🔥廠商批發價"]]
            total_items = len(client_display)
            total_pages = max(1, int(np.ceil(total_items / ITEMS_PER_PAGE)))
            if st.session_state.client_page > total_pages: st.session_state.client_page = 1
            
            st.markdown("### 🛍️ 挑選商品 (即時鎖庫存)")
            col_p_prev, col_p_info, col_p_next = st.columns([1, 2, 1])
            with col_p_prev:
                if st.button("⬅️ 上一頁", key="c_prev_top", disabled=st.session_state.client_page <= 1, use_container_width=True): st.session_state.client_page -= 1; st.rerun()
            with col_p_info: st.markdown(f"<div style='text-align: center; padding-top: 5px;'><b>第 {st.session_state.client_page} / {total_pages} 頁</b> (共 {total_items} 件)</div>", unsafe_allow_html=True)
            with col_p_next:
                if st.button("下一頁 ➡️", key="c_next_top", disabled=st.session_state.client_page >= total_pages, use_container_width=True): st.session_state.client_page += 1; st.rerun()

            start_idx = (st.session_state.client_page - 1) * ITEMS_PER_PAGE
            page_df = client_display.iloc[start_idx : start_idx + ITEMS_PER_PAGE]
            
            edited_client = st.data_editor(
                page_df, use_container_width=True, hide_index=True, height=600,
                disabled=["產品照片", "商品專屬編號", "品名款式", "網頁可用庫存", "黃金重量(錢)", "🔥廠商批發價"],
                column_config={"🛒 我的購物車": st.column_config.NumberColumn("🛒 加入車內", min_value=0, step=1), "產品照片": st.column_config.ImageColumn("產品照片"), "網頁可用庫存": st.column_config.NumberColumn("目前庫存", format="%d 件"), "🔥廠商批發價": st.column_config.NumberColumn("🔥廠商批發價", format="$%d")}
            )
            
            cart_changed = False
            for _, row in edited_client.iterrows():
                name = row["品名款式"]
                valid_qty = min(int(row["🛒 我的購物車"]), int(row["網頁可用庫存"]))
                if valid_qty != my_cart.get(name, 0):
                    if valid_qty > 0: my_cart[name] = valid_qty
                    elif name in my_cart: del my_cart[name]
                    cart_changed = True
            
            if cart_changed:
                all_carts[my_acc] = my_cart
                save_json(CARTS_FILE, all_carts)
                st.rerun()
        else: st.info("目前沒有符合條件的商品。")
            
    with tab2:
        col_title, col_btn = st.columns([4, 1])
        with col_title: st.markdown("### 🛒 結帳與預約出貨")
        with col_btn:
            if st.button("🔄 重整購物車", use_container_width=True): st.rerun()
            
        if not my_cart: st.warning("您的購物車是空的，快去型錄挑選吧！")
        else:
            cart_data = []
            total_amount = 0
            for name, qty in my_cart.items():
                row = df_clean[df_clean["品名款式"] == name]
                if not row.empty:
                    price = int(row.iloc[0]["🔥廠商批發價"])
                    sku = str(row.iloc[0].get("商品專屬編號", ""))
                    subtotal = price * qty
                    total_amount += subtotal
                    cart_data.append({"商品專屬編號": sku, "品名款式": name, "數量": qty, "單價": price, "小計": subtotal, "重量(錢)": row.iloc[0]["黃金重量(錢)"]})
            
            st.table(pd.DataFrame(cart_data))
            st.markdown(f"#### 💰 預計總金額： NT$ {total_amount:,}")
            st.divider()
            
            col_d, col_t = st.columns(2)
            with col_d: live_date = st.date_input("🗓️ 預計直播日期", value=date.today() + timedelta(days=5))
            with col_t: meet_time = st.text_input("⏰ 當天見面與點交時間", placeholder="下午2:00")
            
            urgent_approved = False
            if (live_date - date.today()).days < 5:
                st.error("🚨 【急件注意】距離直播日期不足 5 天！為確保作業流程，急件請直接聯絡您的專屬業務，無法透過系統自助下單。")
                urgent_approved = st.checkbox("☑️ 我已與業務確認，並取得同意送出此急件單")
                allow_submit = urgent_approved
            else: allow_submit = True
                
            if allow_submit and st.button("🚀 確認無誤，送出預約單", type="primary"):
                if not meet_time: st.warning("⚠️ 請填寫見面時間！")
                else:
                    new_order = {
                        "訂單編號": datetime.now().strftime("%Y%m%d%H%M%S"), "客戶名稱": st.session_state.user_name, "帳號": my_acc, "下單時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "預約直播日": str(live_date) + (" 🚨[急件]" if urgent_approved else ""), "見面時間": meet_time, "當時金價": current_gold, "總金額": total_amount, 
                        "狀態": "待派單", "購買明細": cart_data, "客戶簽名": "", "結案時間": "", "結案業務": "", "負責檢貨員": ""
                    }
                    orders.append(new_order)
                    save_json(DB_FILE, orders)
                    all_carts[my_acc] = {}
                    save_json(CARTS_FILE, all_carts)
                    st.success(f"🎉 預約成功！單號：{new_order['訂單編號']} (已送出等候老闆派單)"); st.rerun()

    with tab3:
        st.markdown('<style>iframe[title="streamlit_drawable_canvas.st_canvas"] {pointer-events: none;}</style>', unsafe_allow_html=True)
        my_closed_orders = [o for o in orders if o.get("帳號") == my_acc and o["狀態"] == "已結案"]
        if my_closed_orders:
            st.metric(label="🌟 累積配合的總金額 (GMV)", value=f"NT$ {sum(o['總金額'] for o in my_closed_orders):,}")
            for o in reversed(my_closed_orders):
                with st.expander(f"📦 {o['下單時間']} | 單號: {o['訂單編號']} | 實際總額: ${o['總金額']:,} ✅"):
                    st.write(f"**結案業務：** {o.get('結案業務', '無紀錄')}")
                    sig = o.get('客戶簽名', '')
                    if isinstance(sig, dict): st_canvas(initial_drawing=sig, stroke_width=4, stroke_color="#000000", background_color="#FFFFFF", height=150, width=250, drawing_mode="freedraw", key=f"client_sig_{o['訂單編號']}", update_streamlit=False)
                    st.table(pd.DataFrame(o["購買明細"]))
        else: st.info("您目前還沒有完成結案的訂單。")

# 畫面 作業端 (Picker)
elif st.session_state.role == "picker":
    st.title("📦 內部檢貨作業台")
    my_pick_orders = [o for o in orders if o["狀態"] == "待檢貨" and o.get("負責檢貨員") == my_acc]
    if not my_pick_orders: st.success("目前沒有需要您處理的檢貨單！")
    else:
        for o in my_pick_orders:
            with st.expander(f"🛒 需檢貨：{o['客戶名稱']} | 單號：{o['訂單編號']}", expanded=True):
                st.table(pd.DataFrame(o["購買明細"])[["商品專屬編號", "品名款式", "數量"]])
                if st.button("✅ 檢貨完畢，轉交業務", type="primary", key=f"pick_done_{o['訂單編號']}", use_container_width=True):
                    for raw_o in orders:
                        if raw_o['訂單編號'] == o['訂單編號']: raw_o['狀態'] = "待出貨"
                    save_json(DB_FILE, orders); st.rerun()

# 畫面 業務端 (Operator)
elif st.session_state.role == "operator":
    st.title("💼 業務現場點交台")
    op_tab1, op_tab2 = st.tabs(["📝 待出貨 (點交中)", "⏪ 近期結案單 (1小時內可撤回)"])
    with op_tab1:
        pending_orders = [o for o in orders if o["狀態"] == "待出貨"]
        if not pending_orders: st.success("目前沒有需要點交的預約單！")
        else:
            for o in pending_orders:
                with st.expander(f"📝 {o['預約直播日']} | 客戶：{o['客戶名稱']} | 單號：{o['訂單編號']}", expanded=False):
                    op_df = pd.DataFrame(o["購買明細"])
                    op_df.insert(0, "✅ 實際售出數量", op_df["數量"]) 
                    edited_op = st.data_editor(op_df[["✅ 實際售出數量", "商品專屬編號", "品名款式", "單價", "數量"]], hide_index=True, use_container_width=True, key=f"editor_{o['訂單編號']}")
                    new_total = sum(row["✅ 實際售出數量"] * row["單價"] for _, row in edited_op.iterrows())
                    st.markdown(f"### 💰 結算應收總額： NT$ {new_total:,}")
                    canvas_result = st_canvas(fill_color="rgba(255, 255, 255, 1)", stroke_width=4, stroke_color="#000000", background_color="#FFFFFF", height=200, width=350, drawing_mode="freedraw", key=f"canvas_{o['訂單編號']}")
                    if st.button("✅ 確認結案並送出", type="primary", key=f"btn_{o['訂單編號']}"):
                        if canvas_result.json_data is None or len(canvas_result.json_data.get("objects", [])) == 0: st.error("⚠️ 請客戶手寫簽名！")
                        else:
                            final_items = [{"商品專屬編號": r.get("商品專屬編號", ""), "品名款式": r["品名款式"], "數量": int(r["✅ 實際售出數量"]), "單價": r["單價"], "小計": int(r["✅ 實際售出數量"] * r["單價"])} for _, r in edited_op.iterrows() if r["✅ 實際售出數量"] > 0]
                            for raw_o in orders:
                                if raw_o['訂單編號'] == o['訂單編號']:
                                    raw_o.update({"購買明細": final_items, "總金額": new_total, "狀態": "已結案", "客戶簽名": canvas_result.json_data, "結案時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "結案業務": st.session_state.user_name})
                            save_json(DB_FILE, orders); st.rerun()

    with op_tab2:
        now = datetime.now()
        recent_orders = [o for o in orders if o["狀態"] == "已結案" and o.get("結案時間") and (now - datetime.strptime(o["結案時間"], "%Y-%m-%d %H:%M:%S")) <= timedelta(hours=1)]
        if not recent_orders: st.info("目前沒有1小時內結案的訂單。")
        else:
            for o in recent_orders:
                with st.expander(f"✅ 單號：{o['訂單編號']} (結案時間: {o.get('結案時間')})", expanded=False):
                    if st.button("⏪ 發現錯誤，撤回重簽", type="primary", key=f"op_revert_{o['訂單編號']}"):
                        for raw_o in orders:
                            if raw_o['訂單編號'] == o['訂單編號']: raw_o.update({"狀態": "待出貨", "客戶簽名": "", "結案時間": "", "結案業務": ""})
                        save_json(DB_FILE, orders); st.rerun()

# 畫面 老闆後台 (Admin)
elif st.session_state.role == "admin":
    st.title("📦 B2B 批發查價台 - 老闆中控台")
    t_settings, t_review, t_orders, t_users = st.tabs(["⚙️ 參數與快速授權", "📋 商品審核台", "🛎️ 訂單全紀錄", "👥 帳號與業績管理"])
    
    def save_df_settings(edited_df):
        changed = False
        for _, row in edited_df.iterrows():
            name = row["品名款式"]
            new_val = {"status": row["狀態"], "b2c_status": row.get("B2C狀態", "❌ 隱藏"), "allowed_clients": str(row["👁️ 指定帳號"]).strip(), "fixed_price": int(row["💰 手動批發價"])}
            if prod_settings.get(name) != new_val: prod_settings[name] = new_val; changed = True
        if changed: save_json(SETTINGS_FILE, prod_settings); st.rerun()

    with t_settings:
        st.info(f"**系統黃金牌價：** {current_gold} 元/錢 | **預設利潤：** {current_margin}%")
        if st.button("⚙️ 點此修改全域參數 (需密碼確認)", type="primary"): edit_global_params_dialog()
        st.divider()
        restricted_clients = {k: v for k, v in users_db.items() if v.get("is_restricted", False) and v.get("role")=="client"}
        col_a, col_b = st.columns(2)
        with col_a: target_products = st.multiselect("📦 1. 選擇商品：", df_clean["品名款式"].tolist())
        with col_b: target_clients = st.multiselect("👤 2. 開放給哪些『限制客』：", [f"{k} ({v['name']})" for k, v in restricted_clients.items()])
        if st.button("✨ 套用專屬權限", type="primary"):
            client_str = ",".join([c.split(" (")[0] for c in target_clients])
            for p in target_products:
                if p not in prod_settings: prod_settings[p] = {"status": "🆕 未上架", "b2c_status": "❌ 隱藏", "allowed_clients": "", "fixed_price": 0}
                prod_settings[p]["allowed_clients"] = client_str
            save_json(SETTINGS_FILE, prod_settings); st.rerun()

    with t_review:
        with st.expander("🔍 搜尋與篩選", expanded=False):
            search_kw_admin = st.text_input("🔑 關鍵字：", key="admin_search", on_change=reset_admin_page)
            if not df_clean.empty:
                w_min_a, w_max_a = float(df_clean["黃金重量(錢)"].min()), float(df_clean["黃金重量(錢)"].max())
                if w_min_a == w_max_a: w_max_a += 0.01 
                weight_range_admin = st.slider("⚖️ 重量區間", w_min_a, w_max_a, (w_min_a, w_max_a), step=0.01, key="admin_weight", on_change=reset_admin_page)
            else: weight_range_admin = (0.0, 10.0)
                
        df_filtered = df_clean[(df_clean["黃金重量(錢)"] >= weight_range_admin[0]) & (df_clean["黃金重量(錢)"] <= weight_range_admin[1])].copy()
        if search_kw_admin: df_filtered = df_filtered[df_filtered["品名款式"].str.contains(search_kw_admin, na=False, case=False) | df_filtered["商品專屬編號"].str.contains(search_kw_admin, na=False, case=False)]

        status_filter = st.selectbox("切換商品視角", ["全部顯示", "🆕 未上架 (待審核區)", "✅ 已上架", "🗑️ 隱藏"], on_change=reset_admin_page)
        if status_filter != "全部顯示": df_filtered = df_filtered[df_filtered["狀態"] == status_filter.split(" ")[0]] 

        df_display = df_filtered[["狀態", "B2C狀態", "💰 手動批發價", "👁️ 指定帳號", "產品照片", "商品專屬編號", "品名款式", "網頁可用庫存", "💡今日動態成本", "🔥廠商批發價", "💰實賺金額(歷史比)", "📈實賺毛利率(%)"]].copy()
            
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if len(df_display) > 0 and st.button(f"🚀 將下方 {len(df_display)} 件設為『B2B ✅ 已上架』", type="primary", use_container_width=True):
                for name in df_display["品名款式"]:
                    if name not in prod_settings: prod_settings[name] = {"status": "✅ 已上架", "b2c_status": "❌ 隱藏", "allowed_clients": "", "fixed_price": 0}
                    else: prod_settings[name]["status"] = "✅ 已上架"
                save_json(SETTINGS_FILE, prod_settings); st.rerun()
        with col_b2:
            if len(df_display) > 0 and st.button(f"🌐 將下方 {len(df_display)} 件設為『B2C ✅ 顯示』", type="primary", use_container_width=True):
                for name in df_display["品名款式"]:
                    if name not in prod_settings: prod_settings[name] = {"status": "🆕 未上架", "b2c_status": "✅ 顯示", "allowed_clients": "", "fixed_price": 0}
                    else: prod_settings[name]["b2c_status"] = "✅ 顯示"
                save_json(SETTINGS_FILE, prod_settings); st.rerun()
            
        total_items_admin = len(df_display)
        total_pages_admin = max(1, int(np.ceil(total_items_admin / ITEMS_PER_PAGE)))
        if st.session_state.admin_page > total_pages_admin: st.session_state.admin_page = 1
        
        col_a_prev, col_a_info, col_a_next = st.columns([1, 2, 1])
        with col_a_prev:
            if st.button("⬅️ 上一頁", key="a_prev_top", disabled=st.session_state.admin_page <= 1, use_container_width=True): st.session_state.admin_page -= 1; st.rerun()
        with col_a_info: st.markdown(f"<div style='text-align: center; padding-top: 5px;'><b>第 {st.session_state.admin_page} / {total_pages_admin} 頁</b> (共 {total_items_admin} 件)</div>", unsafe_allow_html=True)
        with col_a_next:
            if st.button("下一頁 ➡️", key="a_next_top", disabled=st.session_state.admin_page >= total_pages_admin, use_container_width=True): st.session_state.admin_page += 1; st.rerun()

        start_idx_admin = (st.session_state.admin_page - 1) * ITEMS_PER_PAGE
        admin_page_df = df_display.iloc[start_idx_admin : start_idx_admin + ITEMS_PER_PAGE]
            
        edited_df = st.data_editor(
            admin_page_df, use_container_width=True, hide_index=True, height=600, disabled=["產品照片", "商品專屬編號"],
            column_config={
                "狀態": st.column_config.SelectboxColumn("B2B 批發狀態", options=["✅ 已上架", "🆕 未上架", "🗑️ 隱藏"]), 
                "B2C狀態": st.column_config.SelectboxColumn("🌐 B2C 狀態", options=["✅ 顯示", "❌ 隱藏"]), 
                "💰 手動批發價": st.column_config.NumberColumn("💰 你的定價 (0=跑公式)", min_value=0, step=10), 
                "🔥廠商批發價": st.column_config.NumberColumn("🔥廠商批發價", format="$%d"),
                "產品照片": st.column_config.ImageColumn("產品照片")
            }
        )
        save_df_settings(edited_df)

    with t_orders:
        status_tab = st.radio("篩選狀態", ["待派單 (等候老闆核發)", "待檢貨 (檢貨中)", "待出貨 (業務點交中)", "已結案 (完成)"], horizontal=True)
        for o in [o for o in orders if o["狀態"] == status_tab.split(" ")[0]]:
            with st.expander(f"[{o['狀態']}] {o['客戶名稱']} - 單號:{o['訂單編號']}"):
                st.table(pd.DataFrame(o["購買明細"]))
                if o["狀態"] == "待派單":
                    picker_users = {k: v for k, v in users_db.items() if v["role"] == "picker"}
                    col_assign, col_del = st.columns([3, 1])
                    with col_assign:
                        selected_picker = st.selectbox("指派檢貨員", list(picker_users.keys()), format_func=lambda x: f"{x} ({picker_users[x]['name']})", key=f"sel_{o['訂單編號']}") if picker_users else None
                        if selected_picker and st.button("🚀 確認核發", key=f"btn_{o['訂單編號']}", type="primary"):
                            for raw_o in orders:
                                if raw_o['訂單編號'] == o['訂單編號']: raw_o.update({'狀態': '待檢貨', '負責檢貨員': selected_picker})
                            save_json(DB_FILE, orders); st.rerun()
                    with col_del:
                        if st.button("🗑️ 刪除訂單", key=f"del_{o['訂單編號']}", use_container_width=True): delete_order_dialog(o['訂單編號'])
                elif o["狀態"] == "已結案":
                    col_info, col_revert, col_del = st.columns([2, 1, 1])
                    with col_revert:
                        if st.button("🚨 強制退回業務端", key=f"rev_{o['訂單編號']}", use_container_width=True):
                            for raw_o in orders:
                                if raw_o['訂單編號'] == o['訂單編號']: raw_o.update({"狀態": "待出貨", "客戶簽名": "", "結案時間": "", "結案業務": ""})
                            save_json(DB_FILE, orders); st.rerun()
                    with col_del:
                        if st.button("🗑️ 刪除訂單", key=f"del_{o['訂單編號']}", use_container_width=True): delete_order_dialog(o['訂單編號'])
                else:
                    if st.button("🗑️ 刪除訂單", key=f"del_{o['訂單編號']}"): delete_order_dialog(o['訂單編號'])

    with t_users:
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            if st.button("🔑 修改帳號密碼", use_container_width=True): password_modal()
        with col_btn2:
            if st.button("🎯 設定專屬利潤", use_container_width=True): custom_margin_dialog()
        with col_btn3:
            if st.button("🗑️ 刪除無用帳號", use_container_width=True): delete_account_dialog()
                
        client_spend = {o["客戶名稱"]: sum(x["總金額"] for x in orders if x["狀態"] == "已結案" and x["客戶名稱"] == o["客戶名稱"]) for o in orders if o["狀態"] == "已結案"}
        user_data = [{"登入帳號": k, "密碼": v["password"], "名稱": v["name"], "權限": v["role"], "業績": client_spend.get(v["name"], 0)} for k, v in users_db.items()]
        st.dataframe(pd.DataFrame(user_data).sort_values(by="業績", ascending=False), hide_index=True, use_container_width=True)
        st.divider()
        with st.form("add_user_form"):
            new_u = st.text_input("帳號")
            new_p = st.text_input("密碼")
            new_n = st.text_input("名稱")
            u_role = st.selectbox("身分", ["🟢 一般客", "🔴 限制客", "💼 現場業務", "📦 內部檢貨員"])
            if st.form_submit_button("建立帳號") and new_u and new_p and new_n:
                role_map = {"🟢 一般客": ("client", False), "🔴 限制客": ("client", True), "💼 現場業務": ("operator", False), "📦 內部檢貨員": ("picker", False)}
                users_db[new_u] = {"password": new_p, "role": role_map[u_role][0], "name": new_n, "is_restricted": role_map[u_role][1]}
                save_json(USERS_DB_FILE, users_db); st.rerun()
