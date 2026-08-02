"""纯 Python 技术指标：MA / EMA / MACD / RSI / KDJ。输入为 fetch_kline 的输出。"""


def ma(values: list[float], n: int) -> list[float | None]:
    out = [None] * len(values)
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= n:
            s -= values[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def ema(values: list[float], n: int) -> list[float]:
    out = []
    k = 2 / (n + 1)
    prev = values[0]
    for v in values:
        prev = v * k + prev * (1 - k)
        out.append(prev)
    return out


def macd(closes: list[float], fast=12, slow=26, sig=9):
    """返回 (dif, dea, hist)。hist=2*(dif-dea) 即国内软件的 MACD 红绿柱。"""
    ef, es = ema(closes, fast), ema(closes, slow)
    dif = [a - b for a, b in zip(ef, es)]
    dea = ema(dif, sig)
    hist = [2 * (a - b) for a, b in zip(dif, dea)]
    return dif, dea, hist


def rsi(closes: list[float], n=14) -> list[float | None]:
    out = [None] * len(closes)
    gain = loss = 0.0
    for i in range(1, len(closes)):
        chg = closes[i] - closes[i - 1]
        g, l = max(chg, 0), max(-chg, 0)
        if i <= n:
            gain += g
            loss += l
            if i == n:
                avg_g, avg_l = gain / n, loss / n
                out[i] = 100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
        else:
            avg_g = (avg_g * (n - 1) + g) / n
            avg_l = (avg_l * (n - 1) + l) / n
            out[i] = 100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
    return out


def kdj(kline: list[dict], n=9):
    k_list, d_list, j_list = [], [], []
    k = d = 50.0
    for i in range(len(kline)):
        lo = min(x["low"] for x in kline[max(0, i - n + 1) : i + 1])
        hi = max(x["high"] for x in kline[max(0, i - n + 1) : i + 1])
        rsv = 50.0 if hi == lo else (kline[i]["close"] - lo) / (hi - lo) * 100
        k = 2 / 3 * k + 1 / 3 * rsv
        d = 2 / 3 * d + 1 / 3 * k
        k_list.append(k)
        d_list.append(d)
        j_list.append(3 * k - 2 * d)
    return k_list, d_list, j_list


def enrich(kline: list[dict]) -> dict:
    """计算全套指标，返回 {closes, ma5/10/20/60, dif, dea, hist, rsi, k, d, j}"""
    closes = [x["close"] for x in kline]
    dif, dea, hist = macd(closes)
    k, d, j = kdj(kline)
    return {
        "kline": kline,
        "closes": closes,
        "ma5": ma(closes, 5),
        "ma10": ma(closes, 10),
        "ma20": ma(closes, 20),
        "ma60": ma(closes, 60),
        "dif": dif,
        "dea": dea,
        "hist": hist,
        "rsi": rsi(closes),
        "k": k,
        "d": d,
        "j": j,
    }
