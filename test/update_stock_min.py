# -*- coding: utf-8 -*-
import tushare as ts
import pandas as pd
from datetime import datetime, timedelta
import os
import time

# -----------------------
# Tushare 配置
# -----------------------
TOKEN = "W5yA7cE9gI1kM3oQ5sU7wY9aC1eG3iK5mO7qS9uW1yA3cE5gI7kM9oQ1sU3wY5aC7eG9iK1mO3qS"
PROXY_URL = "http://47.92.128.69:35721/dataapi"

# -----------------------
# 下载配置
# -----------------------
STOCK_FILE = "output/a_stock_selected.xlsx"   # Excel 股票池
OUTPUT_DIR = "cache/minute_data"       # 保存目录
MINUTES = ['1min','5min','30min']      # Tushare 支持的 freq
DAYS = 10
RETRY_TIMES = 3

os.makedirs(OUTPUT_DIR, exist_ok=True)

# -----------------------
# 初始化 Tushare
# -----------------------
pro = ts.pro_api(TOKEN)
pro._DataApi__http_url = PROXY_URL

# -----------------------
# 下载单支股票分钟数据
# -----------------------
def download_stock_minutes(ts_code, start_str, end_str):
    all_data = {}
    for freq in MINUTES:
        for attempt in range(1, RETRY_TIMES+1):
            try:
                df_min = pro.stk_mins(
                    ts_code=ts_code,
                    start_date=start_str,
                    end_date=end_str,
                    freq=freq,
                    adj='qfq'
                )
                all_data[freq] = df_min
                print(f"  {freq} 数据条数: {len(df_min)}")
                break
            except Exception as e:
                print(f"  获取 {ts_code} {freq} 数据失败（第{attempt}次）: {e}")
                time.sleep(1)
                all_data[freq] = pd.DataFrame()
    return all_data

# -----------------------
# 主函数
# -----------------------
def main():
    try:
        # 读取股票池
        df_stocks = pd.read_excel(STOCK_FILE, dtype=str)
        if "代码" not in df_stocks.columns:
            raise ValueError(f"{STOCK_FILE} 中没有 '代码' 列")

        stock_list = df_stocks["代码"].tolist()
        total_stocks = len(stock_list)
        print(f"股票池共 {total_stocks} 只股票")

        # 设置下载日期
        end_date = datetime.now()
        start_date = end_date - timedelta(days=DAYS)
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")

        # 下载每支股票分钟数据
        start_time = time.time()
        for idx, code in enumerate(stock_list, start=1):
            ts_code = str(code).zfill(6)
            if ts_code.startswith(("0","3")):
                ts_code_full = ts_code + ".SZ"
            elif ts_code.startswith("6"):
                ts_code_full = ts_code + ".SH"
            else:
                ts_code_full = ts_code

            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 正在下载 {ts_code_full} ({idx}/{total_stocks})")

            all_data = download_stock_minutes(ts_code_full, start_str, end_str)

            # 保存文件，命名为 {代码}_{分钟}m.csv
            for freq, df_min in all_data.items():
                if df_min is not None and not df_min.empty:
                    freq_num = freq.replace("min","")
                    out_file = os.path.join(OUTPUT_DIR, f"{ts_code}_{freq_num}m.csv")
                    df_min.to_csv(out_file, index=False)
                    print(f"  保存文件: {out_file}, {len(df_min)} 行")

            elapsed = time.time() - start_time
            avg_time_per_stock = elapsed / idx
            est_remaining = (total_stocks - idx) * avg_time_per_stock
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 已完成 {idx}/{total_stocks}，预计剩余时间 {timedelta(seconds=int(est_remaining))}")

    except Exception as e:
        print("运行失败，错误信息如下：")
        print(type(e).__name__, e)

if __name__ == "__main__":
    main()