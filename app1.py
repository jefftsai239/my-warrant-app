import requests
import pandas as pd

# API 網址
WARRANT_API = "https://openapi.twse.com.tw/v1/warrant/listAll"

print("正在抓取資料...")
w_data = requests.get(WARRANT_API).json()
df_warrant = pd.DataFrame(w_data)

# 💡 防錯機制 1：清除欄位名稱可能存在的空格
df_warrant.columns = df_warrant.columns.str.strip()

# 💡 防錯機制 2：檢查欄位是否存在，不存在就印出提示
target_col = 'ExercisePrice'
if target_col in df_warrant.columns:
    df_warrant[target_col] = pd.to_numeric(df_warrant[target_col], errors='coerce')
    print(f"成功處理 {target_col}")
else:
    print(f"錯誤：找不到 '{target_col}' 欄位！")
    print("實際收到的欄位是：", df_warrant.columns.tolist())