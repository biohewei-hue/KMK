"""背离信号与趋势突破信号检测（用户重点关注项）。

- MACD/RSI 底背离与顶背离：在回看窗口内找最近两个价格枢轴低点/高点，
  价格创新低而指标未创新低 → 底背离（反之为顶背离）。
- 趋势突破：站上/跌破 MA20/MA60、突破N日新高/新低、MACD金叉死叉、放量。
"""

from .indicators import enrich


def _pivots(vals: list[float], is_low: bool, span: int = 3) -> list[int]:
    """局部极值点下标（前后 span 根K线内的最低/最高）。"""
    idx = []
    for i in range(span, len(vals) - span):
        window = vals[i - span : i + span + 1]
        if (is_low and vals[i] == min(window)) or (not is_low and vals[i] == max(window)):
            idx.append(i)
    return idx


def detect_divergence(kline: list[dict], lookback: int = 60) -> list[dict]:
    """返回背离信号列表 [{type, indicator, detail, dates}]。只报告最近仍有效的背离。"""
    if len(kline) < 40:
        return []
    ind = enrich(kline)
    n = len(kline)
    lo = max(0, n - lookback)
    signals = []

    for name, series in [("MACD-DIF", ind["dif"]), ("RSI", ind["rsi"])]:
        vals = [v if v is not None else 0.0 for v in series]

        # 底背离：最近两个价格低点，价格更低但指标更高
        lows = [i for i in _pivots([k["low"] for k in kline], True) if i >= lo]
        if len(lows) >= 2:
            i1, i2 = lows[-2], lows[-1]
            if kline[i2]["low"] < kline[i1]["low"] and vals[i2] > vals[i1] and n - i2 <= 10:
                signals.append(
                    {
                        "type": "底背离",
                        "indicator": name,
                        "detail": (
                            f"价格 {kline[i1]['low']:.2f}({kline[i1]['date']}) → "
                            f"{kline[i2]['low']:.2f}({kline[i2]['date']}) 创新低，"
                            f"{name} {vals[i1]:.2f} → {vals[i2]:.2f} 未创新低"
                        ),
                        "dates": [kline[i1]["date"], kline[i2]["date"]],
                    }
                )
        # 顶背离
        highs = [i for i in _pivots([k["high"] for k in kline], False) if i >= lo]
        if len(highs) >= 2:
            i1, i2 = highs[-2], highs[-1]
            if kline[i2]["high"] > kline[i1]["high"] and vals[i2] < vals[i1] and n - i2 <= 10:
                signals.append(
                    {
                        "type": "顶背离",
                        "indicator": name,
                        "detail": (
                            f"价格 {kline[i1]['high']:.2f}({kline[i1]['date']}) → "
                            f"{kline[i2]['high']:.2f}({kline[i2]['date']}) 创新高，"
                            f"{name} {vals[i1]:.2f} → {vals[i2]:.2f} 未创新高"
                        ),
                        "dates": [kline[i1]["date"], kline[i2]["date"]],
                    }
                )
    return signals


def detect_breakouts(kline: list[dict], windows=(20, 60), vol_ratio: float = 1.5) -> list[dict]:
    """最新一根K线上的趋势突破信号。"""
    if len(kline) < max(windows) + 2:
        return []
    ind = enrich(kline)
    i = len(kline) - 1
    today, prev = kline[i], kline[i - 1]
    signals = []

    for ma_name in ["ma20", "ma60"]:
        m, mp = ind[ma_name][i], ind[ma_name][i - 1]
        if m is None or mp is None:
            continue
        label = ma_name.upper().replace("MA", "MA")
        if prev["close"] < mp and today["close"] > m:
            signals.append({"type": "突破", "detail": f"收盘站上{label}（{m:.2f}）"})
        if prev["close"] > mp and today["close"] < m:
            signals.append({"type": "跌破", "detail": f"收盘跌破{label}（{m:.2f}）"})

    for w in windows:
        hh = max(k["high"] for k in kline[i - w : i])
        ll = min(k["low"] for k in kline[i - w : i])
        if today["close"] > hh:
            signals.append({"type": "突破", "detail": f"创{w}日新高（前高 {hh:.2f}）"})
        if today["close"] < ll:
            signals.append({"type": "跌破", "detail": f"创{w}日新低（前低 {ll:.2f}）"})

    if ind["dif"][i] > ind["dea"][i] and ind["dif"][i - 1] <= ind["dea"][i - 1]:
        pos = "零轴上方" if ind["dif"][i] > 0 else "零轴下方"
        signals.append({"type": "金叉", "detail": f"MACD金叉（{pos}）"})
    if ind["dif"][i] < ind["dea"][i] and ind["dif"][i - 1] >= ind["dea"][i - 1]:
        signals.append({"type": "死叉", "detail": "MACD死叉"})

    vols = [k["volume"] for k in kline]
    vol_ma5 = sum(vols[i - 5 : i]) / 5
    if vol_ma5 and today["volume"] > vol_ratio * vol_ma5:
        signals.append(
            {"type": "放量", "detail": f"成交量为5日均量的{today['volume'] / vol_ma5:.1f}倍"}
        )
    return signals


def index_snapshot(name: str, kline: list[dict], cfg: dict) -> dict:
    """单一指数的技术研判数据包：现价、均线位置、MACD/RSI状态、背离、突破。"""
    ind = enrich(kline)
    i = len(kline) - 1
    today = kline[i]
    pct = (today["close"] / kline[i - 1]["close"] - 1) * 100 if i > 0 else 0
    sig_cfg = cfg.get("signals", {})
    return {
        "name": name,
        "date": today["date"],
        "close": today["close"],
        "pct_chg": round(pct, 2),
        "ma": {k: (round(ind[k][i], 2) if ind[k][i] else None) for k in ["ma5", "ma10", "ma20", "ma60"]},
        "macd": {
            "dif": round(ind["dif"][i], 3),
            "dea": round(ind["dea"][i], 3),
            "hist": round(ind["hist"][i], 3),
            "hist_prev": round(ind["hist"][i - 1], 3),
        },
        "rsi14": round(ind["rsi"][i], 1) if ind["rsi"][i] else None,
        "kdj": {"k": round(ind["k"][i], 1), "d": round(ind["d"][i], 1), "j": round(ind["j"][i], 1)},
        "divergences": detect_divergence(kline, sig_cfg.get("divergence_lookback", 60)),
        "breakouts": detect_breakouts(
            kline,
            tuple(sig_cfg.get("breakout_windows", [20, 60])),
            sig_cfg.get("volume_spike_ratio", 1.5),
        ),
        "recent_20d": [
            {"date": k["date"], "close": k["close"], "volume": k["volume"]} for k in kline[-20:]
        ],
    }
