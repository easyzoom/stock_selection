# test/test_tushare_rt_min.py
# 用于测试当前 Tushare Token/代理是否支持 rt_min 实时分钟K线接口。
#
# 推荐放置位置：
# stock_selection/
# ├── config.py
# ├── main.py
# └── test/
#     └── test_tushare_rt_min.py
#
# 运行方式：
# python test/test_tushare_rt_min.py
#
# 如果请求次数过快，可以调大 REQUEST_SLEEP_SECONDS 和 RATE_LIMIT_SLEEP_SECONDS。

from pathlib import Path
import sys
import time
import traceback

import pandas as pd
import tushare as ts


# =========================
# 路径处理：让 test/ 下脚本能读取根目录 config.py
# =========================

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from config import TUSHARE_TOKEN, TUSHARE_HTTP_URL


# =========================
# 测试配置
# =========================

# 先少测一点，避免频率过快。
# 确认能用后，再增加股票或周期。
TEST_CODES = [
    "600000.SH",
    "000001.SZ",
]

TEST_FREQS = [
    "1MIN",
    "5MIN",
    "15MIN",
    "30MIN",
    "60MIN",
]

# 每次正常请求之间的间隔，单位：秒。
# 如果还报“请求次数过快”，建议改成 5 或 10。
REQUEST_SLEEP_SECONDS = 5

# 遇到“请求次数过快”后的等待时间，单位：秒。
RATE_LIMIT_SLEEP_SECONDS = 20

# 每个 code + freq 最多请求次数。
MAX_RETRY = 2

# 是否打印完整 DataFrame。
PRINT_FULL_DF = False


# =========================
# 初始化 Tushare
# =========================

def init_tushare_pro():
    if not TUSHARE_TOKEN or TUSHARE_TOKEN == "这里填你的token":
        raise ValueError("没有配置 TUSHARE_TOKEN，请检查 config.py。")

    ts.set_token(TUSHARE_TOKEN)
    pro = ts.pro_api(TUSHARE_TOKEN)

    if TUSHARE_HTTP_URL:
        # 兼容你当前使用的 Tushare 代理地址。
        pro._DataApi__http_url = TUSHARE_HTTP_URL

    return pro


def print_df_preview(df: pd.DataFrame):
    print(f"请求成功，返回行数：{len(df)}")
    print(f"字段：{df.columns.tolist()}")

    required_cols = {"ts_code", "time", "open", "close", "high", "low", "vol", "amount"}
    missing_cols = required_cols - set(df.columns)

    if missing_cols:
        print(f"字段检查失败，缺少字段：{sorted(missing_cols)}")
    else:
        print("字段检查通过：包含分钟K线判断所需字段。")

    if df.empty:
        print("返回为空 DataFrame。")
        return

    if PRINT_FULL_DF:
        print("\n完整数据：")
        print(df.to_string(index=False))
    else:
        print("\n前5行：")
        print(df.head().to_string(index=False))

        print("\n后5行：")
        print(df.tail().to_string(index=False))


def call_rt_min_with_retry(pro, ts_code: str, freq: str):
    last_error = None

    for attempt in range(1, MAX_RETRY + 1):
        try:
            print(f"请求尝试：{attempt}/{MAX_RETRY}")
            df = pro.rt_min(ts_code=ts_code, freq=freq)
            return df, None

        except Exception as e:
            last_error = e
            err_msg = str(e)

            print("请求失败。")
            print(f"错误类型：{type(e).__name__}")
            print(f"错误信息：{err_msg}")

            # Tushare 常见限频提示
            if "请求次数过快" in err_msg or "频率" in err_msg or "rate" in err_msg.lower():
                if attempt < MAX_RETRY:
                    print(f"判断为限频，等待 {RATE_LIMIT_SLEEP_SECONDS} 秒后重试...")
                    time.sleep(RATE_LIMIT_SLEEP_SECONDS)
                    continue

            # 非限频错误不重复无意义重试
            break

    return None, last_error


def test_one(pro, ts_code: str, freq: str):
    print("\n" + "-" * 80)
    print(f"开始测试：ts_code={ts_code}, freq={freq}")
    print("-" * 80)

    df, error = call_rt_min_with_retry(pro, ts_code=ts_code, freq=freq)

    if error is not None:
        print("\n完整错误堆栈：")
        traceback.print_exception(type(error), error, error.__traceback__)
        return False

    if df is None:
        print("请求失败：返回 None。")
        return False

    print_df_preview(df)
    return not df.empty


def main():
    print("=" * 80)
    print("Tushare rt_min 实时分钟K线接口测试")
    print("=" * 80)
    print(f"项目根目录：{PROJECT_ROOT}")
    print(f"Token 前8位：{TUSHARE_TOKEN[:8]}******")
    print(f"HTTP URL：{TUSHARE_HTTP_URL}")
    print(f"正常请求间隔：{REQUEST_SLEEP_SECONDS} 秒")
    print(f"限频后等待：{RATE_LIMIT_SLEEP_SECONDS} 秒")
    print(f"最大重试次数：{MAX_RETRY}")
    print("=" * 80)

    pro = init_tushare_pro()

    total = 0
    success = 0

    for code_index, ts_code in enumerate(TEST_CODES, start=1):
        for freq_index, freq in enumerate(TEST_FREQS, start=1):
            total += 1

            ok = test_one(pro, ts_code=ts_code, freq=freq)

            if ok:
                success += 1

            # 最后一次请求后不用 sleep
            is_last = code_index == len(TEST_CODES) and freq_index == len(TEST_FREQS)
            if not is_last:
                print(f"\n等待 {REQUEST_SLEEP_SECONDS} 秒后继续下一次请求...")
                time.sleep(REQUEST_SLEEP_SECONDS)

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)
    print(f"成功：{success}/{total}")

    if success == total:
        print("结论：当前 Token/代理可以调用全部测试的 rt_min 实时分钟K线接口。")
    elif success > 0:
        print("结论：当前 Token/代理至少可以调用部分 rt_min 实时分钟K线接口。")
        print("如果失败原因是“请求次数过快”，请继续调大 REQUEST_SLEEP_SECONDS。")
    else:
        print("结论：当前 Token/代理暂未成功调用 rt_min。请检查权限、代理或接口频率限制。")


if __name__ == "__main__":
    main()
