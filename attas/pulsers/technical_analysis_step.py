"""
Technical Analysis pipeline step for the Pulsers area.

Attas layers finance-oriented pulse definitions, validation rules, and personal-agent
workflows on top of the shared runtimes. Within Attas, these modules define finance-
oriented pulse providers and transformation steps.

It mainly publishes constants such as `EFFECTIVE_INPUT` that are consumed elsewhere in
the codebase.
"""

# Shared technical-analysis calculator for PathPulser pulse definitions.

def _is_blank(value):
    """Return whether the value is a blank."""
    if value in (None, ""):
        return True
    if isinstance(value, (list, dict, tuple, set)) and not value:
        return True
    return False


def _effective_input():
    """Internal helper for effective input."""
    merged = {}
    if isinstance(previous_output, dict):
        for key, value in previous_output.items():
            if str(key).startswith("_"):
                continue
            if not _is_blank(value):
                merged[str(key)] = value
    if isinstance(input_data, dict):
        for key, value in input_data.items():
            if not _is_blank(value) or str(key) not in merged:
                merged[str(key)] = value
    if merged.get("timestamp") in (None, "") and merged.get("end_date") not in (None, ""):
        merged["timestamp"] = merged.get("end_date")
    return merged


EFFECTIVE_INPUT = _effective_input()


def _param(name, fallback=None):
    """Internal helper for param."""
    value = EFFECTIVE_INPUT.get(name)
    if value not in (None, ""):
        return value
    schema = (((pulse.get("input_schema") or {}).get("properties") or {}).get(name) or {})
    if "default" in schema:
        return schema.get("default")
    return fallback


def _param_int(name, fallback=None):
    """Internal helper for param int."""
    value = _param(name, fallback)
    if value in (None, ""):
        raise ValueError(f"Missing required integer parameter: {name}")
    try:
        return int(value)
    except Exception:
        return int(float(value))


def _param_float(name, fallback=None):
    """Internal helper for param float."""
    value = _param(name, fallback)
    if value in (None, ""):
        raise ValueError(f"Missing required numeric parameter: {name}")
    return float(value)


def _number(value, default=0.0):
    """Internal helper for number."""
    if value in (None, ""):
        return float(default)
    return float(value)


def _ensure(condition, message):
    """Internal helper to ensure the value exists."""
    if not condition:
        raise ValueError(message)


def _safe_ratio(numerator, denominator, when_zero=0.0):
    """Internal helper for safe ratio."""
    if denominator == 0:
        return float(when_zero)
    return float(numerator) / float(denominator)


def _normalize_bars():
    """Internal helper to normalize the bars."""
    raw_bars = EFFECTIVE_INPUT.get("ohlc_series") or []
    _ensure(isinstance(raw_bars, list) and raw_bars, "ohlc_series must be a non-empty array.")

    normalized = []
    for raw in raw_bars:
        if not isinstance(raw, dict):
            continue
        timestamp = raw.get("timestamp")
        if timestamp in (None, ""):
            continue
        normalized.append(
            {
                "timestamp": str(timestamp),
                "open": _number(raw.get("open")),
                "high": _number(raw.get("high")),
                "low": _number(raw.get("low")),
                "close": _number(raw.get("close")),
                "volume": _number(raw.get("volume"), 0.0),
            }
        )

    _ensure(normalized, "ohlc_series must contain at least one valid OHLC bar.")
    normalized = sorted(normalized, key=lambda bar: bar["timestamp"])

    target_timestamp = EFFECTIVE_INPUT.get("timestamp")
    if target_timestamp not in (None, ""):
        target_timestamp = str(target_timestamp)
        filtered = [bar for bar in normalized if bar["timestamp"] <= target_timestamp]
        _ensure(filtered, "No OHLC bars are available at or before the requested timestamp.")
        return filtered

    return normalized


def _price_value(bar, field):
    """Internal helper to return the price value."""
    selected = str(field or "close")
    if selected == "open":
        return bar["open"]
    if selected == "high":
        return bar["high"]
    if selected == "low":
        return bar["low"]
    if selected == "close":
        return bar["close"]
    if selected == "hl2":
        return (bar["high"] + bar["low"]) / 2.0
    if selected in ("hlc3", "typical_price"):
        return (bar["high"] + bar["low"] + bar["close"]) / 3.0
    if selected == "ohlc4":
        return (bar["open"] + bar["high"] + bar["low"] + bar["close"]) / 4.0
    raise ValueError(f"Unsupported price_field: {selected}")


def _price_series(bars, field):
    """Internal helper for price series."""
    return [_price_value(bar, field) for bar in bars]


def _closes(bars):
    """Internal helper for closes."""
    return [bar["close"] for bar in bars]


def _highs(bars):
    """Internal helper for highs."""
    return [bar["high"] for bar in bars]


def _lows(bars):
    """Internal helper for lows."""
    return [bar["low"] for bar in bars]


def _volumes(bars):
    """Internal helper for volumes."""
    return [bar["volume"] for bar in bars]


