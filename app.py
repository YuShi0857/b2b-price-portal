import streamlit as st
import requests
import pandas as pd
import urllib.parse
import numpy as np

st.set_page_config(page_title="B2B 查價台系統", layout="wide")

# --- 建立永久記憶區 (防止切換畫面時資料歸零) ---
if "saved_gold" not in st.session_state:
    st.session_state.saved_gold = 10000
if "saved_margin" not in st.session_state:
    st.session_state.saved_margin = 35.0

# --- 側邊欄：身分切換選單 ---
with st.sidebar:
    st.title("系統選單")
    page = st.radio("請選擇您的身分：", ["💎 B2B 客戶前台", "🧑‍💼 老闆專屬後台"])
    st.divider()
    st.caption("💡 提示：目前為測試階段，未來正式上線時，我們會為『老闆專屬後台』加上密碼鎖，防止客戶誤闖。")

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
    
    # === 共通資料準備區 ===
    records = list(data.values())
    df = pd.DataFrame(records)
    
    needed_columns = ["產品照片", "品名款式", "黃金重量(錢)", "盤商收取工資", "定價毛利等級", "手動設定售價(固定商品用)", "目前庫存量", "本件真實總成本"]
    existing_columns = [col for col in needed_columns if col in df.columns]
    df_clean = df[existing_columns].copy()
    df_clean = df_clean.fillna(0)
    
    for col in ["黃金重量(錢)", "盤商收取工資", "目前庫存量", "手動設定售價(固定商品用)", "本件真實總成本"]:
        if col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0)
            
    df_clean = df_clean[df_clean["目前庫存量"] > 0].reset_index(drop=True)
    
    def get_image_url(file_name):
        if not file_name or str(file_name) == "0": return ""
        encoded = urllib.parse.quote(str(file_name))
        return f"https://ap15.ragic.com/sims/file.jsp?a=goldselling&f={encoded}"
    
    if "產品照片" in df_clean.columns:
        df_clean["產品照片"] = df_clean["產品照片"].apply(get_image_url)


    # ==========================================
    # 畫面 A：💎 B2B 客戶前台
    # ==========================================
    if page == "💎 B2B 客戶前台":
        st.title("💎 批發商品線上型錄")
        st.caption("商品批發價將跟隨每日金價浮動，以下為今日最新報價：")
        
        st.info(f"📈 今日系統黃金牌價： **{st.session_state.saved_gold}** 元/錢")
        
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
        
        client_display = df_clean[["產品照片", "品名款式", "目前庫存量", "黃金重量(錢)", "🔥B2B批發價"]]
        
        st.dataframe(
            client_display,
            use_container_width=True,
            hide_index=True,
            height=750,
            column_config={
                "產品照片": st.column_config.ImageColumn("產品照片"),
                "目前庫存量": st.column_config.NumberColumn("庫存狀況", format="%d 件"),
                "黃金重量(錢)": st.column_config.NumberColumn("重量(錢)", format="%.2f"),
                "🔥B2B批發價": st.column_config.NumberColumn("🔥今日批發價", format="$%d")
            }
        )

    # ==========================================
    # 畫面 B：🧑‍💼 老闆專屬後台
    # ==========================================
    elif page == "🧑‍💼 老闆專屬後台":
        st.title("📦 B2B 批發查價台 - 老闆中控台")
        st.markdown("### 💰 今日參數設定")
        
        col1, col2 = st.columns(2)
        with col1:
            # 讀取與寫入永久記憶區
            new_gold = st.number_input("📈 今日黃金牌價 (元/錢)：", min_value=0, value=st.session_state.saved_gold, step=100)
            st.session_state.saved_gold = new_gold
            
        with col2:
            new_margin = st.number_input("🎯 預設 B2B 批發利潤 (%)：", min_value=0.0, value=st.session_state.saved_margin, step=5.0)
            st.session_state.saved_margin = new_margin
        
        st.divider()
        
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

        df_display = df_clean[[
            "產品照片", "品名款式", "目前庫存量", "黃金重量(錢)", 
            "本件真實總成本", "💡今日動態成本", "🏪動態零售價", "🔥B2B批發價", 
            "💰實賺金額(歷史比)", "📈實賺毛利率(%)"
        ]].copy()
        
        df_display.insert(0, "✅ 上架放行", True)

        st.markdown("### 🛠️ 批發商品上架中控台")
        st.data_editor(
            df_display,
            use_container_width=True,
            hide_index=True,
            height=750,
            column_config={
                "✅ 上架放行": st.column_config.CheckboxColumn("上架放行"),
                "產品照片": st.column_config.ImageColumn("產品照片"),
                "目前庫存量": st.column_config.NumberColumn("目前庫存量", format="%d"),
                "本件真實總成本": st.column_config.NumberColumn("歷史真實成本", format="$%d"),
                "💡今日動態成本": st.column_config.NumberColumn("💡今日動態成本", format="$%d"),
                "🏪動態零售價": st.column_config.NumberColumn("🏪動態零售價", format="$%d"),
                "🔥B2B批發價": st.column_config.NumberColumn("🔥B2B批發價", format="$%d"),
                "💰實賺金額(歷史比)": st.column_config.NumberColumn("💰實賺金額", format="$%d"),
                "📈實賺毛利率(%)": st.column_config.NumberColumn("📈實賺毛利(%)", format="%.1f%%")
            }
        )
        
else:
    st.error("讀取資料失敗，請確認 Ragic 金鑰設定。")
