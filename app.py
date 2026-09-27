import streamlit as st
import requests
import pandas as pd
import urllib.parse
import numpy as np

st.set_page_config(page_title="B2B 查價台系統", layout="wide")
st.title("📦 B2B 批發查價台 - 老闆專屬後台")

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
    
    st.markdown("### 💰 今日參數設定")
    col1, col2 = st.columns(2)
    with col1:
        today_gold_price = st.number_input("📈 今日黃金牌價 (元/錢)：", min_value=0, value=10000, step=100)
    with col2:
        default_margin = st.number_input("🎯 預設 B2B 批發利潤 (%)：", min_value=0.0, value=35.0, step=5.0)
    
    st.divider()
    
    records = list(data.values())
    df = pd.DataFrame(records)
    
    needed_columns = ["產品照片", "品名款式", "黃金重量(錢)", "盤商收取工資", "定價毛利等級", "手動設定售價(固定商品用)", "目前庫存量", "本件真實總成本"]
    existing_columns = [col for col in needed_columns if col in df.columns]
    df_clean = df[existing_columns].copy()
    df_clean = df_clean.fillna(0)
    
    # 轉換數字格式
    for col in ["黃金重量(錢)", "盤商收取工資", "目前庫存量", "手動設定售價(固定商品用)", "本件真實總成本"]:
        if col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0)
            
    # 過濾零庫存
    df_clean = df_clean[df_clean["目前庫存量"] > 0].reset_index(drop=True)
    
    # 轉換圖片網址
    def get_image_url(file_name):
        if not file_name or str(file_name) == "0": return ""
        encoded = urllib.parse.quote(str(file_name))
        return f"https://ap15.ragic.com/sims/file.jsp?a=goldselling&f={encoded}"
    if "產品照片" in df_clean.columns:
        df_clean["產品照片"] = df_clean["產品照片"].apply(get_image_url)

    # ==========================================
    # 動態定價與利潤計算核心
    # ==========================================
    # 1. 算今日成本
    df_clean["💡今日動態成本"] = np.round((today_gold_price * df_clean["黃金重量(錢)"]) + df_clean["盤商收取工資"])
    
    # 2. 算今日零售價
    def calculate_retail(row):
        level = str(row.get("定價毛利等級", ""))
        cost = row["💡今日動態成本"]
        
        if "固定價格" in level:
            return row.get("手動設定售價(固定商品用)", cost)
        elif "B級" in level:
            return np.round(cost * 1.16 + 500)
        elif "C級" in level:
            return np.round(cost * 1.20 + 600)
        else:
            return cost

    df_clean["🏪動態零售價"] = df_clean.apply(calculate_retail, axis=1)
    
    # 3. 計算 B2B 批發價
    df_clean["原本預期利潤"] = df_clean["🏪動態零售價"] - df_clean["💡今日動態成本"]
    df_clean["🔥B2B批發價"] = np.round(df_clean["💡今日動態成本"] + (df_clean["原本預期利潤"] * (default_margin / 100)))

    # 4. 🌟 新增老闆專屬指標：實賺金額與毛利率 (與歷史成本比對)
    df_clean["💰實賺金額(歷史比)"] = df_clean["🔥B2B批發價"] - df_clean["本件真實總成本"]
    
    # 避免除以 0 造成程式報錯
    df_clean["📈實賺毛利率(%)"] = np.where(
        df_clean["🔥B2B批發價"] > 0, 
        (df_clean["💰實賺金額(歷史比)"] / df_clean["🔥B2B批發價"]) * 100, 
        0
    )
    # ==========================================

    # 整理顯示清單：加入新欄位
    df_display = df_clean[[
        "產品照片", "品名款式", "目前庫存量", "黃金重量(錢)", 
        "本件真實總成本", "💡今日動態成本", "🏪動態零售價", "🔥B2B批發價", 
        "💰實賺金額(歷史比)", "📈實賺毛利率(%)"
    ]].copy()
    
    df_display.insert(0, "✅ 上架放行", True)

    st.markdown("### 🛠️ 批發商品上架中控台")
    st.caption("表格內的成本與批發價，已根據你上方輸入的【今日黃金牌價】與你的【專屬 Ragic 公式】自動重算完畢！")

    st.data_editor(
        df_display,
        use_container_width=True,
        hide_index=True,
        height=700,
        column_config={
            "✅ 上架放行": st.column_config.CheckboxColumn("上架放行"),
            "產品照片": st.column_config.ImageColumn("產品照片"),
            "目前庫存量": st.column_config.NumberColumn("目前庫存量", format="%d"),
            "本件真實總成本": st.column_config.NumberColumn("歷史真實成本", format="$%d"),
            "💡今日動態成本": st.column_config.NumberColumn("💡今日動態成本", format="$%d"),
            "🏪動態零售價": st.column_config.NumberColumn("🏪動態零售價", format="$%d"),
            "🔥B2B批發價": st.column_config.NumberColumn("🔥B2B批發價", format="$%d"),
            "💰實賺金額(歷史比)": st.column_config.NumberColumn("💰實賺金額", help="用 B2B 批發價扣掉你當初買的歷史真實成本", format="$%d"),
            "📈實賺毛利率(%)": st.column_config.NumberColumn("📈實賺毛利(%)", format="%.1f%%")
        }
    )
    
else:
    st.error("讀取資料失敗，請確認 Ragic 金鑰設定。")
