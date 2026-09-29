import streamlit as st
import requests
import pandas as pd
import urllib.parse
import numpy as np
import json
import os
from datetime import datetime, timedelta, date
from streamlit_drawable_canvas import st_canvas

st.set_page_config(page_title="B2B 查價台系統", layout="wide")

# ==========================================
# 🌟 資料庫設定
# ==========================================
DB_FILE = "orders_db.json"
USERS_DB_FILE = "users_db.json"
SETTINGS_FILE = "product_settings.json" 
CARTS_FILE = "carts_db.json" 

DEFAULT_USERS = {
    "boss": {"password": "123", "role": "admin", "name": "老闆", "is_restricted": False},
    "op1": {"password": "123", "role": "operator", "name": "現場作業員A"} 
}

def load_json(file_path, default_data):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default_data

def save_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

orders = load_json(DB_FILE, [])
users_db = load_json(USERS_DB_FILE, DEFAULT_USERS)
if "op1" not in users_db: 
    users_db["op1"] = {"password": "123", "role": "operator", "name": "現場作業員A"}
    save_json(USERS_DB_FILE, users_db)
    
prod_settings = load_json(SETTINGS_FILE, {})
all_carts = load_json(CARTS_FILE, {})

# ==========================================
# 🌟 狀態與記憶
# ==========================================
if "logged_in" not in st.session_state:
    saved_user = st.query_params.get("user")
    if saved_user and saved_user in users_db:
        st.session_state.logged_in = True
        st.session_state.role = users_db[saved_user]["role"]
        st.session_state.user_name = users_db[saved_user]["name"]
        st.session_state.account_id = saved_user
    else:
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

# ==========================================
# 🟢 側邊欄
# ==========================================
with st.sidebar:
    st.success(f"歡迎回來！\n👤 **{st.session_state.user_name}**")
    if st.button("🚪 登出系統", use_container_width=True):
        st.session_state.logged_in = False
        st.query_params.clear() 
        st.rerun()
    st.divider()

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

df_clean["狀態"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("status", "🆕 未上架"))
df_clean["👁️ 指定帳號"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("allowed_clients", ""))
df_clean["💰 手動批發價"] = df_clean["品名款式"].apply(lambda x: prod_settings.get(x, {}).get("fixed_price", 0))

df_clean["🔥B2B批發價"] = np.where(
    df_clean["💰 手動批發價"] > 0,
    df_clean["💰 手動批發價"],
    np.round(df_clean["💡今日動態成本"] + (df_clean["原本預期利潤"] * (current_margin / 100)))
)
df_clean["💰實賺金額(歷史比)"] = df_clean["🔥B2B批發價"] - df_clean["本件真實總成本"]
df_clean["📈實賺毛利率(%)"] = np.where(df_clean["🔥B2B批發價"] > 0, (df_clean["💰實賺金額(歷史比)"] / df_clean["🔥B2B批發價"]) * 100, 0)

# ==========================================
# 🌟 全域庫存計算
# ==========================================
my_acc = st.session_state.account_id
reserved_stock = {}
for o in orders:
    if o["狀態"] == "待出貨":
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