def _last_window(values, window, label):
    """Internal helper for last window."""
    _ensure(window > 0, f"{label} must be greater than 0.")
    _ensure(len(values) >= window, f"{label} requires at least {window} observations.")
    return values[-window:]


def _sma_series(values, window):
    """Internal helper for sma series."""
    window_values = _last_window(values, window, "SMA")
    if len(values) == window:
        return [sum(window_values) / float(window)]
    series = []
    rolling_sum = sum(values[:window])
    series.append(rolling_sum / float(window))
    for index in range(window, len(values)):
        rolling_sum += values[index] - values[index - window]
        series.append(rolling_sum / float(window))
    return series


def _ema_series(values, window):
    """Internal helper for ema series."""
    _ensure(window > 0, "EMA window must be greater than 0.")
    _ensure(len(values) >= window, f"EMA requires at least {window} observations.")
    multiplier = 2.0 / (float(window) + 1.0)
    current = sum(values[:window]) / float(window)
    series = [current]
    for value in values[window:]:
        current = ((float(value) - current) * multiplier) + current
        series.append(current)
    return series


def _wma_series(values, window):
    """Internal helper for wma series."""
    _ensure(window > 0, "WMA window must be greater than 0.")
    _ensure(len(values) >= window, f"WMA requires at least {window} observations.")
    weights = list(range(1, window + 1))
    weight_sum = float(sum(weights))
    series = []
    for index in range(window - 1, len(values)):
        segment = values[index - window + 1 : index + 1]
        series.append(sum(value * weight for value, weight in zip(segment, weights)) / weight_sum)
    return series


def _wilder_average_series(values, window):
    """Internal helper for wilder average series."""
    _ensure(window > 0, "Wilder window must be greater than 0.")
    _ensure(len(values) >= window, f"Wilder smoothing requires at least {window} observations.")
    current = sum(values[:window]) / float(window)
    series = [current]
    for value in values[window:]:
        current = ((current * float(window - 1)) + float(value)) / float(window)
        series.append(current)
    return series


def _stddev(values):
    """Internal helper for stddev."""
    _ensure(values, "Standard deviation requires at least one observation.")
    mean = sum(values) / float(len(values))
    variance = sum((value - mean) ** 2 for value in values) / float(len(values))
    return variance ** 0.5


def _rsi_series(values, window):
    """Internal helper for rsi series."""
    _ensure(window > 0, "RSI window must be greater than 0.")
    _ensure(len(values) >= window + 1, f"RSI requires at least {window + 1} observations.")
    changes = [values[index] - values[index - 1] for index in range(1, len(values))]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]

    average_gain = sum(gains[:window]) / float(window)
    average_loss = sum(losses[:window]) / float(window)

    series = []
    if average_loss == 0:
        series.append(100.0 if average_gain > 0 else 0.0)
    else:
        rs = average_gain / average_loss
        series.append(100.0 - (100.0 / (1.0 + rs)))

    for index in range(window, len(changes)):
        average_gain = ((average_gain * float(window - 1)) + gains[index]) / float(window)
        average_loss = ((average_loss * float(window - 1)) + losses[index]) / float(window)
        if average_loss == 0:
            series.append(100.0 if average_gain > 0 else 0.0)
        else:
            rs = average_gain / average_loss
            series.append(100.0 - (100.0 / (1.0 + rs)))
    return series


def _true_range_values(bars, include_first=True):
    """Internal helper to return the true range values."""
    _ensure(len(bars) >= 1, "True range requires at least one bar.")
    values = []
    if include_first:
        first = bars[0]
        values.append(first["high"] - first["low"])
    for index in range(1, len(bars)):
        current = bars[index]
        previous = bars[index - 1]
        values.append(
            max(
                current["high"] - current["low"],
                abs(current["high"] - previous["close"]),
                abs(current["low"] - previous["close"]),
            )
        )
    return values


def _directional_components(bars):
    """Internal helper for directional components."""
    _ensure(len(bars) >= 2, "Directional indicators require at least two bars.")
    true_ranges = []
    plus_dms = []
    minus_dms = []
    vortex_plus = []
    vortex_minus = []
    buying_pressure = []
    ultimate_tr = []
    for index in range(1, len(bars)):
        current = bars[index]
        previous = bars[index - 1]

        up_move = current["high"] - previous["high"]
        down_move = previous["low"] - current["low"]
        plus_dms.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dms.append(down_move if down_move > up_move and down_move > 0 else 0.0)

        tr = max(
            current["high"] - current["low"],
            abs(current["high"] - previous["close"]),
            abs(current["low"] - previous["close"]),
        )
        true_ranges.append(tr)

        vortex_plus.append(abs(current["high"] - previous["low"]))
        vortex_minus.append(abs(current["low"] - previous["high"]))

        buying_pressure.append(current["close"] - min(current["low"], previous["close"]))
        ultimate_tr.append(max(current["high"], previous["close"]) - min(current["low"], previous["close"]))

    return true_ranges, plus_dms, minus_dms, vortex_plus, vortex_minus, buying_pressure, ultimate_tr


