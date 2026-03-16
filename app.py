import streamlit as st
import requests
import pandas as pd
import urllib3
import time

# 隱藏 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 網頁基本設定
st.set_page_config(page_title="權證智能分析", layout="wide", page_icon="📈")

@st.cache_data(ttl=600)
def load_data():
    # 權證與股價 API 網址
    WARRANT_API = "https://openapi.twse.com.tw/v1/warrant/listAll"
    STOCK_API = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_AVG_ALL"
    
    # 強化 Headers：模擬最新版 Chrome 瀏覽器，減少被擋機率
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.twse.com.tw/',
        'Connection': 'keep-alive'
    }

    def fetch_with_retry(url, name, retries=3):
        for i in range(retries):
            try:
                time.sleep(1) # 每次重試前稍微延遲
                resp = requests.get(url, headers=headers, verify=False, timeout=15)
                if resp.status_code == 200 and len(resp.text.strip()) > 0:
                    return resp.json()
                else:
                    st.warning(f"正在嘗試重新連接 {name} (第 {i+1} 次)...")
            except Exception:
                continue
        return None

    # 1. 抓取股價
    s_json = fetch_with_retry(STOCK_API, "股價資料")
    if not s_json:
        st.error("❌ 股價資料抓取失敗。這通常是證交所暫時阻擋了雲端連線。")
        return pd.DataFrame()
    
    df_s = pd.DataFrame(s_json)
    df_s['ClosingPrice'] = pd.to_numeric(df_s['ClosingPrice'], errors='coerce')
    df_s['Code'] = df_s['Code'].str.strip()
    df_s['Name'] = df_s['Name'].str.strip()

    # 2. 抓取權證
    w_json = fetch_with_retry(WARRANT_API, "權證資料")
    if not w_json:
        # 如果 listAll 失敗，嘗試備用 API
        W_BACKUP = "https://openapi.twse.com.tw/v1/opendata/t187ap37_L"
        w_json = fetch_with_retry(W_BACKUP, "備用權證資料")
        
    if not w_json:
        st.error("❌ 權證資料抓取失敗。")
        return pd.DataFrame()

    df_w = pd.DataFrame(w_json)

    # 3. 自動辨識欄位
    col_map = {
        'strike': ['ExercisePrice', '最新履約價格(元)/履約指數'],
        'target': ['UnderlyingIndex', '標的證券/指數'],
        'code': ['WarrantCode', '權證代號'],
        'name': ['WarrantName', '權證簡稱']
    }

    def get_col(k):
        for c in col_map[k]:
            if c in df_w.columns: return c
        return None

    w_strike, w_target, w_code, w_name = get_col('strike'), get_col('target'), get_col('code'), get_col('name')

    # 4. 清洗與合併
    df_w['StrikePrice'] = pd.to_numeric(df_w[w_strike], errors='coerce')
    df_w['TargetClean'] = df_w[w_target].str.strip()

    # 雙重匹配邏輯 (代號 vs 名稱)
    merged = pd.merge(df_w, df_s, left_on='TargetClean', right_on='Code', how='left')
    if merged['ClosingPrice'].isna().sum() > len(merged) * 0.8:
        merged = pd.merge(df_w, df_s, left_on='TargetClean', right_on='Name', how='left')

    # 整理最終表格
    final = merged[[w_code, w_name, 'TargetClean', 'ClosingPrice', 'StrikePrice']].copy()
    final.columns = ['權證代號', '權證名稱', '標的', '標的現價', '履約價']
    return final

# --- 介面呈現 ---
st.title("🛡️ 權證智能分析儀表板")

data = load_data()

if not data.empty:
    st.sidebar.header("搜尋與自選")
    search_input = st.sidebar.text_input("輸入標的名或代號 (如: 台積電 或 2330):", "台積電")
    
    # 模糊搜尋
    filtered = data[data['標的'].str.contains(search_input, na=False)]

    if not filtered.empty:
        curr_price = filtered['標的現價'].iloc[0]
        st.subheader(f"🔍 {search_input} 相關權證分析")
        st.metric("標的收盤價", f"{curr_price} 元")

        def get_advice(row):
            if pd.isna(row['標的現價']) or pd.isna(row['履約價']): return "資料不全"
            m_ratio = (row['標的現價'] / row['履約價'] - 1) * 100
            if -15 <= m_ratio <= -2: return "🔥 微價外 (槓桿優)"
            if -2 < m_ratio <= 10: return "✅ 微價內 (連動穩)"
            if m_ratio < -30: return "💀 深價外 (風險大)"
            return "🟡 觀察中"

        filtered['智能建議'] = filtered.apply(get_advice, axis=1)
        st.dataframe(filtered[['權證代號', '權證名稱', '履約價', '智能建議']], width='stretch', hide_index=True)
    else:
        st.warning("查無資料，請確認搜尋關鍵字。")
else:
    st.info("📡 正在等待證交所回應，請重新整理網頁或稍後再試。")