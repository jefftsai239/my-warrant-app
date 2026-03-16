import streamlit as st
import requests
import pandas as pd
import urllib3

# 隱藏 SSL 警告訊息 (部署至雲端必要設定)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 網頁基本設定
st.set_page_config(page_title="權證智能評估儀表板", layout="wide", page_icon="📈")

# 1. 資料讀取函式 (加入快取機制與 SSL 忽略)
@st.cache_data(ttl=3600)  # 每小時自動更新一次
def load_data():
    WARRANT_API = "https://openapi.twse.com.tw/v1/opendata/t187ap37_L"
    STOCK_API = "https://openapi.twse.com.tw/v1/exchange_report/STOCK_DAY_AVG_ALL"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    
    try:
        # 抓取權證與股價資料，verify=False 解決雲端 SSL 報錯
        w_resp = requests.get(WARRANT_API, headers=headers, verify=False, timeout=15)
        s_resp = requests.get(STOCK_API, headers=headers, verify=False, timeout=15)
        
        df_w = pd.DataFrame(w_resp.json())
        df_s = pd.DataFrame(s_resp.json())
        
        # 資料清洗 - 股票
        df_s['ClosingPrice'] = pd.to_numeric(df_s['ClosingPrice'], errors='coerce')
        df_s['Code'] = df_s['Code'].str.strip()
        df_s['Name'] = df_s['Name'].str.strip()
        
        # 資料清洗 - 權證
        df_w['最新履約價格'] = pd.to_numeric(df_w['最新履約價格(元)/履約指數'], errors='coerce')
        df_w['標的名稱'] = df_w['標的證券/指數'].str.strip()
        
        # 合併兩表 (以標的名稱對應股票名稱)
        merged = pd.merge(df_w, df_s, left_on='標的名稱', right_on='Name', how='left')
        return merged
    except Exception as e:
        st.error(f"❌ 數據讀取發生錯誤: {e}")
        return pd.DataFrame()

# 2. 評估邏輯函式
def smart_eval(row):
    if pd.isna(row['ClosingPrice']) or pd.isna(row['最新履約價格']):
        return "資料缺漏"
    
    # 計算價內外幅度 % (現價 / 履約價 - 1)
    m_ratio = (row['ClosingPrice'] / row['最新履約價格'] - 1) * 100
    
    if -15 <= m_ratio <= -2:
        return "🔥 潛力：微價外 (高槓桿)"
    elif -2 < m_ratio <= 10:
        return "✅ 穩健：微價內 (連動強)"
    elif m_ratio < -30:
        return "💀 警報：深價外 (風險高)"
    else:
        return "🟡 觀察：條件一般"

# 3. UI 介面設計
st.title("📈 權證智能評估系統")
st.markdown("---")

df = load_data()

if not df.empty:
    # 側邊欄控制
    st.sidebar.header("🔍 篩選與自選")
    mode = st.sidebar.radio("查詢模式", ["輸入代碼或名稱", "常用自選股"])
    
    if mode == "輸入代碼或名稱":
        target_stock = st.sidebar.text_input("請輸入股票名稱 (如: 台積電):", "台積電")
    else:
        my_watchlist = ["台積電", "鴻海", "聯發科", "廣達", "欣興", "長榮"]
        target_stock = st.sidebar.selectbox("自選清單:", my_watchlist)

    # 過濾資料
    filtered = df[df['標的名稱'] == target_stock].copy()

    if not filtered.empty:
        # 計算智能建議
        filtered['智能建議'] = filtered.apply(smart_eval, axis=1)
        
        # 頂部資訊卡片
        price = filtered['ClosingPrice'].iloc[0]
        col1, col2 = st.columns(2)
        col1.metric("標的股票", target_stock)
        col2.metric("標的現價", f"{price} TWD")
        
        st.subheader(f"相關權證清單 ({len(filtered)} 檔)")
        
        # 整理最終表格
        display_df = filtered[['權證代號', '權證簡稱', '最新履約價格', '智能建議']]
        display_df.columns = ['權證代號', '權證名稱', '履約價格', '智能評估建議']
        
        # 表格美化與顯示
        st.dataframe(display_df, width='stretch', hide_index=True)
    else:
        st.warning(f"目前找不到 '{target_stock}' 的相關權證資料，請確認名稱是否正確。")
else:
    st.error("無法取得資料，請檢查網路連線或 API 狀態。")

st.markdown("---")
st.caption("資料來源：臺灣證券交易所 (TWSE) Open Data / 計算結果僅供參考，不構成投資建議。")