# ==========================================
# 畫面 A：💎 B2B 客戶前台
# ==========================================
if st.session_state.role == "client":
    tab1, tab2, tab3 = st.tabs(["🛍️ 線上批發型錄", "🛒 我的購物車與結帳", "📜 歷史結案明細"])
    
    with tab1:
        col_info, col_btn = st.columns([4, 1])
        with col_info:
            st.info(f"📈 今日系統黃金牌價： **{current_gold}** 元/錢")
        with col_btn:
            if st.button("🔄 抓取最新庫存", use_container_width=True, type="primary"): st.rerun()
                
        df_client_view = df_clean[df_clean["網頁可用庫存"] > 0].copy()
        
        with st.expander("🔍 搜尋與篩選", expanded=False):
            search_kw = st.text_input("🔑 關鍵字搜尋：")
            if not df_client_view.empty:
                w_min, w_max = float(df_client_view["黃金重量(錢)"].min()), float(df_client_view["黃金重量(錢)"].max())
                if w_min == w_max: w_max += 0.01 
                weight_range = st.slider("⚖️ 重量區間 (錢)", w_min, w_max, (w_min, w_max), step=0.01)
            else:
                weight_range = (0.0, 10.0)

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
            if search_kw: df_client_view = df_client_view[df_client_view["品名款式"].str.contains(search_kw, na=False, case=False)]
        
        if not df_client_view.empty:
            client_display = df_client_view[["🛒 我的購物車", "產品照片", "品名款式", "網頁可用庫存", "黃金重量(錢)", "🔥B2B批發價"]]
            
            st.markdown("### 🛍️ 挑選商品 (即時鎖庫存)")
            st.caption("修改數量後，商品將暫時保留在購物車內。若想看最新庫存，請點擊上方『🔄 抓取最新庫存』。")
            
            edited_client = st.data_editor(
                client_display, use_container_width=True, hide_index=True, height=500,
                disabled=["產品照片", "品名款式", "網頁可用庫存", "黃金重量(錢)", "🔥B2B批發價"],
                column_config={
                    "🛒 我的購物車": st.column_config.NumberColumn("🛒 加入車內", min_value=0, step=1),
                    "產品照片": st.column_config.ImageColumn("產品照片"),
                    "網頁可用庫存": st.column_config.NumberColumn("目前庫存", format="%d 件"),
                    "🔥B2B批發價": st.column_config.NumberColumn("🔥今日批發價", format="$%d")
                }
            )
            
            new_cart = {}
            for _, row in edited_client.iterrows():
                qty = int(row["🛒 我的購物車"])
                if qty > 0:
                    new_cart[row["品名款式"]] = min(qty, int(row["網頁可用庫存"]))
            
            if new_cart != my_cart:
                all_carts[my_acc] = new_cart
                save_json(CARTS_FILE, all_carts)
                st.rerun()
        else:
            st.info("目前沒有符合條件的商品。")
            
    with tab2:
        col_title, col_btn = st.columns([4, 1])
        with col_title: st.markdown("### 🛒 結帳與預約出貨")
        with col_btn:
            if st.button("🔄 重整購物車", use_container_width=True): st.rerun()
            
        if not my_cart:
            st.warning("您的購物車是空的，快去型錄挑選吧！")
        else:
            cart_data = []
            total_amount = 0
            for name, qty in my_cart.items():
                row = df_clean[df_clean["品名款式"] == name]
                if not row.empty:
                    price = int(row.iloc[0]["🔥B2B批發價"])
                    subtotal = price * qty
                    total_amount += subtotal
                    cart_data.append({"品名款式": name, "數量": qty, "單價": price, "小計": subtotal, "重量(錢)": row.iloc[0]["黃金重量(錢)"]})
            
            st.table(pd.DataFrame(cart_data))
            st.markdown(f"#### 💰 預計總金額： NT$ {total_amount:,}")
            
            st.divider()
            st.markdown("### 📅 直播預約資訊 (重要！)")
            
            col_d, col_t = st.columns(2)
            with col_d: live_date = st.date_input("🗓️ 預計直播日期", value=date.today() + timedelta(days=5))
            with col_t: meet_time = st.text_input("⏰ 當天見面與點交時間", placeholder="下午2:00")
            
            if (live_date - date.today()).days < 5:
                st.error("🚨 【急件注意】距離直播日期不足 5 天！為確保作業流程，急件請直接聯絡您的專屬業務，無法透過系統自助下單。")
            else:
                if st.button("🚀 確認無誤，送出預約單", type="primary"):
                    if not meet_time: st.warning("⚠️ 請填寫見面時間！")
                    else:
                        new_order = {
                            "訂單編號": datetime.now().strftime("%Y%m%d%H%M%S"),
                            "客戶名稱": st.session_state.user_name, "帳號": my_acc,
                            "下單時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "預約直播日": str(live_date), "見面時間": meet_time,
                            "當時金價": current_gold, "總金額": total_amount, 
                            "狀態": "待出貨", "購買明細": cart_data,
                            "客戶簽名": "", "結案時間": ""
                        }
                        orders.append(new_order)
                        save_json(DB_FILE, orders)
                        all_carts[my_acc] = {}
                        save_json(CARTS_FILE, all_carts)
                        st.balloons()
                        st.success(f"🎉 預約成功！單號：{new_order['訂單編號']}")
                        st.rerun()

    with tab3:
        st.markdown('<style>iframe[title="streamlit_drawable_canvas.st_canvas"] {pointer-events: none;}</style>', unsafe_allow_html=True)
        st.markdown("### 💰 累積結案消費紀錄")
        st.caption("此處僅顯示已由現場作業人員點交、簽名並『已結案』的實際交易紀錄。")
        my_closed_orders = [o for o in orders if o.get("帳號") == my_acc and o["狀態"] == "已結案"]
        
        if my_closed_orders:
            total_spent = sum(o["總金額"] for o in my_closed_orders)
            st.metric(label="🌟 您在我們這裡累積配合的總金額 (GMV)", value=f"NT$ {total_spent:,}")
            st.divider()
            for o in reversed(my_closed_orders):
                with st.expander(f"📦 {o['下單時間']} | 單號: {o['訂單編號']} | 實際總額: ${o['總金額']:,} ✅"):
                    st.write(f"**直播日期：** {o.get('預約直播日', '未填寫')}")
                    sig = o.get('客戶簽名', '')
                    if isinstance(sig, dict):
                        st.write("**📝 客戶簽名確認：**")
                        st_canvas(initial_drawing=sig, stroke_width=4, stroke_color="#000000", background_color="#FFFFFF", height=200, width=350, drawing_mode="freedraw", key=f"client_sig_{o['訂單編號']}", update_streamlit=False)
                    else:
                        st.write(f"**📝 客戶簽名確認：** {sig if sig else '(無)'}")
                    st.table(pd.DataFrame(o["購買明細"]))
        else:
            st.info("您目前還沒有完成結案的訂單。")


