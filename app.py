import streamlit as st
import requests
import pandas as pd
import urllib3
import time

# 隱藏 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 網頁基本設定
st.set_page_config(page_title="權證評估工具", layout="wide", page_icon="📈")

@st.cache_data(ttl=600)  # 快取 10 分鐘，兼顧即時性與防封鎖
def load_data():
    # 備選 API 清單
    WARRANT_URLS = [
        "https://openapi.twse.com.tw/v1/warrant/listAll",
        "https://openapi.twse.com.tw/v1/opendata/t187ap37_L"
    ]
    STOCK_API = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_AVG_ALL"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }

    # 1. 抓取股價資料
    try:
        s_resp = requests.get(STOCK_API, headers=headers, verify=False, timeout=15)
        df_s = pd.DataFrame(s_resp.json())
        df_s['ClosingPrice'] = pd.to_numeric(df_s['ClosingPrice'], errors='coerce')
        df_s['Code'] = df_s['Code'].str.strip()
        df_s['Name'] = df_s['Name'].str.strip()
    except Exception as e:
        st.error(f"股價資料抓取失敗: {e}")
        return pd.DataFrame()

    # 2. 抓取權證資料 (嘗試多個 API 直到成功)
    df_w = pd.DataFrame()
    for url in WARRANT_URLS:
        try:
            time.sleep(1) # 稍微延遲避免請求過快
            w_resp = requests.get(url, headers=headers, verify=False, timeout=15)
            if w_resp.status_code == 200 and len(w_resp.text) > 100:
                df_w = pd.DataFrame(w_resp.json())
                break
        except:
            continue
            
    if df_w.empty:
        st.error("❌ 無法從證交所取得權證資料。原因：API 回傳為空或連線遭拒。")
        st.info("💡 建議：請稍後 5 分鐘再重新整理網頁，或於台股收盤時間後測試。")
        return pd.DataFrame()

    # 3. 自動辨識欄位名稱 (適應不同 API 版本)
    col_map = {
        'strike': ['ExercisePrice', '最新履約價格(元)/履約指數', '原始履約價格(元)/履約指數'],
        'target': ['UnderlyingIndex', '標的證券/指數', '標的代號'],
        'code': ['WarrantCode', '權證代號'],
        'name': ['WarrantName', '權證簡稱', '權證名稱']
    }

    def get_real_col(target_key):
        for possible_name in col_map[target_key]:
            if possible_name in df_w.columns:
                return possible_name
        return None

    w_strike = get_real_col('strike')
    w_target = get_real_col('target')
    w_code = get_real_col('code')
    w_name = get_real_col('name')

    # 4. 資料清洗與轉換
    df_w['StrikePrice'] = pd.to_numeric(df_w[w_strike], errors='coerce')
    df_w['TargetClean'] = df_w[w_target].str.strip()

    # 5. 合併資料 (先嘗試代碼對接，再嘗試名稱對接)
    # 嘗試代碼匹配 (如: 2330 == 2330)
    merged = pd.merge(df_w, df_s, left_on='TargetClean', right_on='Code', how='left')
    
    # 如果標現價全是空值，嘗試名稱匹配 (如: 台積電 == 台積電)
    if merged['ClosingPrice'].isna().sum() > len(merged) * 0.8:
        merged = pd.merge(df_w, df_s, left_on='TargetClean', right_on='Name', how='left')

    # 保留必要欄位
    merged = merged[[w_code, w_name, 'TargetClean', 'ClosingPrice', 'StrikePrice']].copy()
    merged.columns = ['權證代號', '權證名稱', '標的', '標的現價', '履約價']
    return merged

# --- UI 介面 ---
st.title("🛡️ 權證智能分析儀表板")

data = load_data()

if not data.empty:
    st.sidebar.header("搜尋與自選")
    all_stocks = sorted(data['標的'].dropna().unique())
    
    # 搜尋框與選單
    search_input = st.sidebar.text_input("輸入標的名稱或代號 (如: 2330 或 台積電):", "台積電")
    
    # 過濾邏輯
    filtered = data[(data['標的'] == search_input) | (data['標的'].str.contains(search_input, na=False))]

    if not filtered.empty:
        # 標的資訊顯示
        target_name = filtered['標的'].iloc[0]
        curr_price = filtered['標的現價'].iloc[0]
        
        c1, c2 = st.columns(2)
        c1.metric("標的名稱", target_name)
        c2.metric("標的收盤價", f"{curr_price} 元")

        # 計算評估建議
        def get_advice(row):
            if pd.isna(row['標的現價']) or pd.isna(row['履約價']): return "資料不全"
            m_ratio = (row['標的現價'] / row['履約價'] - 1) * 100
            if -15 <= m_ratio <= -2: return "🔥 微價外 (槓桿優)"
            if -2 < m_ratio <= 10: return "✅ 微價內 (連動穩)"
            if m_ratio < -30: return "💀 深價外 (風險大)"
            return "🟡 觀察中"

        filtered['智能建議'] = filtered.apply(get_advice, axis=1)

        # 顯示表格
        st.subheader(f"🔍 '{target_name}' 相關權證分析")
        st.dataframe(filtered[['權證代號', '權證名稱', '履約價', '智能建議']], 
                     width='stretch', hide_index=True)
    else:
        st.warning(f"找不到 '{search_input}' 的相關權證，請確認代號或名稱。")
else:
    st.info("📡 等待資料傳輸中，請確保連線正常...")

st.caption("註：建議於收盤後(14:30後)查看，資料較為齊全。")