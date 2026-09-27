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
# 🌟 迷你資料庫：訂單管理 & 帳號管理
# ==========================================
DB_FILE = "orders_db.json"
USERS_DB_FILE = "users_db.json"

# 預設的老闆超級帳號 (防止你把自己刪掉進不去系統)
DEFAULT_USERS = {
    "boss": {"password": "123", "role": "admin", "name": "老闆"}
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
    # 如果檔案不存在，就建立並寫入預設老闆帳號
    save_users(DEFAULT_USERS)
    return DEFAULT_USERS

def save_users(users):
    with open(USERS_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

# 讀取最新帳號資料庫
users_db = load_users()

# ==========================================
# 🌟 登入狀態與記憶區
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.user_name = None

if "saved_gold" not in st.session_state:
    st.session_state.saved_gold = 10000
if "saved_margin" not in st.session_state:
    st.session_state.saved_margin = 35.0
if "listing_status" not in st.session_state:
    st.session_state.listing_status = {} 


# ==========================================
# 🛑 登入大門
# ==========================================
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>🔐 B2B 批發查價系統</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>請輸入您的專屬帳號密碼以查看最新報價</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            input_user = st.text_input("👤 帳號 (Username)")
            input_pwd = st.text_input("🔑 密碼 (Password)", type="password")
            
            if st.button("🚀 登入系統", use_container_width=True):
                # 改從資料庫檢查帳號密碼
                if input_user in users_db and users_db[input_user]["password"] == input_pwd:
                    st.session_state.logged_in = True
                    st.session_state.role = users_db[input_user]["role"]
                    st.session_state.user_name = users_db[input_user]["name"]
                    st.rerun() 
                else:
                    st.error("❌ 帳號或密碼錯誤，請重新輸入。")
    st.stop()


# ==========================================
# 🟢 成功登入後的側邊欄
# ==========================================
with st.sidebar:
    st.success(f"歡迎回來！\n👤 **{st.session_state.user_name}**")
    if st.button("🚪 登出系統", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()
    st.divider()


# ==========================================
# 🌟 連線 Ragic 與準備資料 (共通)
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

if data and isinstance(data, dict) and data.get("0") != "ERROR":
    
    records = list(data.values())
    df = pd.DataFrame(records)
    
    needed_columns = ["產品照片", "品名款式", "黃金重量(錢)", "盤商收取工資", "定價毛利等級", "手動設定售價(固定商品用)", "目前庫存量", "本件真實總成本"]
    existing_columns = [col for col in needed_columns if col in df.columns]
    df_clean = df[existing_columns].copy()
    df_clean = df_clean.fillna(0)
    
    for col in ["黃金重量(錢)", "盤商收取工資", "目前庫存量", "手動設定售價(固定商品用)", "本件真實總成本"]:
        if col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0)
            
    def get_image_url(file_name):
        if not file_name or str(file_name) == "0": return ""
        encoded = urllib.parse.quote(str(file_name))
        return f"https://ap15.ragic.com/sims/file.jsp?a=goldselling&f={encoded}"
    
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
    df_clean["🔥B2B批發價"] = np.round(df_clean["💡今日動態成本"] + (df_clean["原本預期利潤"] * (current_margin / 100)))
    df_clean["💰實賺金額(歷史比)"] = df_clean["🔥B2B批發價"] - df_clean["本件真實總成本"]
    df_clean["📈實賺毛利率(%)"] = np.where(df_clean["🔥B2B批發價"] > 0, (df_clean["💰實賺金額(歷史比)"] / df_clean["🔥B2B批發價"]) * 100, 0)
    df_clean["✅ 上架放行"] = df_clean["品名款式"].apply(lambda x: st.session_state.listing_status.get(x, True))

    orders = load_orders()
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

            p_min, p_max = float(df_clean["🔥B2B批發價"].min()), float(df_clean["🔥B2B批發價"].max())
            if p_min == p_max: p_max += 100.0
            price_range = st.slider("💰 批發價區間 (元)", int(p_min), int(p_max), (int(p_min), int(p_max)), step=100)
        else:
            weight_range, price_range = (0.0, 10.0), (0, 10000)

    df_filtered = df_clean[
        (df_clean["黃金重量(錢)"] >= weight_range[0]) & (df_clean["黃金重量(錢)"] <= weight_range[1]) &
        (df_clean["🔥B2B批發價"] >= price_range[0]) & (df_clean["🔥B2B批發價"] <= price_range[1])
    ]
    if search_kw:
        df_filtered = df_filtered[df_filtered["品名款式"].str.contains(search_kw, na=False, case=False)]


    # ==========================================
    # 畫面 A：💎 B2B 客戶前台
    # ==========================================
    if st.session_state.role == "client":
        st.title("💎 批發商品線上型錄")
        st.info(f"📈 今日系統黃金牌價： **{current_gold}** 元/錢")
        
        df_client = df_filtered[df_filtered["✅ 上架放行"] == True].copy()
        
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
                    "黃金重量(錢)": st.column_config.NumberColumn("重量(錢)", format="%.2f"),
                    "🔥B2B批發價": st.column_config.NumberColumn("🔥今日批發價", format="$%d")
                }
            )
            
            st.divider()
            
            st.markdown("### 📝 確認預約單")
            st.success(f"👤 訂購客戶： **{st.session_state.user_name}**")
            
            if st.button("🚀 送出預約單", type="primary"):
                cart_items = edited_client[edited_client["🛒 購買數量"] > 0]
                
                if cart_items.empty:
                    st.warning("⚠️ 購物車是空的，請先填寫購買數量！")
                else:
                    order_items = []
                    total_amount = 0
                    for _, row in cart_items.iterrows():
                        qty = int(row["🛒 購買數量"])
                        if qty > row["網頁可用庫存"]:
                            qty = int(row["網頁可用庫存"])
                            
                        subtotal = qty * row["🔥B2B批發價"]
                        total_amount += subtotal
                        order_items.append({
                            "品名款式": row["品名款式"],
                            "重量": row["黃金重量(錢)"],
                            "數量": qty,
                            "單價": row["🔥B2B批發價"],
                            "小計": subtotal
                        })
                    
                    new_order = {
                        "訂單編號": datetime.now().strftime("%Y%m%d%H%M%S"),
                        "客戶名稱": st.session_state.user_name, 
                        "下單時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "當時金價": current_gold,
                        "總金額": total_amount,
                        "狀態": "待處理",
                        "購買明細": order_items
                    }
                    
                    orders.append(new_order)
                    save_orders(orders)
                    st.balloons()
                    st.success(f"🎉 預約單送出成功！您的訂單編號為：{new_order['訂單編號']}。我們會盡快為您處理。")
                    
        else:
            st.info("目前沒有符合條件的商品。")

    # ==========================================
    # 畫面 B：🧑‍💼 老闆專屬後台
    # ==========================================
    elif st.session_state.role == "admin":
        st.title("📦 B2B 批發查價台 - 老闆中控台")
        
        # 🌟 多加一個「帳號管理」的分頁
        tab1, tab2, tab3 = st.tabs(["🛠️ 商品上架中控台", "📋 客戶預約訂單管理", "👥 客戶帳號管理"])
        
        with tab1:
            st.markdown("### 💰 今日參數設定")
            col1, col2 = st.columns(2)
            with col1:
                new_gold = st.number_input("📈 今日黃金牌價 (元/錢)：", min_value=0, value=st.session_state.saved_gold, step=100)
                if new_gold != st.session_state.saved_gold:
                    st.session_state.saved_gold = new_gold
                    st.rerun() 
            with col2:
                new_margin = st.number_input("🎯 預設 B2B 批發利潤 (%)：", min_value=0.0, value=st.session_state.saved_margin, step=5.0)
                if new_margin != st.session_state.saved_margin:
                    st.session_state.saved_margin = new_margin
                    st.rerun()

            df_display = df_filtered[[
                "✅ 上架放行", "產品照片", "品名款式", "目前庫存量", "網頁可用庫存", "黃金重量(錢)", 
                "本件真實總成本", "💡今日動態成本", "🏪動態零售價", "🔥B2B批發價", 
                "💰實賺金額(歷史比)", "📈實賺毛利率(%)"
            ]].copy()
            
            st.caption("『目前庫存量』為 Ragic 實際庫存，『網頁可用庫存』為扣除未處理訂單後的數量。")
            
            edited_df = st.data_editor(
                df_display,
                use_container_width=True,
                hide_index=True,
                height=600,
                column_config={
                    "✅ 上架放行": st.column_config.CheckboxColumn("上架放行"),
                    "產品照片": st.column_config.ImageColumn("產品照片"),
                    "🔥B2B批發價": st.column_config.NumberColumn("🔥B2B批發價", format="$%d"),
                    "💰實賺金額(歷史比)": st.column_config.NumberColumn("💰實賺金額", format="$%d"),
                    "📈實賺毛利率(%)": st.column_config.NumberColumn("📈實賺毛利(%)", format="%.1f%%")
                }
            )
            
            for index, row in edited_df.iterrows():
                st.session_state.listing_status[row["品名款式"]] = row["✅ 上架放行"]

        with tab2:
            st.markdown("### 🛎️ 待處理預約單")
            pending_orders = [o for o in orders if o["狀態"] == "待處理"]
            
            if not pending_orders:
                st.success("目前沒有待處理的訂單，太棒了！")
            else:
                for idx, o in enumerate(pending_orders):
                    with st.expander(f"📌 [{o['下單時間']}] 客戶：{o['客戶名稱']} - 總額：${o['總金額']}", expanded=True):
                        st.write(f"**訂單編號：** {o['訂單編號']} (當時金價：{o['當時金價']})")
                        st.table(pd.DataFrame(o["購買明細"]))
                        
                        if st.button(f"✅ 標記為『已處理』 (請先至 Ragic 扣除庫存)", key=f"btn_{o['訂單編號']}"):
                            for raw_o in orders:
                                if raw_o['訂單編號'] == o['訂單編號']:
                                    raw_o['狀態'] = "已完成"
                            save_orders(orders)
                            st.rerun()

        # 🌟 新增：帳號管理後台
        with tab3:
            st.markdown("### ➕ 新增客戶帳號")
            with st.form("add_user_form"):
                new_username = st.text_input("帳號 (英文/數字)")
                new_password = st.text_input("密碼")
                new_name = st.text_input("客戶名稱 / 行號 (例如：林先生 / 聚點工作室)")
                submit_btn = st.form_submit_button("建立帳號")
                
                if submit_btn:
                    if not new_username or not new_password or not new_name:
                        st.warning("⚠️ 請填寫完整資訊！")
                    elif new_username in users_db:
                        st.warning("⚠️ 此帳號已存在，請換一個！")
                    else:
                        users_db[new_username] = {"password": new_password, "role": "client", "name": new_name}
                        save_users(users_db)
                        st.success(f"🎉 成功建立客戶：{new_name} 的帳號！")
                        st.rerun()
            
            st.divider()
            st.markdown("### 📋 現有客戶名單")
            # 撈出所有 client 角色
            client_users = {k: v for k, v in users_db.items() if v["role"] == "client"}
            
            if client_users:
                user_df = pd.DataFrame([
                    {"登入帳號": k, "密碼": v["password"], "客戶名稱": v["name"]}
                    for k, v in client_users.items()
                ])
                st.dataframe(user_df, hide_index=True, use_container_width=True)
                
                # 刪除功能
                del_user = st.selectbox("選擇要刪除的帳號", ["(請選擇)"] + list(client_users.keys()))
                if st.button("🗑️ 刪除選取的帳號"):
                    if del_user != "(請選擇)":
                        del users_db[del_user]
                        save_users(users_db)
                        st.success(f"已成功刪除帳號：{del_user}")
                        st.rerun()
            else:
                st.info("目前還沒有建立任何客戶帳號喔！可以在上方立即新增。")

else:
    st.error("讀取資料失敗，請確認 Ragic 金鑰設定。")
