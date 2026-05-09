# config.py

import os

# =========================
# Tushare 配置
# =========================
# 为了避免把 Token 上传到 GitHub，优先读取环境变量 TUSHARE_TOKEN。
# 如果你只是本地测试，也可以把下面的“这里填你的token”替换成自己的 token。
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "W5yA7cE9gI1kM3oQ5sU7wY9aC1eG3iK5mO7qS9uW1yA3cE5gI7kM9oQ1sU3wY5aC7eG9iK1mO3qS")

# 你购买的 Tushare 代理地址
TUSHARE_HTTP_URL = os.getenv("TUSHARE_HTTP_URL", "http://47.92.128.69:35721/dataapi")

# =========================
# 基础股票池筛选条件
# =========================
# 市值范围，单位：亿元
MIN_MARKET_VALUE = 100
MAX_MARKET_VALUE = 1500

# 排除行业关键词
EXCLUDE_INDUSTRIES = [
    "银行",
    "证券",
    "券商",
    "保险",
    "信托",
    "房地产",
    "地产",
    "钢铁",
    "煤炭",
    "煤炭开采",
    "铁路运输",
    "航运",
    "水运",
    "港口",
]

# 导出路径
OUTPUT_FILE = "output/a_stock_selected.xlsx"
