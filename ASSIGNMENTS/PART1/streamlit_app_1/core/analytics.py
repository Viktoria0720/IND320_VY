# core/analytics.py
import numpy as np
import pandas as pd
from scipy.fft import dct, idct
from sklearn.neighbors import LocalOutlierFactor
from statsmodels.tsa.seasonal import STL
from scipy.signal import spectrogram

try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except Exception:
    px = None
    go = None
    make_subplots = None

def stl_decompose_production(prod_df, area, group,
                             period=24, seasonal=13, trend=101, robust=True):
    if go is None or make_subplots is None:
        raise RuntimeError("Plotly not available.")
    df = prod_df.copy()
    if "area" not in df.columns:
        df["area"] = area
    if "group" not in df.columns:
        df["group"] = group
    df = df[(df["area"] == area) & (df["group"] == group)].sort_values("time")
    if df.empty:
        raise ValueError(f"No production for {area}/{group}")
    y = pd.Series(df["production"].to_numpy(float), index=pd.to_datetime(df["time"]))
    if len(y) < period * 2:
        raise ValueError(
            f"Not enough data points ({len(y)}) for STL with period={period}."
        )
    res = STL(y, period=period, seasonal=seasonal, trend=trend, robust=robust).fit()
    comp_df = pd.DataFrame(
        {"observed": y, "trend": res.trend, "seasonal": res.seasonal, "resid": res.resid},
        index=y.index,
    )
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.02,
        subplot_titles=["Observed", "Trend", "Seasonal", "Remainder"],
    )
    for row, key in enumerate(["observed", "trend", "seasonal", "resid"], start=1):
        fig.add_trace(
            go.Scatter(x=comp_df.index, y=comp_df[key], mode="lines", name=key.title()),
            row=row, col=1,
        )
    fig.update_layout(
        height=700, title=f"STL – {area}/{group}", showlegend=False, hovermode="x unified"
    )
    return fig, res

def production_spectrogram(prod_df, area, group, window_len=24*7, overlap=0.5):
    if go is None:
        raise RuntimeError("Plotly not available.")
    df = prod_df.copy()
    if "area" not in df.columns:
        df["area"] = area
    if "group" not in df.columns:
        df["group"] = group
    df = df[(df["area"] == area) & (df["group"] == group)].sort_values("time")
    if df.empty:
        raise ValueError(f"No production for {area}/{group}")
    x = df["production"].to_numpy(float)
    fs = 1.0
    nperseg = int(window_len)
    noverlap = int(overlap * nperseg)
    f, t, Sxx = spectrogram(x, fs=fs, nperseg=nperseg, noverlap=noverlap, scaling="spectrum")
    z_db = 10 * np.log10(Sxx + 1e-12)
    fig = go.Figure(
        data=go.Heatmap(x=t, y=f, z=z_db, colorbar=dict(title="Power [dB]"))
    )
    fig.update_layout(
        title=f"Spectrogram – {area}/{group}",
        xaxis_title="Window index",
        yaxis_title="Frequency [cycles/hour]",
        height=400,
    )
    return fig

def spc_outliers_temperature(df, dct_cutoff=0.02, n_sigma=3.5, spc_stats=None):
    if go is None:
        raise RuntimeError("Plotly not available.")
    ts = df[["timestamp", "temperature_2m"]].dropna().copy()
    if ts.empty:
        raise ValueError("No temperature data.")
    x = ts["temperature_2m"].to_numpy(float)
    X = dct(x, type=2, norm="ortho")
    k = max(1, int(len(X) * dct_cutoff))
    X_hp = X.copy()
    X_hp[:k] = 0.0
    satv = idct(X_hp, type=2, norm="ortho")
    satv_s = pd.Series(satv, index=ts.index, name="SATV")

    if spc_stats is None:
        med = float(np.median(satv))
        mad = float(np.median(np.abs(satv - med)))
        sigma = 1.4826 * mad if mad > 0 else float(np.std(satv))
        upper = med + n_sigma * sigma
        lower = med - n_sigma * sigma
    else:
        med = float(spc_stats["median_SATV"])
        sigma = float(spc_stats["sigma_robust"])
        upper = float(spc_stats["upper_bound"])
        lower = float(spc_stats["lower_bound"])

    is_out = (satv_s > upper) | (satv_s < lower)
    out_df = ts.loc[is_out].assign(SATV=satv_s.loc[is_out])

    baseline = x - satv
    baseline_s = pd.Series(baseline, index=ts.index, name="baseline_temp")
    upper_curve = baseline_s + upper
    lower_curve = baseline_s + lower
    times = ts["timestamp"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=times, y=ts["temperature_2m"], mode="lines", name="Temperature"))
    fig.add_trace(go.Scatter(x=times, y=upper_curve, mode="lines",
                             name=f"SPC upper (±{n_sigma}σ)", line=dict(dash="dash")))
    fig.add_trace(go.Scatter(x=times, y=lower_curve, mode="lines",
                             name=f"SPC lower (±{n_sigma}σ)", line=dict(dash="dash")))
    if not out_df.empty:
        fig.add_trace(
            go.Scatter(
                x=out_df["timestamp"], y=out_df["temperature_2m"],
                mode="markers", name="Outlier",
                marker=dict(color="crimson", size=7, line=dict(color="black", width=0.5)),
            )
        )
    fig.update_layout(
        title="Temperature with SPC Outliers (SATV via DCT high-pass)",
        yaxis_title="°C",
        hovermode="x unified",
        height=400,
    )

    summary = pd.DataFrame([{
        "n": int(len(ts)),
        "n_outliers": int(is_out.sum()),
        "pct_outliers": float(is_out.mean() * 100.0),
        "dct_cutoff": float(dct_cutoff),
        "n_sigma": float(n_sigma),
        "median_SATV": med,
        "sigma_robust": sigma,
        "upper_bound": upper,
        "lower_bound": lower,
    }])
    return fig, out_df, summary

def lof_precip_anomalies(df, contamination=0.01, n_neighbors=35):
    if go is None:
        raise RuntimeError("Plotly not available.")
    sub = df[["timestamp", "precipitation"]].dropna().copy()
    if sub.empty:
        raise ValueError("No precipitation data.")
    if len(sub) <= n_neighbors:
        raise ValueError(
            f"Not enough data points ({len(sub)}) for LOF with n_neighbors={n_neighbors}."
        )
    y = sub["precipitation"].to_numpy(float).reshape(-1, 1)
    lof = LocalOutlierFactor(n_neighbors=n_neighbors, contamination=contamination)
    labels = lof.fit_predict(y)
    sub["lof_score"] = -lof.negative_outlier_factor_
    anoms = sub.loc[labels == -1]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=sub["timestamp"], y=sub["precipitation"],
        mode="lines", name="Precipitation",
    ))
    if not anoms.empty:
        fig.add_trace(go.Scatter(
            x=anoms["timestamp"], y=anoms["precipitation"],
            mode="markers", name="LOF anomaly",
            marker=dict(color="orange", size=7, line=dict(color="black", width=0.5)),
        ))
    fig.update_layout(
        title="Precipitation & LOF anomalies",
        yaxis_title="mm",
        hovermode="x unified",
        height=400,
    )
    summary = pd.DataFrame([{
        "n": int(len(sub)),
        "n_anomalies": int(len(anoms)),
        "pct_anomalies": float(100*len(anoms)/max(1, len(sub))),
        "contamination": float(contamination),
        "n_neighbors": int(n_neighbors),
    }])
    return fig, anoms, summary
