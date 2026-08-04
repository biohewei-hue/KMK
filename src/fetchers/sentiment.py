"""市场情绪指标（同花顺为主数据源）。

见底判断的核心依据：地量见地价、跌停家数收敛、连板高度回升。

- 连板高度/炸板率：同花顺涨停池与炸板池
- 两市成交额：上证+深证成指K线的成交额之和
- 涨跌家数：同花顺无稳定公开接口，缺失时明确标注，不编造
"""

from . import ths_market


def fetch_amount(cfg: dict) -> dict:
    """两市成交额（亿元）——地量是底部特征，需与历史分位对比。"""
    total, detail, errors = 0.0, {}, []
    hist = []
    for idx in cfg.get("amount_indexes", []):
        try:
            kl = ths_market.fetch_kline(idx["ths_code"], 60)
            if not kl:
                errors.append(f"{idx['name']}: K线为空")
                continue
            amt = kl[-1]["amount"] / 1e8
            total += amt
            detail[idx["name"]] = round(amt, 0)
            hist.append([k["amount"] / 1e8 for k in kl])
        except Exception as e:  # noqa: BLE001
            errors.append(f"{idx['name']}: {str(e)[:80]}")

    out = {"amount_yi": round(total, 0), "detail": detail}
    if hist and all(len(h) >= 40 for h in hist):
        # 两市合计的近60日分位，用于判断是否接近地量
        combined = [sum(x) for x in zip(*hist)]
        below = sum(1 for v in combined if v < total)
        out["amount_pctile_60d"] = round(below / len(combined) * 100, 0)
    if errors:
        out["errors"] = errors
    return out


def fetch_all(cfg: dict, date_str: str = "", creds: dict | None = None) -> dict:
    out: dict = {"errors": []}

    amt = fetch_amount(cfg)
    out["amount"] = amt
    out["errors"] += amt.pop("errors", [])

    if date_str:
        lp = ths_market.fetch_limit_pool(date_str, creds)
        out["limit_pool"] = lp
        if lp.get("error"):
            out["errors"].append(lp["error"])

    out["breadth"] = {"note": "涨跌家数无稳定公开接口，暂缺"}
    return out
