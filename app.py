import streamlit as st
import requests
import pandas as pd

# 網頁標題設定
st.set_page_config(page_title="權證智能評估儀表板", layout="wide")
st.title("📈 權證自選股分析系統")

# 1. 抓取資料 (加入快取功能，避免每次點選都重新下載，速度會變快)
@st.cache_data
def load_data():
    WARRANT_API = "https://openapi.twse.com.tw/v1/opendata/t187ap37_L"
    STOCK_API = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_AVG_ALL"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    w_json = requests.get(WARRANT_API, headers=headers).json()
    s_json = requests.get(STOCK_API, headers=headers).json()
    
    df_w = pd.DataFrame(w_json)
    df_s = pd.DataFrame(s_json)
    
    # 清洗數據
    df_s['ClosingPrice'] = pd.to_numeric(df_s['ClosingPrice'], errors='coerce')
    df_s['Code'] = df_s['Code'].str.strip()
    df_s['Name'] = df_s['Name'].str.strip()
    
    df_w['最新履約價格'] = pd.to_numeric(df_w['最新履約價格(元)/履約指數'], errors='coerce')
    df_w['標的名稱'] = df_w['標的證券/指數'].str.strip()
    
    # 合併
    df = pd.merge(df_w, df_s, left_on='標的名稱', right_on='Name', how='left')
    return df

df = load_data()

# 2. 側邊欄：設定自選股
st.sidebar.header("自選股設定")
search_method = st.sidebar.radio("查詢方式", ["輸入代碼/名稱", "常用自選股"])

if search_method == "輸入代碼/名稱":
    search_query = st.sidebar.text_input("輸入股票名稱 (例如: 台積電):", "台積電")
else:
    # 你可以在這裡設定你常看的股票清單
    my_stocks = ["台積電", "鴻海", "聯發科", "欣興", "長榮"]
    search_query = st.sidebar.selectbox("選擇自選股:", my_stocks)

# 3. 執行過濾
filtered_df = df[df['標的名稱'] == search_query].copy()

# 4. 智能評估邏輯
def smart_eval(row):
    if pd.isna(row['ClosingPrice']) or pd.isna(row['最新履約價格']): return "資料缺漏"
    m_ratio = (row['ClosingPrice'] / row['最新履約價格'] - 1) * 100
    if -15 <= m_ratio <= -2: return "🔥 潛力：微價外"
    elif -2 < m_ratio <= 10: return "✅ 穩健：微價內"
    elif m_ratio < -25: return "💀 警報：深價外"
    return "🟡 觀察中"

if not filtered_df.empty:
    filtered_df['智能建議'] = filtered_df.apply(smart_eval, axis=1)
    
    # 顯示標的資訊卡片
    stock_price = filtered_df['ClosingPrice'].iloc[0]
    st.metric(label=f"當前標的：{search_query}", value=f"{stock_price} TWD")
    
    # 整理表格顯示
    display_df = filtered_df[['權證代號', '權證簡稱', '最新履約價格', '智能建議']]
    display_df.columns = ['權證代號', '權證名稱', '履約價', '智能評估建議']
    
    # 顯示美化表格
    st.dataframe(display_df, width='stretch', hide_index=True)
else:
    st.warning(f"找不到 '{search_query}' 的相關權證，請確認名稱是否正確。")

# 5. 下一步建議
st.info("💡 提示：點選表格標題可以進行排序（例如按履約價排序）。")