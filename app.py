import streamlit as st
import pandas as pd
import requests
import numpy as np

# ==========================================
# 1. 網頁基本設定
# ==========================================
st.set_page_config(page_title="商品庫存管理系統", page_icon="💎", layout="wide")
st.title("💎 商品與庫存主檔管理系統")

# ==========================================
# 2. 讀取 Ragic 資料 
# ==========================================
@st.cache_data(ttl=300) 
def load_ragic_data():
    # ⚠️ 【重要提醒】請換回你「原本會通的真實網址與金鑰」
    api_url = "https://www.ragic.com/YOUR_ACCOUNT/YOUR_FORM_PATH?v=3&api&limit=10000"
    headers = {'Authorization': 'Basic YOUR_API_KEY_HERE'}
    
    try:
        response = requests.get(api_url, headers=headers)
        data = response.json()
        df = pd.DataFrame.from_dict(data, orient='index')
        
        # 排除贈品
        if '定價毛利等級' in df.columns:
            df = df[df['定價毛利等級'] != '贈品']
            
        # 【新增防呆】：過濾掉 Ragic 中完全沒填寫「品名款式」的空白幽靈資料
        if '品名款式' in df.columns:
            df = df[df['品名款式'].notna() & (df['品名款式'].str.strip() != '')]
            
        return df
    except Exception as e:
        st.error(f"讀取資料失敗: {e}")
        return pd.DataFrame()

# ==========================================
# 3. 側邊欄：強制刷新按鈕、篩選器與今日牌價
# ==========================================
st.sidebar.markdown("### 🔄 系統資料同步")
if st.sidebar.button("從 Ragic 重新抓取最新資料", use_container_width=True):
    load_ragic_data.clear() # 清除快取，強制重新抓資料
    st.rerun() # 重新整理畫面

# 載入資料 (放在按鈕下方，確保能讀到最新狀態)
df = load_ragic_data()

