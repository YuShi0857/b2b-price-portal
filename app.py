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

if "undo_b2b" not in st.