def _money_flow_multiplier(bar):
    """Internal helper for money flow multiplier."""
    spread = bar["high"] - bar["low"]
    if spread == 0:
        return 0.0
    return ((bar["close"] - bar["low"]) - (bar["high"] - bar["close"])) / spread


def _adl_series(bars, start_value):
    """Internal helper for adl series."""
    total = float(start_value)
    series = []
    for bar in bars:
        total += _money_flow_multiplier(bar) * bar["volume"]
        series.append(total)
    return series


def _obv_series(bars, start_value):
    """Internal helper for obv series."""
    _ensure(len(bars) >= 1, "OBV requires at least one bar.")
    total = float(start_value)
    series = [total]
    for index in range(1, len(bars)):
        current_close = bars[index]["close"]
        previous_close = bars[index - 1]["close"]
        if current_close > previous_close:
            total += bars[index]["volume"]
        elif current_close < previous_close:
            total -= bars[index]["volume"]
        series.append(total)
    return series


def _last_index_of_max(values):
    """Internal helper for last index of max."""
    best_index = 0
    best_value = values[0]
    for index, value in enumerate(values):
        if value >= best_value:
            best_value = value
            best_index = index
    return best_index


def _last_index_of_min(values):
    """Internal helper for last index of min."""
    best_index = 0
    best_value = values[0]
    for index, value in enumerate(values):
        if value <= best_value:
            best_value = value
            best_index = index
    return best_index


def _macd_line_series(values, fast_window, slow_window):
    """Internal helper for macd line series."""
    fast_series = _ema_series(values, fast_window)
    slow_series = _ema_series(values, slow_window)
    aligned_fast = fast_series[-len(slow_series) :]
    return [fast - slow for fast, slow in zip(aligned_fast, slow_series)]


def _ppo_series(values, fast_window, slow_window):
    """Internal helper for ppo series."""
    fast_series = _ema_series(values, fast_window)
    slow_series = _ema_series(values, slow_window)
    aligned_fast = fast_series[-len(slow_series) :]
    return [100.0 * _safe_ratio(fast - slow, slow, 0.0) for fast, slow in zip(aligned_fast, slow_series)]


def _dmi_series(bars, window):
    """Internal helper for dmi series."""
    true_ranges, plus_dms, minus_dms, _vp, _vm, _bp, _utr = _directional_components(bars)
    tr_average = _wilder_average_series(true_ranges, window)
    plus_average = _wilder_average_series(plus_dms, window)
    minus_average = _wilder_average_series(minus_dms, window)
    plus_di = []
    minus_di = []
    dx = []
    for tr_value, plus_value, minus_value in zip(tr_average, plus_average, minus_average):
        plus_current = 100.0 * _safe_ratio(plus_value, tr_value, 0.0)
        minus_current = 100.0 * _safe_ratio(minus_value, tr_value, 0.0)
        plus_di.append(plus_current)
        minus_di.append(minus_current)
        denominator = plus_current + minus_current
        dx.append(100.0 * _safe_ratio(abs(plus_current - minus_current), denominator, 0.0))
    return plus_di, minus_di, dx


def _pack_series(bars, start_index, values):
    """Internal helper for pack series."""
    _ensure(isinstance(values, list) and values, "Indicator produced no time-series values.")
    _ensure(start_index >= 0, "Indicator start index must be non-negative.")
    _ensure(start_index + len(values) <= len(bars), "Indicator series is longer than the available OHLC bars.")

    points = []
    for offset, value in enumerate(values):
        numeric_value = float(value)
        _ensure(math.isfinite(numeric_value), "Computed indicator value must be finite.")
        points.append(
            {
                "timestamp": bars[start_index + offset]["timestamp"],
                "value": numeric_value,
            }
        )
    return {"values": points}