if not df.empty:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔍 商品篩選")
    search_term = st.sidebar.text_input("尋找款式 (輸入關鍵字)：")
    
    # 重量篩選
    if '黃金重量(錢)' in df.columns:
        df['黃金重量(錢)'] = pd.to_numeric(df['黃金重量(錢)'], errors='coerce').fillna(0)
        max_val = float(df['黃金重量(錢)'].max())
        weight_range = st.sidebar.slider("黃金重量篩選 (錢)", 0.0, max_val if max_val > 0 else 10.0, (0.0, max_val if max_val > 0 else 10.0))
    else:
        weight_range = (0.0, 10.0)
    
    st.sidebar.markdown("---")
    gold_price = st.sidebar.number_input("今日黃金參考牌價 (元/錢)", value=16700, step=100)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚠️ 老闆專屬待辦區")
    need_check = st.sidebar.toggle("🔔 只顯示【待確認 / 未設底價】之商品")

    # ==========================================
    # 4. 資料過濾與【歷史/動態 利潤雙引擎計算】
    # ==========================================
    filtered_df = df.copy()
    
    if search_term:
        filtered_df = filtered_df[filtered_df['品名款式'].str.contains(search_term, na=False)]
    if '黃金重量(錢)' in df.columns:
        filtered_df = filtered_df[(filtered_df['黃金重量(錢)'] >= weight_range[0]) & (filtered_df['黃金重量(錢)'] <= weight_range[1])]

    if need_check and '主播授權底價' in df.columns:
        filtered_df = filtered_df[
            (filtered_df['主播授權底價'].isna()) | 
            (filtered_df['主播授權底價'] == '') | 
            (filtered_df['主播授權底價'] == '0')
        ]
        st.warning(f"🚨 目前為待辦模式：共有 {len(filtered_df)} 件商品尚未設定底價，請確認！")

    # ------------------------------------------
    # 💡 核心計算：安全提取數值防呆機制
    # ------------------------------------------
    def safe_numeric(data_frame, col_name):
        if col_name in data_frame.columns:
            return pd.to_numeric(data_frame[col_name], errors='coerce').fillna(0)
        return pd.Series(0, index=data_frame.index)

    weight = safe_numeric(filtered_df, '黃金重量(錢)')
    labor_fee = safe_numeric(filtered_df, '盤商收取工資')
    historical_cost = safe_numeric(filtered_df, '本件真實總成本')
    b2b_price = safe_numeric(filtered_df, '廠商對接成本價')
    b2c_price = safe_numeric(filtered_df, '標準售價')

    # ------------------------------------------
    # 📊 動態/歷史成本與毛利計算
    # ------------------------------------------
    filtered_df['動態總成本(即時)'] = (weight * gold_price) + labor_fee
    
    filtered_df['B2B實賺(動態)'] = b2b_price - filtered_df['動態總成本(即時)']
    filtered_df['B2C實賺(動態)'] = b2c_price - filtered_df['動態總成本(即時)']
    filtered_df['B2B毛利率(動態)'] = np.where(b2b_price > 0, (filtered_df['B2B實賺(動態)'] / b2b_price * 100).round(1).astype(str) + '%', '0%')
    filtered_df['B2C毛利率(動態)'] = np.where(b2c_price > 0, (filtered_df['B2C實賺(動態)'] / b2c_price * 100).round(1).astype(str) + '%', '0%')

    filtered_df['B2B實賺(歷史)'] = b2b_price - historical_cost
    filtered_df['B2C實賺(歷史)'] = b2c_price - historical_cost
    filtered_df['B2B毛利率(歷史)'] = np.where(b2b_price > 0, (filtered_df['B2B實賺(歷史)'] / b2b_price * 100).round(1).astype(str) + '%', '0%')
    filtered_df['B2C毛利率(歷史)'] = np.where(b2c_price > 0, (filtered_df['B2C實賺(歷史)'] / b2c_price * 100).round(1).astype(str) + '%', '0%')

    # ==========================================
    # 5. 主畫面：B2B / B2C 欄位一鍵切換與排序
    # ==========================================
    st.markdown("### ⚙️ 欄位顯示設定")
    
    all_columns = list(filtered_df.columns)
    
    view_mode = st.radio(
        "⚡ 快速切換檢視情境 (自動幫您勾選基本盤欄位)：",
        ["🏢 B2B 批發模式", "🛍️ B2C 零售模式", "🔧 綜合檢視 (全開)"],
        horizontal=True
    )
    
    if view_mode == "🏢 B2B 批發模式":
        default_cols = [c for c in ["產品照片", "品名款式", "黃金重量(錢)", "本件真實總成本", "動態總成本(即時)", "廠商對接成本價", "B2B毛利率(歷史)", "B2B毛利率(動態)"] if c in all_columns]
    elif view_mode == "🛍️ B2C 零售模式":
        default_cols = [c for c in ["產品照片", "品名款式", "黃金重量(錢)", "本件真實總成本", "動態總成本(即時)", "標準售價", "B2C毛利率(歷史)", "B2C毛利率(動態)"] if c in all_columns]
    else:
        default_cols = [c for c in ["品名款式", "黃金重量(錢)", "B2C毛利率(歷史)", "B2C毛利率(動態)", "B2B毛利率(歷史)", "B2B毛利率(動態)"] if c in all_columns]

    st.caption("💡 提示：在下方框框中，**「取消勾選再重新點選」** 就可以改變欄位在表格中的左右顯示順序！")
    selected_columns = st.multiselect(
        "請選擇要在表格中檢視的欄位：",
        options=all_columns,
        default=default_cols
    )

    st.markdown("---")
    
    # ==========================================
    # 6. 顯示資料
    # ==========================================
    display_mode = st.radio("顯示模式", ["大圖示檢視 (適合檢視圖片)", "表格快速編輯"], horizontal=True, label_visibility="collapsed")
    
    st.write(f"共找到 {len(filtered_df)} 件商品")

    if display_mode == "大圖示檢視 (適合檢視圖片)":
        cols = st.columns(4)
        for index, (df_index, row) in enumerate(filtered_df.iterrows()):
            col = cols[index % 4]
            with col:
                st.info(f"✔️ {row.get('品名款式', '未知商品')} ({row.get('黃金重量(錢)', 0)} 錢)")
                
                if view_mode == "🛍️ B2C 零售模式":
                    st.caption(f"歷史毛利: {row.get('B2C毛利率(歷史)')} | 動態毛利: {row.get('B2C毛利率(動態)')}")
                elif view_mode == "🏢 B2B 批發模式":
                    st.caption(f"歷史毛利: {row.get('B2B毛利率(歷史)')} | 動態毛利: {row.get('B2B毛利率(動態)')}")
                
                unique_key = f"btn_detail_{index}_{row.get('商品專屬編號', df_index)}"
                if st.button("🔍 查看商品詳情", key=unique_key, use_container_width=True):
                    st.toast(f"查看 {row.get('品名款式')}")
                    
    else:
        if selected_columns:
            st.dataframe(filtered_df[selected_columns], use_container_width=True, hide_index=True)

else:
    st.info("系統目前沒有資料，或正在連線至 Ragic...")
