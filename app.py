import streamlit as st
import requests
import pandas as pd
import urllib.parse
import numpy as np

st.set_page_config(page_title="B2B 查價台系統", layout="wide")

# --- 建立永久記憶區 ---
if "saved_gold" not in st.session_state:
    st.session_state.saved_gold = 10000
if "saved_margin" not in st.session_state:
    st.session_state.saved_margin = 35.0
if "listing_status" not in st.session_state:
    st.session_state.listing_status = {} 

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
    # 🌟 核心計算區 (先算好所有的價格，才能產生動態篩選器的區間)
    # ==========================================
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


    # ==========================================
    # 🌟 左側邊欄：身分切換 ＆ 智慧篩選器
    # ==========================================
    with st.sidebar:
        st.title("系統選單")
        page = st.radio("請選擇您的身分：", ["💎 B2B 客戶前台", "🧑‍💼 老闆專屬後台"])
        st.divider()
        
        st.markdown("### 🔍 智慧商品篩選")
        
        # 1. 關鍵字篩選
        search_kw = st.text_input("🔑 關鍵字搜尋 (品名/款式)：", placeholder="例如：手繩, 蝴蝶結...")
        
        # 取得資料庫的最大/最小值，用來動態設定滑桿範圍
        if not df_clean.empty:
            w_min, w_max = float(df_clean["黃金重量(錢)"].min()), float(df_clean["黃金重量(錢)"].max())
            if w_min == w_max: w_max += 0.01 # 避免最大最小值一樣導致報錯
            weight_range = st.slider("⚖️ 重量區間 (錢)", w_min, w_max, (w_min, w_max), step=0.01)

            p_min, p_max = float(df_clean["🔥B2B批發價"].min()), float(df_clean["🔥B2B批發價"].max())
            if p_min == p_max: p_max += 100.0
            price_range = st.slider("💰 批發價區間 (元)", int(p_min), int(p_max), (int(p_min), int(p_max)), step=100)

            s_min, s_max = int(df_clean["目前庫存量"].min()), int(df_clean["目前庫存量"].max())
            if s_min == s_max: s_max += 1
            stock_range = st.slider("📦 庫存數量區間", s_min, s_max, (s_min, s_max), step=1)
        else:
            weight_range, price_range, stock_range = (0.0, 10.0), (0, 10000), (0, 100)

    # ==========================================
    # 🌟 執行篩選動作：套用使用者在左邊設定的條件
    # ==========================================
    df_filtered = df_clean[
        (df_clean["黃金重量(錢)"] >= weight_range[0]) & (df_clean["黃金重量(錢)"] <= weight_range[1]) &
        (df_clean["🔥B2B批發價"] >= price_range[0]) & (df_clean["🔥B2B批發價"] <= price_range[1]) &
        (df_clean["目前庫存量"] >= stock_range[0]) & (df_clean["目前庫存量"] <= stock_range[1])
    ]
    if search_kw:
        df_filtered = df_filtered[df_filtered["品名款式"].str.contains(search_kw, na=False, case=False)]


    # ==========================================
    # 畫面 A：💎 B2B 客戶前台
    # ==========================================
    if page == "💎 B2B 客戶前台":
        st.title("💎 批發商品線上型錄")
        st.caption("商品批發價將跟隨每日金價浮動，以下為今日最新報價：")
        
        st.info(f"📈 今日系統黃金牌價： **{st.session_state.saved_gold}** 元/錢")
        
        # 前台再多一道過濾：只顯示有打勾放行的商品
        df_client = df_filtered[df_filtered["✅ 上架放行"] == True]
        client_display = df_client[["產品照片", "品名款式", "目前庫存量", "黃金重量(錢)", "🔥B2B批發價"]]
        
        st.markdown(f"**共找到 {len(client_display)} 筆符合條件的商品**")
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
            new_gold = st.number_input("📈 今日黃金牌價 (元/錢)：", min_value=0, value=st.session_state.saved_gold, step=100)
            if new_gold != st.session_state.saved_gold:
                st.session_state.saved_gold = new_gold
                st.rerun() # 金價改變時，立刻重新計算畫面
            
        with col2:
            new_margin = st.number_input("🎯 預設 B2B 批發利潤 (%)：", min_value=0.0, value=st.session_state.saved_margin, step=5.0)
            if new_margin != st.session_state.saved_margin:
                st.session_state.saved_margin = new_margin
                st.rerun()

        st.divider()
        
        df_display = df_filtered[[
            "✅ 上架放行", "產品照片", "品名款式", "目前庫存量", "黃金重量(錢)", 
            "本件真實總成本", "💡今日動態成本", "🏪動態零售價", "🔥B2B批發價", 
            "💰實賺金額(歷史比)", "📈實賺毛利率(%)"
        ]].copy()
        
        st.markdown("### 🛠️ 批發商品上架中控台")
        st.markdown(f"**目前篩選出 {len(df_display)} 筆商品**")
        
        edited_df = st.data_editor(
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
        
        # 存檔打勾狀態
        for index, row in edited_df.iterrows():
            st.session_state.listing_status[row["品名款式"]] = row["✅ 上架放行"]
        
else:
    st.error("讀取資料失敗，請確認 Ragic 金鑰設定。")
