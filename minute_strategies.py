from __future__ import annotations

import pandas as pd

from .base_strategy import BaseMinuteStrategy


def prepare_minute_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算分钟级B点所需指标。

    这里单独放到策略模块，避免 minute_strategy.py 里既放数据获取又放策略判断。
    后续无论分钟数据来自 BaoStock、Tushare stk_mins、rt_min，还是实时快照合成，
    只要字段统一为：开盘、最高、最低、收盘、成交量、成交额，就可以复用这里的策略。
    """

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime"])
    df = df.sort_values("datetime")

    for col in ["开盘", "最高", "最低", "收盘", "成交量", "成交额"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["MA5"] = df["收盘"].rolling(5).mean()
    df["MA10"] = df["收盘"].rolling(10).mean()
    df["MA20"] = df["收盘"].rolling(20).mean()
    df["VOL20"] = df["成交量"].shift(1).rolling(20).mean()

    df["前12根最高"] = df["最高"].shift(1).rolling(12).max()
    df["前12根最低"] = df["最低"].shift(1).rolling(12).min()
    df["前12根振幅"] = df["前12根最高"] / df["前12根最低"] - 1

    return df


def check_30m_structure(df30: pd.DataFrame) -> tuple[bool, str]:
    """
    30分钟结构过滤：判断盘中是否具备基本趋势结构。
    这是分钟B点策略前的公共过滤，不算某一个具体B点。
    """

    df = prepare_minute_data(df30)

    if len(df) < 25:
        return False, "30分钟K线不足"

    latest = df.iloc[-1]

    if pd.isna(latest[["MA5", "MA10", "VOL20"]]).any():
        return False, "30分钟指标不足"

    cond_ma = latest["收盘"] > latest["MA5"] and latest["MA5"] >= latest["MA10"]
    cond_vol = latest["成交量"] >= latest["VOL20"] * 0.8 if latest["VOL20"] > 0 else False

    if cond_ma and cond_vol:
        return True, "30分钟趋势结构有效"

    return False, "30分钟结构未确认"


class PullbackStartMinuteStrategy(BaseMinuteStrategy):
    """
    5分钟B点1：回踩均线后重新启动。
    适合日线主升趋势类股票。
    """

    name = "5分钟回踩均线启动"
    support_groups = ("主升趋势类",)

    def match(self, row: pd.Series, df5: pd.DataFrame, df30: pd.DataFrame) -> bool:
        df = prepare_minute_data(df5)

        if len(df) < 30:
            return False

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        if pd.isna(latest[["MA5", "MA10", "MA20", "VOL20"]]).any():
            return False

        trend_ok = latest["MA5"] > latest["MA10"] > latest["MA20"]
        pullback_ok = (
            prev["最低"] <= prev["MA10"] * 1.01
            or prev["最低"] <= prev["MA20"] * 1.01
        )
        restart_ok = latest["收盘"] > latest["MA5"] and latest["收盘"] > prev["最高"]
        volume_ok = latest["成交量"] > latest["VOL20"] * 1.10 if latest["VOL20"] > 0 else False

        return bool(trend_ok and pullback_ok and restart_ok and volume_ok)


class PlatformBreakoutMinuteStrategy(BaseMinuteStrategy):
    """
    5分钟B点2：平台突破确认。
    适合箱体突破、放量启动类股票。
    也作为“其他”分组的保底确认策略。
    """

    name = "5分钟平台突破确认"
    support_groups = ("突破类", "其他")

    def support(self, daily_group: str) -> bool:
        daily_group = "" if daily_group is None else str(daily_group)
        return "突破类" in daily_group or daily_group == "其他"

    def match(self, row: pd.Series, df5: pd.DataFrame, df30: pd.DataFrame) -> bool:
        df = prepare_minute_data(df5)

        if len(df) < 30:
            return False

        latest = df.iloc[-1]

        if pd.isna(latest[["前12根最高", "前12根最低", "前12根振幅", "VOL20"]]).any():
            return False

        range_ok = latest["前12根振幅"] <= 0.04
        breakout_ok = latest["收盘"] > latest["前12根最高"]
        volume_ok = latest["成交量"] > latest["VOL20"] * 1.20 if latest["VOL20"] > 0 else False

        return bool(range_ok and breakout_ok and volume_ok)


class VolumeReversalMinuteStrategy(BaseMinuteStrategy):
    """
    5分钟B点3：放量反包确认。
    适合低位放量启动类股票。
    """

    name = "5分钟放量反包确认"
    support_groups = ("放量启动类",)

    def match(self, row: pd.Series, df5: pd.DataFrame, df30: pd.DataFrame) -> bool:
        df = prepare_minute_data(df5)

        if len(df) < 30:
            return False

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        if pd.isna(latest[["MA5", "MA10", "VOL20"]]).any():
            return False

        intrabar_pct = latest["收盘"] / latest["开盘"] - 1 if latest["开盘"] > 0 else 0
        reverse_ok = latest["收盘"] > latest["MA5"] and latest["收盘"] > prev["最高"] and intrabar_pct >= 0.005
        volume_ok = latest["成交量"] > latest["VOL20"] * 1.30 if latest["VOL20"] > 0 else False

        return bool(reverse_ok and volume_ok)


class OneMinuteBuyStrategy(BaseMinuteStrategy):
    """
    1分钟精确买点确认。

    注意：
    - 这个策略不是替代 30分钟 / 5分钟策略；
    - 30分钟趋势过滤在 registry.evaluate_minute_strategies() 中统一执行；
    - 5分钟结构 / 缠论B点也在 registry 中先执行；
    - 本策略只负责最后一层 1分钟入场确认。
    """

    name = "1分钟精确买点"
    support_groups = ("主升趋势类", "突破类", "放量启动类", "其他")

    def support(self, daily_group: str) -> bool:
        # 1分钟确认策略对所有已经通过 30分钟和5分钟结构的候选开放
        return True

    def match(self, row: pd.Series, df1: pd.DataFrame, df5: pd.DataFrame, df30: pd.DataFrame) -> bool:
        df1 = prepare_minute_data(df1)
        df5 = prepare_minute_data(df5)

        if len(df1) < 30 or len(df5) < 20:
            return False

        latest1 = df1.iloc[-1]
        prev1 = df1.iloc[-2]
        latest5 = df5.iloc[-1]

        if pd.isna(latest1[["MA5", "MA10", "MA20", "VOL20"]]).any():
            return False

        if pd.isna(latest5[["MA5", "MA10", "MA20"]]).any():
            return False

        # 1分钟短线重新转强
        one_min_trend_ok = (
            latest1["收盘"] > latest1["MA5"]
            and latest1["MA5"] >= latest1["MA10"] * 0.998
        )

        # 1分钟突破上一根高点，避免只是横盘
        one_min_restart_ok = latest1["收盘"] > prev1["最高"]

        # 不能离5分钟MA5太远，避免追高
        not_too_far_from_5m_ma5 = (
            latest5["MA5"] > 0
            and latest1["收盘"] <= latest5["MA5"] * 1.035
        )

        # 1分钟量能温和放大
        volume_ok = (
            latest1["VOL20"] > 0
            and latest1["成交量"] >= latest1["VOL20"] * 1.05
        )

        return bool(
            one_min_trend_ok
            and one_min_restart_ok
            and not_too_far_from_5m_ma5
            and volume_ok
        )
