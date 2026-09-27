import streamlit as st
import requests
import pandas as pd
import urllib.parse
import numpy as np
import json
import os
from datetime import datetime

st.set_page_config(page_title="B2B 查價台系統", layout="wide")

# ==========================================
# 🌟 資料庫設定
# ==========================================
DB_FILE = "orders_db.json"
USERS_DB_FILE = "users_db.json"
SETTINGS_FILE = "product_settings.json" 

DEFAULT_USERS = {
    "boss": {"password": "123", "role": "admin", "name": "老闆", "is_restricted": False}
}

def load_orders():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_orders(orders):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=4)

def load_users():
    if os.path.exists(USERS_DB_FILE):
        with open(USERS_DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    save_users(DEFAULT_USERS)
    return DEFAULT_USERS

def save_users(users):
    with open(USERS_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)

users_db = load_users()
prod_settings = load_settings()
orders = load_orders()

# ==========================================
# 🌟 狀態與記憶
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.user_name = None
    st.session_state.account_id = None 

if "saved_gold" not in st.session_state:
    st.session_state.saved_gold = 10000
if "saved_margin" not in st.session_state:
    st.session_state.saved_margin = 35.0

# ==========================================
# 🛑 登入大門
# ==========================================
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>🔐 B2B 批發查價系統</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>請輸入您的專屬帳號密碼以查看最新報價</p>", unsafe_allow_html=True)
    
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
                    st.rerun() 
                else:
                    st.error("❌ 帳號或密碼錯誤，請重新輸入。")
    st.stop()

# ==========================================
# 🟢 側邊欄
# ==========================================
with st.sidebar:
    st.success(f"歡迎回來！\n👤 **{st.session_state.user_name}**")
    if st.button("🚪 登出系統", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()
    st.divider()

# ==========================================
# 🌟 資料處理與計算 
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
    st.error("讀取資料失敗，請確認 Ragic 金鑰設定。")
    st.stop()

records = list(data.values())
df = pd.DataFrame(records)
needed_columns = ["產品照片", "品名款式", "黃金重量(錢)", "盤商收取工資", "定價毛利等級", "手動設定售價(固定商品用)", "目前庫存量", "本件真實總成本"]
df_clean = df[[col for col in needed_columns if col in df.columns]].copy().fillna(0)

for col in ["黃金重量(錢)", "盤商收取工資", "目前庫存量", "手動設定售價(固定商品用)", "本件真實總成本"]:
    if col in df_clean.columns: df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0)
        
def get_image_url(file_name):
    if not file_name or str(file_name) == "0": return ""
    return f"https://ap15.ragic.com/sims/file.jsp?a=goldselling&f={urllib.parse.quote(str(file_name))}"

if "產品照片" in df_clean.columns:
    df_clean["產品照片"] = df_clean["產品照片"].apply(get_image_url)

current_gold = st.session_state.saved_gold
current_margin = st.session_state.saved_margin

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

# 🌟 套用設定：狀態、指定帳號、手動固定價格
df_clean["狀態"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("status", "🆕 未上架"))
df_clean["👁️ 指定帳號"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("allowed_clients", ""))
df_clean["💰 手動批發價"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("fixed_price", 0))

# 🌟 價格計算：如果老闆有填「手動批發價」，就強制蓋掉公式
df_clean["🔥B2B批發價"] = np.where(
    df_clean["💰 手動批發價"] > 0,
    df_clean["💰 手動批發價"],
    np.round(df_clean["💡今日動態成本"] + (df_clean["原本預期利潤"] * (current_margin / 100)))
)

df_clean["💰實賺金額(歷史比)"] = df_clean["🔥B2B批發價"] - df_clean["本件真實總成本"]
df_clean["📈實賺毛利率(%)"] = np.where(df_clean["🔥B2B批發價"] > 0, (df_clean["💰實賺金額(歷史比)"] / df_clean["🔥B2B批發價"]) * 100, 0)

# 扣除網頁預留庫存
reserved_stock = {}
for o in orders:
    if o["狀態"] == "待處理":
        for item in o["購買明細"]:
            name = item["品名款式"]
            reserved_stock[name] = reserved_stock.get(name, 0) + item["數量"]
            
df_clean["網頁可用庫存"] = df_clean["目前庫存量"] - df_clean["品名款式"].map(reserved_stock).fillna(0)
df_clean = df_clean[df_clean["網頁可用庫存"] > 0].reset_index(drop=True)

with st.sidebar:
    st.markdown("### 🔍 智慧商品篩選")
    search_kw = st.text_input("🔑 關鍵字搜尋 (品名/款式)：", placeholder="例如：手繩, 蝴蝶結...")
    
    if not df_clean.empty:
        w_min, w_max = float(df_clean["黃金重量(錢)"].min()), float(df_clean["黃金重量(錢)"].max())
        if w_min == w_max: w_max += 0.01 
        weight_range = st.slider("⚖️ 重量區間 (錢)", w_min, w_max, (w_min, w_max), step=0.01)
    else:
        weight_range = (0.0, 10.0)

df_filtered = df_clean[
    (df_clean["黃金重量(錢)"] >= weight_range[0]) & (df_clean["黃金重量(錢)"] <= weight_range[1])
]
if search_kw:
    df_filtered = df_filtered[df_filtered["品名款式"].str.contains(search_kw, na=False, case=False)]


# ==========================================
# 畫面 A：💎 B2B 客戶前台 (新增歷史明細)
# ==========================================
if st.session_state.role == "client":
    tab1, tab2 = st.tabs(["🛍️ 線上批發型錄", "📜 我的訂單與累積消費"])
    
    with tab1:
        st.info(f"📈 今日系統黃金牌價： **{current_gold}** 元/錢")
        
        # 🌟 邏輯：一般客看已上架。限制客看指定（就算未上架也能看）。兩者都不能看隱藏。
        def can_see(row):
            user = st.session_state.account_id
            is_restricted = users_db.get(user, {}).get("is_restricted", False)
            status = row["狀態"]
            allowed_str = str(row["👁️ 指定帳號"]).strip()
            
            if status == "🗑️ 隱藏": return False
            
            if not is_restricted:
                return status == "✅ 已上架"
            else:
                allowed_list = [acc.strip() for acc in allowed_str.split(",")] if allowed_str else []
                return user in allowed_list

        df_client = df_filtered[df_filtered.apply(can_see, axis=1)].copy()
        
        if not df_client.empty:
            df_client.insert(0, "🛒 購買數量", 0)
            client_display = df_client[["🛒 購買數量", "產品照片", "品名款式", "網頁可用庫存", "黃金重量(錢)", "🔥B2B批發價"]]
            
            st.markdown("### 🛍️ 選擇商品與數量")
            edited_client = st.data_editor(
                client_display,
                use_container_width=True,
                hide_index=True,
                height=500,
                disabled=["產品照片", "品名款式", "網頁可用庫存", "黃金重量(錢)", "🔥B2B批發價"],
                column_config={
                    "🛒 購買數量": st.column_config.NumberColumn("🛒 購買數量", min_value=0, step=1),
                    "產品照片": st.column_config.ImageColumn("產品照片"),
                    "網頁可用庫存": st.column_config.NumberColumn("目前庫存", format="%d 件"),
                    "🔥B2B批發價": st.column_config.NumberColumn("🔥今日批發價", format="$%d")
                }
            )
            
            st.divider()
            if st.button("🚀 送出預約單", type="primary"):
                cart_items = edited_client[edited_client["🛒 購買數量"] > 0]
                if cart_items.empty:
                    st.warning("⚠️ 購物車是空的！")
                else:
                    total_amount = sum(row["🛒 購買數量"] * row["🔥B2B批發價"] for _, row in cart_items.iterrows())
                    order_items = [{"品名款式": r["品名款式"], "數量": r["🛒 購買數量"], "單價": r["🔥B2B批發價"], "小計": r["🛒 購買數量"]*r["🔥B2B批發價"]} for _, r in cart_items.iterrows()]
                    
                    new_order = {
                        "訂單編號": datetime.now().strftime("%Y%m%d%H%M%S"),
                        "客戶名稱": st.session_state.user_name, 
                        "下單時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "當時金價": current_gold, "總金額": total_amount, "狀態": "待處理", "購買明細": order_items
                    }
                    orders.append(new_order)
                    save_orders(orders)
                    st.success(f"🎉 成功送出！訂單編號：{new_order['訂單編號']}")
        else:
            st.info("目前沒有符合條件的商品。")
            
    with tab2:
        st.markdown("### 💰 我的消費紀錄")
        my_orders = [o for o in orders if o["客戶名稱"] == st.session_state.user_name]
        
        if my_orders:
            # 計算該客戶所有訂單總和
            total_spent = sum(o["總金額"] for o in my_orders)
            st.metric(label="🌟 您在我們這裡累積配合的總金額", value=f"NT$ {total_spent:,}")
            st.divider()
            
            for o in reversed(my_orders):
                with st.expander(f"📦 {o['下單時間']} | 訂單編號: {o['訂單編號']} | 總額: ${o['總金額']:,} ({o['狀態']})"):
                    st.table(pd.DataFrame(o["購買明細"]))
        else:
            st.info("您目前還沒有下過訂單喔！")


# ==========================================
# 畫面 B：🧑‍💼 老闆專屬後台
# ==========================================
elif st.session_state.role == "admin":
    st.title("📦 B2B 批發查價台 - 老闆中控台")
    
    # 🌟 後台分頁重組
    t_settings, t_review, t_orders, t_users = st.tabs(["⚙️ 參數與快速授權", "📋 商品上架審核台", "🛎️ 訂單管理", "👥 帳號與業績管理"])
    
    def save_df_settings(edited_df):
        changed = False
        for _, row in edited_df.iterrows():
            name = row["品名款式"]
            new_val = {
                "status": row["狀態"],
                "allowed_clients": str(row["👁️ 指定帳號"]).strip(),
                "fixed_price": int(row["💰 手動批發價"])
            }
            if prod_settings.get(name) != new_val:
                prod_settings[name] = new_val
                changed = True
        if changed:
            save_settings(prod_settings)
            st.rerun()

    with t_settings:
        st.markdown("### 💰 參數設定")
        col1, col2 = st.columns(2)
        with col1:
            new_gold = st.number_input("📈 今日黃金牌價：", min_value=0, value=st.session_state.saved_gold, step=100)
            if new_gold != st.session_state.saved_gold: st.session_state.saved_gold = new_gold; st.rerun() 
        with col2:
            new_margin = st.number_input("🎯 B2B 利潤 (%)：", min_value=0.0, value=st.session_state.saved_margin, step=5.0)
            if new_margin != st.session_state.saved_margin: st.session_state.saved_margin = new_margin; st.rerun()
            
        st.divider()
        st.markdown("### 👑 限制客專屬：批次授權小工具")
        restricted_clients = {k: v for k, v in users_db.items() if v.get("is_restricted", False)}
        col_a, col_b = st.columns(2)
        with col_a:
            target_products = st.multiselect("📦 1. 選擇商品：", df_filtered["品名款式"].tolist())
        with col_b:
            client_options = [f"{k} ({v['name']})" for k, v in restricted_clients.items()]
            target_clients = st.multiselect("👤 2. 開放給哪些『限制客』：", client_options)
            
        if st.button("✨ 套用專屬權限", type="primary"):
            if target_products:
                client_str = ",".join([c.split(" (")[0] for c in target_clients])
                for p in target_products:
                    if p not in prod_settings: prod_settings[p] = {"status": "🆕 未上架", "allowed_clients": "", "fixed_price": 0}
                    prod_settings[p]["allowed_clients"] = client_str
                save_settings(prod_settings)
                st.success("🎉 權限套用成功！")
                st.rerun()

    with t_review:
        st.markdown("### 📋 商品上架與定價審核台")
        st.caption("你可以在這裡切換狀態、設定『手動批發價(填 0 即套用公式)』，以及指定客戶帳號。")
        
        status_filter = st.selectbox("切換商品視角", ["全部顯示", "🆕 未上架 (待審核區)", "✅ 已上架", "🗑️ 隱藏"])
        
        df_display = df_filtered[[
            "狀態", "💰 手動批發價", "👁️ 指定帳號", "品名款式", "產品照片", "網頁可用庫存", 
            "💡今日動態成本", "🔥B2B批發價", "💰實賺金額(歷史比)"
        ]].copy()
        
        if status_filter != "全部顯示":
            df_display = df_display[df_display["狀態"] == status_filter.split(" ")[0]] # 擷取 icon+文字
            
        edited_df = st.data_editor(
            df_display,
            use_container_width=True,
            hide_index=True,
            height=600,
            column_config={
                "狀態": st.column_config.SelectboxColumn("狀態", options=["✅ 已上架", "🆕 未上架", "🗑️ 隱藏"], required=True),
                "💰 手動批發價": st.column_config.NumberColumn("💰 你的定價", min_value=0, step=10, help="填 0 會跑公式，填數字就是一口價！"),
                "👁️ 指定帳號": st.column_config.TextColumn("👁️ 限客名單"),
                "產品照片": st.column_config.ImageColumn("產品照片"),
                "🔥B2B批發價": st.column_config.NumberColumn("🔥 最終給客人的價錢", format="$%d")
            }
        )
        save_df_settings(edited_df)

    with t_orders:
        st.markdown("### 🛎️ 待處理預約單")
        pending_orders = [o for o in orders if o["狀態"] == "待處理"]
        if not pending_orders: st.success("沒有待處理的訂單！")
        else:
            for o in pending_orders:
                with st.expander(f"📌 {o['客戶名稱']} - 總額：${o['總金額']:,}", expanded=True):
                    st.table(pd.DataFrame(o["購買明細"]))
                    if st.button(f"✅ 標記『已完成』 (請先扣 Ragic)", key=f"btn_{o['訂單編號']}"):
                        for raw_o in orders:
                            if raw_o['訂單編號'] == o['訂單編號']: raw_o['狀態'] = "已完成"
                        save_orders(orders)
                        st.rerun()

    with t_users:
        st.markdown("### 🏆 客戶業績排行榜與帳號管理")
        
        # 🌟 老闆福利：自動結算所有客戶業績總額！
        client_spend = {}
        for o in orders:
            client_spend[o["客戶名稱"]] = client_spend.get(o["客戶名稱"], 0) + o["總金額"]
            
        client_users = {k: v for k, v in users_db.items() if v["role"] == "client"}
        
        if client_users:
            user_df = pd.DataFrame([
                {
                    "登入帳號": k, 
                    "密碼": v["password"], 
                    "客戶名稱": v["name"],
                    "權限層級": "🔴 限制客" if v.get("is_restricted") else "🟢 一般客",
                    "累積貢獻總額": client_spend.get(v["name"], 0) # 帶入業績
                } for k, v in client_users.items()
            ])
            # 按業績排序
            user_df = user_df.sort_values(by="累積貢獻總額", ascending=False)
            
            st.dataframe(user_df, hide_index=True, use_container_width=True, column_config={
                "累積貢獻總額": st.column_config.NumberColumn("💰 累積貢獻總額", format="$%d")
            })
            
            del_user = st.selectbox("刪除帳號", ["(請選擇)"] + list(client_users.keys()))
            if st.button("🗑️ 刪除選取帳號") and del_user != "(請選擇)":
                del users_db[del_user]
                save_users(users_db)
                st.rerun()