def _compute_indicator():
    """Internal helper for compute indicator."""
    bars = _normalize_bars()
    pulse_name = str(pulse.get("name") or pulse.get("pulse_name") or "").strip()
    _ensure(pulse_name, "Pulse name is required.")

    price_field = str(_param("price_field", "close") or "close")
    prices = _price_series(bars, price_field)
    closes = _closes(bars)
    highs = _highs(bars)
    lows = _lows(bars)
    volumes = _volumes(bars)

    if pulse_name == "sma":
        window = _param_int("window")
        return _pack_series(bars, window - 1, _sma_series(prices, window))

    if pulse_name == "ema":
        window = _param_int("window")
        return _pack_series(bars, window - 1, _ema_series(prices, window))

    if pulse_name == "wma":
        window = _param_int("window")
        return _pack_series(bars, window - 1, _wma_series(prices, window))

    if pulse_name == "dema":
        window = _param_int("window")
        ema_one = _ema_series(prices, window)
        ema_two = _ema_series(ema_one, window)
        dema_values = [(2.0 * fast) - slow for fast, slow in zip(ema_one[-len(ema_two) :], ema_two)]
        return _pack_series(bars, (2 * window) - 2, dema_values)

    if pulse_name == "tema":
        window = _param_int("window")
        ema_one = _ema_series(prices, window)
        ema_two = _ema_series(ema_one, window)
        ema_three = _ema_series(ema_two, window)
        tema_values = [
            (3.0 * ema_a) - (3.0 * ema_b) + ema_c
            for ema_a, ema_b, ema_c in zip(ema_one[-len(ema_three) :], ema_two[-len(ema_three) :], ema_three)
        ]
        return _pack_series(bars, (3 * window) - 3, tema_values)

    if pulse_name == "trima":
        window = _param_int("window")
        first_window = int(math.ceil((float(window) + 1.0) / 2.0))
        second_window = int(math.floor((float(window) + 1.0) / 2.0))
        first = _sma_series(prices, first_window)
        second = _sma_series(first, second_window)
        return _pack_series(bars, window - 1, second)

    if pulse_name == "kama":
        window = _param_int("window")
        fast_window = _param_int("fast_window")
        slow_window = _param_int("slow_window")
        _ensure(len(prices) >= window + 1, f"KAMA requires at least {window + 1} observations.")
        fastest = 2.0 / (float(fast_window) + 1.0)
        slowest = 2.0 / (float(slow_window) + 1.0)
        kama = sum(prices[:window]) / float(window)
        kama_values = [kama]
        for index in range(window, len(prices)):
            change = abs(prices[index] - prices[index - window])
            volatility = sum(abs(prices[offset] - prices[offset - 1]) for offset in range(index - window + 1, index + 1))
            efficiency_ratio = _safe_ratio(change, volatility, 0.0)
            smoothing_constant = (efficiency_ratio * (fastest - slowest) + slowest) ** 2
            kama = kama + (smoothing_constant * (prices[index] - kama))
            kama_values.append(kama)
        return _pack_series(bars, window - 1, kama_values)

    if pulse_name == "zlema":
        window = _param_int("window")
        lag = max(1, int((window - 1) / 2))
        adjusted = []
        for index, value in enumerate(prices):
            lagged = prices[index - lag] if index - lag >= 0 else prices[0]
            adjusted.append(value + (value - lagged))
        return _pack_series(bars, window - 1, _ema_series(adjusted, window))

    if pulse_name == "hma":
        window = _param_int("window")
        half_window = max(1, int(window / 2))
        sqrt_window = max(1, int(math.sqrt(float(window))))
        wma_half = _wma_series(prices, half_window)
        wma_full = _wma_series(prices, window)
        aligned_half = wma_half[-len(wma_full) :]
        transformed = [(2.0 * half) - full for half, full in zip(aligned_half, wma_full)]
        hma_values = _wma_series(transformed, sqrt_window)
        return _pack_series(bars, (window - 1) + (sqrt_window - 1), hma_values)

    if pulse_name == "t3":
        window = _param_int("window")
        vfactor = _param_float("vfactor")
        ema_one = _ema_series(prices, window)
        ema_two = _ema_series(ema_one, window)
        ema_three = _ema_series(ema_two, window)
        ema_four = _ema_series(ema_three, window)
        ema_five = _ema_series(ema_four, window)
        ema_six = _ema_series(ema_five, window)
        c1 = -(vfactor ** 3)
        c2 = (3.0 * (vfactor ** 2)) + (3.0 * (vfactor ** 3))
        c3 = (-6.0 * (vfactor ** 2)) - (3.0 * vfactor) - (3.0 * (vfactor ** 3))
        c4 = 1.0 + (3.0 * vfactor) + (3.0 * (vfactor ** 2)) + (vfactor ** 3)
        t3_values = [
            (c1 * ema_f) + (c2 * ema_e) + (c3 * ema_d) + (c4 * ema_c)
            for ema_c, ema_d, ema_e, ema_f in zip(
                ema_three[-len(ema_six) :],
                ema_four[-len(ema_six) :],
                ema_five[-len(ema_six) :],
                ema_six,
            )
        ]
        return _pack_series(bars, (6 * window) - 6, t3_values)

    if pulse_name == "vwma":
        window = _param_int("window")
        vwma_values = []
        for index in range(window - 1, len(prices)):
            trailing_prices = prices[index - window + 1 : index + 1]
            trailing_volumes = volumes[index - window + 1 : index + 1]
            weighted_sum = sum(price * volume for price, volume in zip(trailing_prices, trailing_volumes))
            vwma_values.append(_safe_ratio(weighted_sum, sum(trailing_volumes), 0.0))
        return _pack_series(bars, window - 1, vwma_values)

    if pulse_name == "midpoint":
        window = _param_int("window")
        midpoint_values = []
        for index in range(window - 1, len(prices)):
            trailing = prices[index - window + 1 : index + 1]
            midpoint_values.append((max(trailing) + min(trailing)) / 2.0)
        return _pack_series(bars, window - 1, midpoint_values)

    if pulse_name == "midprice":
        window = _param_int("window")
        midprice_values = []
        for index in range(window - 1, len(bars)):
            trailing_highs = highs[index - window + 1 : index + 1]
            trailing_lows = lows[index - window + 1 : index + 1]
            midprice_values.append((max(trailing_highs) + min(trailing_lows)) / 2.0)
        return _pack_series(bars, window - 1, midprice_values)

    if pulse_name == "rsi":
        window = _param_int("window")
        return _pack_series(bars, window, _rsi_series(prices, window))

    if pulse_name == "stochastic_k":
        k_window = _param_int("k_window")
        smooth_window = _param_int("smooth_window", 1)
        raw_series = []
        for index in range(k_window - 1, len(bars)):
            window_high = max(highs[index - k_window + 1 : index + 1])
            window_low = min(lows[index - k_window + 1 : index + 1])
            denominator = window_high - window_low
            raw_series.append(100.0 * _safe_ratio(closes[index] - window_low, denominator, 0.0))
        if smooth_window <= 1:
            return _pack_series(bars, k_window - 1, raw_series)
        smoothed_series = _sma_series(raw_series, smooth_window)
        return _pack_series(bars, (k_window - 1) + (smooth_window - 1), smoothed_series)

    if pulse_name == "stochastic_d":
        k_window = _param_int("k_window")
        k_smoothing = _param_int("k_smoothing")
        d_window = _param_int("d_window")
        raw_series = []
        for index in range(k_window - 1, len(bars)):
            window_high = max(highs[index - k_window + 1 : index + 1])
            window_low = min(lows[index - k_window + 1 : index + 1])
            denominator = window_high - window_low
            raw_series.append(100.0 * _safe_ratio(closes[index] - window_low, denominator, 0.0))
        raw_start = k_window - 1
        smoothed_k = raw_series if k_smoothing <= 1 else _sma_series(raw_series, k_smoothing)
        smoothed_start = raw_start if k_smoothing <= 1 else raw_start + k_smoothing - 1
        signal_series = _sma_series(smoothed_k, d_window)
        return _pack_series(bars, smoothed_start + d_window - 1, signal_series)

    if pulse_name == "williams_r":
        window = _param_int("window")
        values = []
        for index in range(window - 1, len(bars)):
            trailing_highs = highs[index - window + 1 : index + 1]
            trailing_lows = lows[index - window + 1 : index + 1]
            highest = max(trailing_highs)
            lowest = min(trailing_lows)
            values.append(-100.0 * _safe_ratio(highest - closes[index], highest - lowest, 0.0))
        return _pack_series(bars, window - 1, values)

    if pulse_name == "cci":
        window = _param_int("window")
        constant = _param_float("constant")
        typical = _price_series(bars, price_field)
        cci_values = []
        for index in range(window - 1, len(typical)):
            trailing = typical[index - window + 1 : index + 1]
            mean = sum(trailing) / float(window)
            mean_deviation = sum(abs(value - mean) for value in trailing) / float(window)
            cci_values.append(_safe_ratio(trailing[-1] - mean, constant * mean_deviation, 0.0))
        return _pack_series(bars, window - 1, cci_values)

    if pulse_name == "roc":
        window = _param_int("window")
        _ensure(len(prices) >= window + 1, f"ROC requires at least {window + 1} observations.")
        roc_values = []
        for index in range(window, len(prices)):
            baseline = prices[index - window]
            roc_values.append(100.0 * _safe_ratio(prices[index] - baseline, baseline, 0.0))
        return _pack_series(bars, window, roc_values)

    if pulse_name == "momentum":
        window = _param_int("window")
        _ensure(len(prices) >= window + 1, f"Momentum requires at least {window + 1} observations.")
        momentum_values = [prices[index] - prices[index - window] for index in range(window, len(prices))]
        return _pack_series(bars, window, momentum_values)

    if pulse_name == "trix":
        window = _param_int("window")
        ema_one = _ema_series(prices, window)
        ema_two = _ema_series(ema_one, window)
        ema_three = _ema_series(ema_two, window)
        _ensure(len(ema_three) >= 2, "TRIX requires enough data for two triple-smoothed EMA values.")
        trix_values = [
            100.0 * _safe_ratio(ema_three[index] - ema_three[index - 1], ema_three[index - 1], 0.0)
            for index in range(1, len(ema_three))
        ]
        return _pack_series(bars, (3 * window) - 2, trix_values)

    if pulse_name == "macd_line":
        fast_window = _param_int("fast_window")
        slow_window = _param_int("slow_window")
        return _pack_series(bars, slow_window - 1, _macd_line_series(prices, fast_window, slow_window))

    if pulse_name == "macd_signal":
        fast_window = _param_int("fast_window")
        slow_window = _param_int("slow_window")
        signal_window = _param_int("signal_window")
        macd_line = _macd_line_series(prices, fast_window, slow_window)
        signal_values = _ema_series(macd_line, signal_window)
        return _pack_series(bars, slow_window + signal_window - 2, signal_values)

    if pulse_name == "macd_histogram":
        fast_window = _param_int("fast_window")
        slow_window = _param_int("slow_window")
        signal_window = _param_int("signal_window")
        macd_line = _macd_line_series(prices, fast_window, slow_window)
        signal_values = _ema_series(macd_line, signal_window)
        histogram_values = [macd - signal for macd, signal in zip(macd_line[-len(signal_values) :], signal_values)]
        return _pack_series(bars, slow_window + signal_window - 2, histogram_values)

    if pulse_name == "ppo":
        fast_window = _param_int("fast_window")
        slow_window = _param_int("slow_window")
        return _pack_series(bars, slow_window - 1, _ppo_series(prices, fast_window, slow_window))

    if pulse_name == "ppo_signal":
        fast_window = _param_int("fast_window")
        slow_window = _param_int("slow_window")
        signal_window = _param_int("signal_window")
        ppo_values = _ppo_series(prices, fast_window, slow_window)
        signal_values = _ema_series(ppo_values, signal_window)
        return _pack_series(bars, slow_window + signal_window - 2, signal_values)

    if pulse_name == "ppo_histogram":
        fast_window = _param_int("fast_window")
        slow_window = _param_int("slow_window")
        signal_window = _param_int("signal_window")
        ppo_values = _ppo_series(prices, fast_window, slow_window)
        signal_values = _ema_series(ppo_values, signal_window)
        histogram_values = [ppo - signal for ppo, signal in zip(ppo_values[-len(signal_values) :], signal_values)]
        return _pack_series(bars, slow_window + signal_window - 2, histogram_values)

    if pulse_name == "awesome_oscillator":
        fast_window = _param_int("fast_window")
        slow_window = _param_int("slow_window")
        ao_prices = _price_series(bars, price_field)
        fast_values = _sma_series(ao_prices, fast_window)
        slow_values = _sma_series(ao_prices, slow_window)
        oscillator_values = [fast - slow for fast, slow in zip(fast_values[-len(slow_values) :], slow_values)]
        return _pack_series(bars, slow_window - 1, oscillator_values)

    if pulse_name == "ultimate_oscillator":
        short_window = _param_int("short_window")
        medium_window = _param_int("medium_window")
        long_window = _param_int("long_window")
        _tr, _plus, _minus, _vp, _vm, buying_pressure, ultimate_tr = _directional_components(bars)
        max_window = max(short_window, medium_window, long_window)
        oscillator_values = []
        for index in range(max_window - 1, len(buying_pressure)):
            avg_short = _safe_ratio(
                sum(buying_pressure[index - short_window + 1 : index + 1]),
                sum(ultimate_tr[index - short_window + 1 : index + 1]),
                0.0,
            )
            avg_medium = _safe_ratio(
                sum(buying_pressure[index - medium_window + 1 : index + 1]),
                sum(ultimate_tr[index - medium_window + 1 : index + 1]),
                0.0,
            )
            avg_long = _safe_ratio(
                sum(buying_pressure[index - long_window + 1 : index + 1]),
                sum(ultimate_tr[index - long_window + 1 : index + 1]),
                0.0,
            )
            oscillator_values.append(100.0 * ((4.0 * avg_short) + (2.0 * avg_medium) + avg_long) / 7.0)
        return _pack_series(bars, max_window, oscillator_values)

    if pulse_name == "tsi":
        short_window = _param_int("short_window")
        long_window = _param_int("long_window")
        _ensure(len(prices) >= 2, "TSI requires at least two observations.")
        momentum = [prices[index] - prices[index - 1] for index in range(1, len(prices))]
        absolute_momentum = [abs(value) for value in momentum]
        smoothed_momentum = _ema_series(_ema_series(momentum, long_window), short_window)
        smoothed_absolute = _ema_series(_ema_series(absolute_momentum, long_window), short_window)
        tsi_values = [
            100.0 * _safe_ratio(momentum_value, absolute_value, 0.0)
            for momentum_value, absolute_value in zip(smoothed_momentum, smoothed_absolute)
        ]
        return _pack_series(bars, long_window + short_window - 1, tsi_values)

    if pulse_name == "stoch_rsi":
        rsi_window = _param_int("rsi_window")
        stochastic_window = _param_int("stochastic_window")
        smooth_window = _param_int("smooth_window", 1)
        rsi_values = _rsi_series(prices, rsi_window)
        raw_stoch = []
        for index in range(stochastic_window - 1, len(rsi_values)):
            segment = rsi_values[index - stochastic_window + 1 : index + 1]
            highest = max(segment)
            lowest = min(segment)
            raw_stoch.append(100.0 * _safe_ratio(rsi_values[index] - lowest, highest - lowest, 0.0))
        if smooth_window <= 1:
            return _pack_series(bars, rsi_window + stochastic_window - 1, raw_stoch)
        smooth_values = _sma_series(raw_stoch, smooth_window)
        return _pack_series(bars, rsi_window + stochastic_window + smooth_window - 2, smooth_values)

    if pulse_name == "mfi":
        window = _param_int("window")
        typical = _price_series(bars, "typical_price")
        _ensure(len(typical) >= window + 1, f"MFI requires at least {window + 1} observations.")
        positive_flow = []
        negative_flow = []
        for index in range(1, len(typical)):
            flow = typical[index] * volumes[index]
            if typical[index] > typical[index - 1]:
                positive_flow.append(flow)
                negative_flow.append(0.0)
            elif typical[index] < typical[index - 1]:
                positive_flow.append(0.0)
                negative_flow.append(flow)
            else:
                positive_flow.append(0.0)
                negative_flow.append(0.0)
        mfi_values = []
        for index in range(window - 1, len(positive_flow)):
            positive = sum(positive_flow[index - window + 1 : index + 1])
            negative = sum(negative_flow[index - window + 1 : index + 1])
            money_ratio = _safe_ratio(positive, negative, 0.0)
            if negative == 0:
                mfi_values.append(100.0 if positive > 0 else 0.0)
            else:
                mfi_values.append(100.0 - (100.0 / (1.0 + money_ratio)))
        return _pack_series(bars, window, mfi_values)

    if pulse_name == "obv":
        start_value = _param_float("start_value", 0.0)
        return _pack_series(bars, 0, _obv_series(bars, start_value))

    if pulse_name == "chaikin_money_flow":
        window = _param_int("window")
        cmf_values = []
        for index in range(window - 1, len(bars)):
            trailing_bars = bars[index - window + 1 : index + 1]
            money_flow_volume = [(_money_flow_multiplier(bar) * bar["volume"]) for bar in trailing_bars]
            cmf_values.append(_safe_ratio(sum(money_flow_volume), sum(bar["volume"] for bar in trailing_bars), 0.0))
        return _pack_series(bars, window - 1, cmf_values)

    if pulse_name == "accumulation_distribution":
        start_value = _param_float("start_value", 0.0)
        return _pack_series(bars, 0, _adl_series(bars, start_value))

    if pulse_name == "chaikin_oscillator":
        fast_window = _param_int("fast_window")
        slow_window = _param_int("slow_window")
        adl_values = _adl_series(bars, 0.0)
        fast_values = _ema_series(adl_values, fast_window)
        slow_values = _ema_series(adl_values, slow_window)
        oscillator_values = [fast - slow for fast, slow in zip(fast_values[-len(slow_values) :], slow_values)]
        return _pack_series(bars, slow_window - 1, oscillator_values)

    if pulse_name == "atr":
        window = _param_int("window")
        return _pack_series(bars, window - 1, _wilder_average_series(_true_range_values(bars, include_first=True), window))

    if pulse_name == "natr":
        window = _param_int("window")
        atr_values = _wilder_average_series(_true_range_values(bars, include_first=True), window)
        natr_values = [
            100.0 * _safe_ratio(atr_value, closes[(window - 1) + index], 0.0)
            for index, atr_value in enumerate(atr_values)
        ]
        return _pack_series(bars, window - 1, natr_values)

    if pulse_name == "true_range":
        return _pack_series(bars, 0, _true_range_values(bars, include_first=True))

    if pulse_name == "adx":
        window = _param_int("window")
        _plus_di, _minus_di, dx = _dmi_series(bars, window)
        adx_values = _wilder_average_series(dx, window)
        return _pack_series(bars, (2 * window) - 1, adx_values)

    if pulse_name == "plus_di":
        window = _param_int("window")
        plus_di, _minus_di, _dx = _dmi_series(bars, window)
        return _pack_series(bars, window, plus_di)

    if pulse_name == "minus_di":
        window = _param_int("window")
        _plus_di, minus_di, _dx = _dmi_series(bars, window)
        return _pack_series(bars, window, minus_di)

    if pulse_name == "aroon_up":
        window = _param_int("window")
        values = []
        for index in range(window - 1, len(bars)):
            trailing_highs = highs[index - window + 1 : index + 1]
            highest_index = _last_index_of_max(trailing_highs)
            periods_since_high = (window - 1) - highest_index
            values.append(100.0 * (float(window) - float(periods_since_high)) / float(window))
        return _pack_series(bars, window - 1, values)

    if pulse_name == "aroon_down":
        window = _param_int("window")
        values = []
        for index in range(window - 1, len(bars)):
            trailing_lows = lows[index - window + 1 : index + 1]
            lowest_index = _last_index_of_min(trailing_lows)
            periods_since_low = (window - 1) - lowest_index
            values.append(100.0 * (float(window) - float(periods_since_low)) / float(window))
        return _pack_series(bars, window - 1, values)

    if pulse_name == "aroon_oscillator":
        window = _param_int("window")
        values = []
        for index in range(window - 1, len(bars)):
            trailing_highs = highs[index - window + 1 : index + 1]
            trailing_lows = lows[index - window + 1 : index + 1]
            highest_index = _last_index_of_max(trailing_highs)
            lowest_index = _last_index_of_min(trailing_lows)
            up = 100.0 * (float(window) - float((window - 1) - highest_index)) / float(window)
            down = 100.0 * (float(window) - float((window - 1) - lowest_index)) / float(window)
            values.append(up - down)
        return _pack_series(bars, window - 1, values)

    if pulse_name == "bollinger_percent_b":
        window = _param_int("window")
        stddev_multiplier = _param_float("stddev_multiplier")
        values = []
        for index in range(window - 1, len(prices)):
            trailing = prices[index - window + 1 : index + 1]
            middle = sum(trailing) / float(window)
            deviation = _stddev(trailing)
            upper = middle + (stddev_multiplier * deviation)
            lower = middle - (stddev_multiplier * deviation)
            values.append(0.5 if upper == lower else (prices[index] - lower) / (upper - lower))
        return _pack_series(bars, window - 1, values)

    if pulse_name == "bollinger_bandwidth":
        window = _param_int("window")
        stddev_multiplier = _param_float("stddev_multiplier")
        values = []
        for index in range(window - 1, len(prices)):
            trailing = prices[index - window + 1 : index + 1]
            middle = sum(trailing) / float(window)
            deviation = _stddev(trailing)
            upper = middle + (stddev_multiplier * deviation)
            lower = middle - (stddev_multiplier * deviation)
            values.append(_safe_ratio(upper - lower, middle, 0.0))
        return _pack_series(bars, window - 1, values)

    if pulse_name == "donchian_position":
        window = _param_int("window")
        values = []
        for index in range(window - 1, len(bars)):
            trailing_highs = highs[index - window + 1 : index + 1]
            trailing_lows = lows[index - window + 1 : index + 1]
            upper = max(trailing_highs)
            lower = min(trailing_lows)
            values.append(0.5 if upper == lower else (closes[index] - lower) / (upper - lower))
        return _pack_series(bars, window - 1, values)

    if pulse_name == "keltner_percent_b":
        ema_window = _param_int("ema_window")
        atr_window = _param_int("atr_window")
        atr_multiplier = _param_float("atr_multiplier")
        middle_values = _ema_series(prices, ema_window)
        atr_values = _wilder_average_series(_true_range_values(bars, include_first=True), atr_window)
        middle_start = ema_window - 1
        atr_start = atr_window - 1
        start_index = max(middle_start, atr_start)
        values = []
        for bar_index in range(start_index, len(bars)):
            middle = middle_values[bar_index - middle_start]
            atr_value = atr_values[bar_index - atr_start]
            upper = middle + (atr_multiplier * atr_value)
            lower = middle - (atr_multiplier * atr_value)
            values.append(0.5 if upper == lower else (prices[bar_index] - lower) / (upper - lower))
        return _pack_series(bars, start_index, values)

    if pulse_name == "ichimoku_conversion_line":
        conversion_window = _param_int("conversion_window")
        values = []
        for index in range(conversion_window - 1, len(bars)):
            trailing_highs = highs[index - conversion_window + 1 : index + 1]
            trailing_lows = lows[index - conversion_window + 1 : index + 1]
            values.append((max(trailing_highs) + min(trailing_lows)) / 2.0)
        return _pack_series(bars, conversion_window - 1, values)

    if pulse_name == "ichimoku_base_line":
        base_window = _param_int("base_window")
        values = []
        for index in range(base_window - 1, len(bars)):
            trailing_highs = highs[index - base_window + 1 : index + 1]
            trailing_lows = lows[index - base_window + 1 : index + 1]
            values.append((max(trailing_highs) + min(trailing_lows)) / 2.0)
        return _pack_series(bars, base_window - 1, values)

    if pulse_name == "vortex_plus":
        window = _param_int("window")
        true_ranges, _plus_dms, _minus_dms, vortex_plus, _vortex_minus, _bp, _utr = _directional_components(bars)
        values = []
        for index in range(window - 1, len(vortex_plus)):
            values.append(
                _safe_ratio(
                    sum(vortex_plus[index - window + 1 : index + 1]),
                    sum(true_ranges[index - window + 1 : index + 1]),
                    0.0,
                )
            )
        return _pack_series(bars, window, values)

    if pulse_name == "vortex_minus":
        window = _param_int("window")
        true_ranges, _plus_dms, _minus_dms, _vortex_plus, vortex_minus, _bp, _utr = _directional_components(bars)
        values = []
        for index in range(window - 1, len(vortex_minus)):
            values.append(
                _safe_ratio(
                    sum(vortex_minus[index - window + 1 : index + 1]),
                    sum(true_ranges[index - window + 1 : index + 1]),
                    0.0,
                )
            )
        return _pack_series(bars, window, values)

    if pulse_name == "chande_momentum_oscillator":
        window = _param_int("window")
        _ensure(len(prices) >= window + 1, f"CMO requires at least {window + 1} observations.")
        changes = [prices[index] - prices[index - 1] for index in range(1, len(prices))]
        values = []
        for index in range(window - 1, len(changes)):
            trailing_changes = changes[index - window + 1 : index + 1]
            gains = sum(max(change, 0.0) for change in trailing_changes)
            losses = sum(max(-change, 0.0) for change in trailing_changes)
            values.append(100.0 * _safe_ratio(gains - losses, gains + losses, 0.0))
        return _pack_series(bars, window, values)

    raise ValueError(f"Unsupported technical analysis pulse: {pulse_name}")


try:
    result = _compute_indicator()
except Exception as exc:
    result = {"error": str(exc)}