# ==========================================
# 畫面 B：👷‍♂️ 現場作業人員 (專屬對點畫面)
# ==========================================
elif st.session_state.role == "operator":
    col_t, col_b = st.columns([4, 1])
    with col_t: st.title("👷‍♂️ 現場對點結算台")
    with col_b: 
        if st.button("🔄 重整", use_container_width=True): st.rerun()
    
    # 🌟 業務端雙分頁：待出貨 vs 一小時內可撤回的結案單
    op_tab1, op_tab2 = st.tabs(["📝 待出貨 (點交中)", "⏪ 近期結案單 (1小時內可撤回)"])
    
    with op_tab1:
        pending_orders = [o for o in orders if o["狀態"] == "待出貨"]
        if not pending_orders:
            st.success("目前沒有需要結算的預約單！辛苦了！")
        else:
            st.markdown("請選擇要結算的訂單，修改客戶『實際賣出』數量，並請客戶簽名。")
            for o in pending_orders:
                with st.expander(f"📝 {o['預約直播日']} | 客戶：{o['客戶名稱']} | 單號：{o['訂單編號']}", expanded=False):
                    st.write(f"**見面時間：** {o.get('見面時間', '未提供')} | **預付時金價：** {o['當時金價']}")
                    
                    op_df = pd.DataFrame(o["購買明細"])
                    op_df.insert(0, "✅ 實際售出數量", op_df["數量"]) 
                    
                    edited_op = st.data_editor(
                        op_df[["✅ 實際售出數量", "品名款式", "單價", "數量"]], 
                        hide_index=True, use_container_width=True, key=f"editor_{o['訂單編號']}"
                    )
                    
                    new_total = sum(row["✅ 實際售出數量"] * row["單價"] for _, row in edited_op.iterrows())
                    st.markdown(f"### 💰 結算應收總額： NT$ {new_total:,}")
                    
                    st.divider()
                    st.warning("⚠️ 簽名並送出後，即代表現金點交完畢，本單將鎖定結案。")
                    st.write("✍️ **請客戶在下方白框內手寫簽名：**")
                    
                    canvas_result = st_canvas(
                        fill_color="rgba(255, 255, 255, 1)", stroke_width=4, stroke_color="#000000",
                        background_color="#FFFFFF", height=200, width=350, drawing_mode="freedraw",
                        key=f"canvas_{o['訂單編號']}",
                    )
                    
                    if st.button("✅ 確認結案並送出", type="primary", key=f"btn_{o['訂單編號']}"):
                        if canvas_result.json_data is None or len(canvas_result.json_data.get("objects", [])) == 0:
                            st.error("⚠️ 請務必請客戶在上方白框內手寫簽名！")
                        else:
                            final_items = []
                            for _, row in edited_op.iterrows():
                                if row["✅ 實際售出數量"] > 0:
                                    final_items.append({
                                        "品名款式": row["品名款式"], "數量": int(row["✅ 實際售出數量"]),
                                        "單價": row["單價"], "小計": int(row["✅ 實際售出數量"] * row["單價"])
                                    })
                            
                            for raw_o in orders:
                                if raw_o['訂單編號'] == o['訂單編號']:
                                    raw_o['購買明細'] = final_items
                                    raw_o['總金額'] = new_total
                                    raw_o['狀態'] = "已結案"
                                    raw_o['客戶簽名'] = canvas_result.json_data
                                    # 🌟 記錄結案時間
                                    raw_o['結案時間'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                            save_json(DB_FILE, orders)
                            st.success("✅ 訂單已結案！")
                            st.rerun()

    with op_tab2:
        st.markdown("### ⏪ 發現錯誤？黃金一小時內可撤回重簽")
        st.caption("為防範作帳爭議，業務僅能在送出後的 **1 小時內** 執行撤回。若超過時間，請聯絡老闆由後台強制退回。")
        
        closed_orders = [o for o in orders if o["狀態"] == "已結案"]
        recent_orders = []
        now = datetime.now()
        for o in closed_orders:
            ctime_str = o.get("結案時間")
            if ctime_str:
                try:
                    ctime = datetime.strptime(ctime_str, "%Y-%m-%d %H:%M:%S")
                    if now - ctime <= timedelta(hours=1):
                        recent_orders.append(o)
                except: pass
                
        if not recent_orders:
            st.info("目前沒有1小時內結案的訂單。")
        else:
            for o in recent_orders:
                with st.expander(f"✅ {o['預約直播日']} | 客戶：{o['客戶名稱']} | 單號：{o['訂單編號']} (結案時間: {o.get('結案時間')})", expanded=False):
                    st.table(pd.DataFrame(o["購買明細"]))
                    if st.button("⏪ 發現錯誤，撤回重簽", type="primary", key=f"op_revert_{o['訂單編號']}"):
                        for raw_o in orders:
                            if raw_o['訂單編號'] == o['訂單編號']:
                                raw_o['狀態'] = "待出貨"
                                raw_o['客戶簽名'] = ""
                                raw_o['結案時間'] = ""
                        save_json(DB_FILE, orders)
                        st.success("已撤回！請至『待出貨』分頁重新修改並簽名。")
                        st.rerun()


# ==========================================
# 畫面 C：🧑‍💼 老闆專屬後台
# ==========================================
elif st.session_state.role == "admin":
    st.title("📦 B2B 批發查價台 - 老闆中控台")
    
    t_settings, t_review, t_orders, t_users = st.tabs(["⚙️ 參數與快速授權", "📋 商品審核台", "🛎️ 訂單全紀錄", "👥 帳號與業績管理"])
    
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
            save_json(SETTINGS_FILE, prod_settings)
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
        restricted_clients = {k: v for k, v in users_db.items() if v.get("is_restricted", False) and v.get("role")=="client"}
        col_a, col_b = st.columns(2)
        with col_a: target_products = st.multiselect("📦 1. 選擇商品：", df_clean["品名款式"].tolist())
        with col_b: target_clients = st.multiselect("👤 2. 開放給哪些『限制客』：", [f"{k} ({v['name']})" for k, v in restricted_clients.items()])
            
        if st.button("✨ 套用專屬權限", type="primary"):
            if target_products:
                client_str = ",".join([c.split(" (")[0] for c in target_clients])
                for p in target_products:
                    if p not in prod_settings: prod_settings[p] = {"status": "🆕 未上架", "allowed_clients": "", "fixed_price": 0}
                    prod_settings[p]["allowed_clients"] = client_str
                save_json(SETTINGS_FILE, prod_settings)
                st.success("🎉 權限套用成功！")
                st.rerun()

    with t_review:
        st.markdown("### 📋 商品上架與定價審核台")
        status_filter = st.selectbox("切換商品視角", ["全部顯示", "🆕 未上架 (待審核區)", "✅ 已上架", "🗑️ 隱藏"])
        
        df_display = df_clean[[
            "狀態", "💰 手動批發價", "👁️ 指定帳號", "品名款式", "產品照片", "網頁可用庫存", 
            "💡今日動態成本", "🔥B2B批發價", "💰實賺金額(歷史比)", "📈實賺毛利率(%)"
        ]].copy()
        
        if status_filter != "全部顯示": df_display = df_display[df_display["狀態"] == status_filter.split(" ")[0]] 
            
        if len(df_display) > 0 and st.button(f"🚀 批次將下方 {len(df_display)} 件商品設為『✅ 已上架』", type="primary"):
            for name in df_display["品名款式"]:
                if name not in prod_settings: prod_settings[name] = {"status": "✅ 已上架", "allowed_clients": "", "fixed_price": 0}
                else: prod_settings[name]["status"] = "✅ 已上架"
            save_json(SETTINGS_FILE, prod_settings)
            st.rerun()
            
        edited_df = st.data_editor(
            df_display, use_container_width=True, hide_index=True, height=600,
            column_config={
                "狀態": st.column_config.SelectboxColumn("狀態", options=["✅ 已上架", "🆕 未上架", "🗑️ 隱藏"]),
                "💰 手動批發價": st.column_config.NumberColumn("💰 你的定價 (0=跑公式)", min_value=0, step=10),
                "產品照片": st.column_config.ImageColumn("產品照片"),
                "💡今日動態成本": st.column_config.NumberColumn("💡今日動態成本", format="$%d"),
                "🔥B2B批發價": st.column_config.NumberColumn("🔥B2B批發價", format="$%d"),
                "💰實賺金額(歷史比)": st.column_config.NumberColumn("💰實賺金額", format="$%d"),
                "📈實賺毛利率(%)": st.column_config.NumberColumn("📈實賺毛利(%)", format="%.1f%%")
            }
        )
        save_df_settings(edited_df)

    with t_orders:
        st.markdown('<style>iframe[title="streamlit_drawable_canvas.st_canvas"] {pointer-events: none;}</style>', unsafe_allow_html=True)
        st.markdown("### 🛎️ 所有訂單全紀錄")
        status_tab = st.radio("篩選狀態", ["待出貨 (點交中)", "已結案 (完成)"], horizontal=True)
        filtered_orders = [o for o in orders if o["狀態"] == status_tab.split(" ")[0]]
        
        for o in filtered_orders:
            with st.expander(f"[{o['狀態']}] {o['客戶名稱']} - 總額：${o['總金額']:,} (單號:{o['訂單編號']})"):
                st.write(f"直播日: {o.get('預約直播日','-')} | 見面時間: {o.get('見面時間','-')}")
                
                sig = o.get('客戶簽名', '')
                if isinstance(sig, dict):
                    st.write("**📝 客戶簽名確認：**")
                    st_canvas(initial_drawing=sig, stroke_width=4, stroke_color="#000000", background_color="#FFFFFF", height=200, width=350, drawing_mode="freedraw", key=f"boss_sig_{o['訂單編號']}", update_streamlit=False)
                else:
                    st.write(f"**📝 客戶簽名確認：** {sig if sig else '(尚未點交)'}")
                    
                st.table(pd.DataFrame(o["購買明細"]))
                
                # 🌟 老闆專屬無限制強制退回按鈕
                if o["狀態"] == "已結案":
                    col_info, col_btn = st.columns([3, 1])
                    with col_info:
                        st.info(f"💡 提醒：這筆單已於 {o.get('結案時間', '過去')} 簽名點交，請記得至 Ragic 扣除庫存。")
                    with col_btn:
                        if st.button("🚨 強制退回業務端", key=f"boss_revert_{o['訂單編號']}", help="退回後，該筆訂單業績將被扣除，並回到『待出貨』讓業務重簽。"):
                            for raw_o in orders:
                                if raw_o['訂單編號'] == o['訂單編號']:
                                    raw_o['狀態'] = "待出貨"
                                    raw_o['客戶簽名'] = ""
                                    raw_o['結案時間'] = ""
                            save_json(DB_FILE, orders)
                            st.success("已成功退回！請通知業務重新點交。")
                            st.rerun()

    with t_users:
        st.markdown("### 🏆 客戶業績 (GMV) 與帳號管理")
        st.caption("業績只計算『已結案』的訂單。")
        
        client_spend = {}
        for o in orders:
            if o["狀態"] == "已結案": 
                client_spend[o["客戶名稱"]] = client_spend.get(o["客戶名稱"], 0) + o["總金額"]
            
        client_users = {k: v for k, v in users_db.items() if v["role"] == "client"}
        
        if client_users:
            user_df = pd.DataFrame([
                {
                    "登入帳號": k, "密碼": v["password"], "客戶名稱": v["name"],
                    "權限層級": "🔴 限制客" if v.get("is_restricted") else "🟢 一般客",
                    "🏆 已結案累積業績": client_spend.get(v["name"], 0) 
                } for k, v in client_users.items()
            ]).sort_values(by="🏆 已結案累積業績", ascending=False)
            
            st.dataframe(user_df, hide_index=True, use_container_width=True, column_config={
                "🏆 已結案累積業績": st.column_config.NumberColumn("🏆 已結案累積業績", format="$%d")
            })

        st.divider()
        st.markdown("### ➕ 新增帳號 (包含作業員)")
        with st.form("add_user_form"):
            new_u = st.text_input("帳號")
            new_p = st.text_input("密碼")
            new_n = st.text_input("顯示名稱 (例如: 陳小姐 / 現場人員B)")
            u_role = st.selectbox("帳號身分", ["🟢 一般客", "🔴 限制客", "👷‍♂️ 現場作業員"])
            
            if st.form_submit_button("建立帳號") and new_u and new_p and new_n:
                if new_u in users_db: st.warning("帳號已存在！")
                else:
                    role_map = {"🟢 一般客": ("client", False), "🔴 限制客": ("client", True), "👷‍♂️ 現場作業員": ("operator", False)}
                    users_db[new_u] = {"password": new_p, "role": role_map[u_role][0], "name": new_n, "is_restricted": role_map[u_role][1]}
                    save_json(USERS_DB_FILE, users_db)
                    st.success(f"成功建立帳號 {new_u}！")
                    st.rerun()
