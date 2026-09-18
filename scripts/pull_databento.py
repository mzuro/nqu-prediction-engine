#!/usr/bin/env python3
"""Paid Databento pulls for NQU prediction-engine data_disk.

Reads DATABENTO_API_KEY from the environment. Never prints the key.
Large raw parquet.gz stay under data_disk/**/raw/ (gitignored).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
FUTURES_DIR = REPO_ROOT / "data_disk" / "03_futures_cme"
EQUITIES_DIR = REPO_ROOT / "data_disk" / "04_equities_dbeq"
COST_ABORT_USD = 150.0

EQUITY_TICKERS = [
    "NVDA",
    "MSFT",
    "AAPL",
    "AMZN",
    "META",
    "AVGO",
    "AMD",
    "COST",
    "GILD",
    "PYPL",
]

# Prefer volume-ranked continuous front; fall back to parent symbology.
FUTURES_CONTINUOUS = ["NQ.v.0", "ES.v.0", "VX.v.0"]
FUTURES_PARENT = ["NQ.FUT", "ES.FUT", "VX.FUT"]
FUTURES_SCHEMAS = ["trades", "mbp-10"]
EQUITIES_SCHEMAS = ["trades", "mbp-10"]


def _require_databento():
    try:
        import databento as db  # noqa: F401
    except ImportError:
        print(
            "ERROR: databento is not installed.\n"
            "  pip install databento pandas\n"
            "Then re-run this script.",
            file=sys.stderr,
        )
        sys.exit(1)
    return __import__("databento")


def _client():
    db = _require_databento()
    key = os.environ.get("DATABENTO_API_KEY") or os.environ.get("DATABENTO_KEY")
    if not key or not str(key).strip():
        print(
            "ERROR: DATABENTO_API_KEY is not set in the environment.\n"
            "Export it before running (the key is never printed by this script).",
            file=sys.stderr,
        )
        sys.exit(1)
    # Historical() reads DATABENTO_API_KEY; pass explicitly without logging it.
    return db.Historical(key=key)


def _detect_equities_dataset(client) -> str:
    """Prefer DBEQ.BASIC, then EQUS.MINI / EQUS.*, else first DBEQ* hit."""
    try:
        datasets = list(client.metadata.list_datasets())
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: list_datasets failed ({exc}); defaulting to DBEQ.BASIC")
        return "DBEQ.BASIC"

    preferred = [
        "DBEQ.BASIC",
        "EQUS.MINI",
        "EQUS.SUMMARY",
        "DBEQ.MAX",
    ]
    for name in preferred:
        if name in datasets:
            print(f"Equities dataset: {name}")
            return name

    for d in datasets:
        if d.startswith("DBEQ") or d.startswith("EQUS"):
            print(f"Equities dataset (auto): {d}")
            return d

    print("WARN: no DBEQ/EQUS dataset found; using DBEQ.BASIC")
    return "DBEQ.BASIC"


def _resolve_futures_symbols(client, start: str, end: str) -> tuple[list[str], str, str]:
    """Return (symbols, stype_in, note). Prefer continuous; else parent."""
    # Probe continuous cost; on failure fall back to parent.
    try:
        client.metadata.get_cost(
            dataset="GLBX.MDP3",
            symbols=FUTURES_CONTINUOUS,
            schema="trades",
            start=start,
            end=end,
            stype_in="continuous",
        )
        note = (
            "Using continuous volume-ranked front contracts "
            f"{FUTURES_CONTINUOUS} (stype_in=continuous)."
        )
        print(note)
        return FUTURES_CONTINUOUS, "continuous", note
    except Exception as exc:  # noqa: BLE001
        note = (
            f"Continuous symbology unavailable ({exc}); "
            f"falling back to parent symbology {FUTURES_PARENT} "
            "(stype_in=parent). Documented parent roots: NQ.FUT, ES.FUT, VX.FUT."
        )
        print(note)
        return FUTURES_PARENT, "parent", note


def _get_cost(
    client,
    *,
    dataset: str,
    symbols: Iterable[str],
    schema: str,
    start: str,
    end: str,
    stype_in: str,
) -> float:
    cost = client.metadata.get_cost(
        dataset=dataset,
        symbols=list(symbols),
        schema=schema,
        start=start,
        end=end,
        stype_in=stype_in,
    )
    return float(cost)


def _abort_if_expensive(cost: float, label: str, force: bool) -> None:
    print(f"COST {label}: ${cost:.2f} USD")
    if cost > COST_ABORT_USD and not force:
        print(
            f"ABORT: estimated cost ${cost:.2f} exceeds ${COST_ABORT_USD:.0f}. "
            "Re-run with --force to override.",
            file=sys.stderr,
        )
        sys.exit(2)


def _write_sizes(out_dir: Path) -> Path:
    lines = ["# SIZES.md — local parquet.gz / parquet footprints\n", "| path | bytes |\n", "|------|------:|\n"]
    found = False
    for pattern in ("**/*.parquet.gz", "**/*.parquet"):
        for p in sorted(out_dir.glob(pattern)):
            found = True
            rel = p.relative_to(REPO_ROOT)
            lines.append(f"| `{rel.as_posix()}` | {p.stat().st_size} |\n")
    if not found:
        lines.append("| _(none yet)_ | 0 |\n")
    path = out_dir / "SIZES.md"
    path.write_text("".join(lines), encoding="utf-8")
    print(f"Wrote {path.relative_to(REPO_ROOT)}")
    return path


def _trades_to_1min_ohlc(df, symbol: str):
    """Resample trade prints to 1-min OHLC (+ volume) in America/New_York."""
    import pandas as pd

    if df is None or len(df) == 0:
        return pd.DataFrame(columns=["ts", "symbol", "open", "high", "low", "close", "volume"])

    work = df.copy()
    # Databento DBN -> DataFrame typically has ts_event / price / size
    ts_col = "ts_event" if "ts_event" in work.columns else work.index.name
    if ts_col and ts_col in work.columns:
        work["ts"] = pd.to_datetime(work[ts_col], utc=True)
        work = work.set_index("ts")
    elif not isinstance(work.index, pd.DatetimeIndex):
        work.index = pd.to_datetime(work.index, utc=True)

    if work.index.tz is None:
        work.index = work.index.tz_localize("UTC")
    work = work.tz_convert("America/New_York")

    price_col = "price" if "price" in work.columns else None
    size_col = "size" if "size" in work.columns else None
    if price_col is None:
        raise ValueError("trades frame missing price column")

    # Databento prices are often fixed-point ints; scale if needed
    prices = work[price_col].astype("float64")
    if prices.abs().median() > 1e6:
        prices = prices / 1e9

    ohlc = prices.resample("1min").ohlc()
    ohlc.columns = ["open", "high", "low", "close"]
    if size_col:
        ohlc["volume"] = work[size_col].astype("float64").resample("1min").sum()
    else:
        ohlc["volume"] = 0.0
    ohlc = ohlc.dropna(subset=["open"])
    ohlc = ohlc.reset_index()
    ohlc = ohlc.rename(columns={ohlc.columns[0]: "ts"})
    ohlc.insert(1, "symbol", symbol)
    return ohlc


def _filter_rth_equities(df):
    import pandas as pd

    if df is None or len(df) == 0:
        return df
    work = df.copy()
    if "ts_event" in work.columns:
        work["ts"] = pd.to_datetime(work["ts_event"], utc=True)
        work = work.set_index("ts")
    if not isinstance(work.index, pd.DatetimeIndex):
        work.index = pd.to_datetime(work.index, utc=True)
    if work.index.tz is None:
        work.index = work.index.tz_localize("UTC")
    work = work.tz_convert("America/New_York")
    minutes = work.index.hour * 60 + work.index.minute
    # RTH 09:30–16:00 ET inclusive of 09:30, exclusive of 16:00 close print window end
    mask = (minutes >= 9 * 60 + 30) & (minutes < 16 * 60)
    return work.loc[mask]


def _filter_small_lot(df):
    if df is None or len(df) == 0 or "size" not in df.columns:
        return df
    return df.loc[df["size"].astype("float64") < 100]


def _download_batch(
    client,
    *,
    dataset: str,
    symbols: list[str],
    schema: str,
    start: str,
    end: str,
    stype_in: str,
    raw_dir: Path,
    force: bool,
    dry_cost_only: bool,
    label: str,
) -> Any:
    cost = _get_cost(
        client,
        dataset=dataset,
        symbols=symbols,
        schema=schema,
        start=start,
        end=end,
        stype_in=stype_in,
    )
    _abort_if_expensive(cost, label, force)
    if dry_cost_only:
        return None

    raw_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {label} …")
    data = client.timeseries.get_range(
        dataset=dataset,
        symbols=symbols,
        schema=schema,
        start=start,
        end=end,
        stype_in=stype_in,
    )
    out = raw_dir / f"{label.replace(' ', '_').replace('/', '_')}.parquet.gz"
    # Store as parquet via pandas when possible
    try:
        df = data.to_df()
        df.to_parquet(out, compression="gzip")
        print(f"Wrote {out.relative_to(REPO_ROOT)} ({out.stat().st_size} bytes)")
        return df
    except Exception as exc:  # noqa: BLE001
        # Fall back to DBN file write if available
        dbn_path = out.with_suffix("").with_suffix(".dbn.zst")
        try:
            data.to_file(path=str(dbn_path))
            print(f"Wrote {dbn_path.relative_to(REPO_ROOT)} (parquet conversion failed: {exc})")
        except Exception as exc2:  # noqa: BLE001
            print(f"WARN: could not persist {label}: {exc}; fallback also failed: {exc2}")
        return data


def run_futures(client, args) -> None:
    symbols, stype_in, note = _resolve_futures_symbols(client, args.start, args.end)
    (FUTURES_DIR / "raw").mkdir(parents=True, exist_ok=True)
    (FUTURES_DIR / "SYMBLOGY.md").write_text(
        f"# Futures symbology\n\n{note}\n",
        encoding="utf-8",
    )

    trades_frames: dict[str, Any] = {}
    for schema in FUTURES_SCHEMAS:
        label = f"futures_{schema}"
        df = _download_batch(
            client,
            dataset="GLBX.MDP3",
            symbols=symbols,
            schema=schema,
            start=args.start,
            end=args.end,
            stype_in=stype_in,
            raw_dir=FUTURES_DIR / "raw",
            force=args.force,
            dry_cost_only=args.dry_cost_only,
            label=label,
        )
        if schema == "trades" and df is not None and hasattr(df, "columns"):
            trades_frames["ALL"] = df

    if not args.dry_cost_only and trades_frames:
        import pandas as pd

        df = trades_frames["ALL"]
        # Split by symbol if present
        sym_col = "symbol" if "symbol" in df.columns else None
        if sym_col:
            for sym, part in df.groupby(sym_col):
                root = str(sym).split(".")[0]
                ohlc = _trades_to_1min_ohlc(part, root)
                path = FUTURES_DIR / f"{root}_1min_ohlc.csv"
                ohlc.to_csv(path, index=False)
                print(f"Wrote {path.relative_to(REPO_ROOT)} ({len(ohlc)} bars)")
        else:
            ohlc = _trades_to_1min_ohlc(df, "MIXED")
            path = FUTURES_DIR / "futures_1min_ohlc.csv"
            ohlc.to_csv(path, index=False)
            print(f"Wrote {path.relative_to(REPO_ROOT)}")

    _write_sizes(FUTURES_DIR)


def run_equities(client, args) -> None:
    dataset = _detect_equities_dataset(client)
    (EQUITIES_DIR / "raw").mkdir(parents=True, exist_ok=True)
    (EQUITIES_DIR / "DATASET.md").write_text(
        f"# Equities dataset\n\nSelected: `{dataset}`\n"
        f"Tickers: {', '.join(EQUITY_TICKERS)}\n"
        "RTH filter: 09:30–16:00 America/New_York\n"
        "Small-lot filter on trades: size < 100\n",
        encoding="utf-8",
    )

    trades_df = None
    for schema in EQUITIES_SCHEMAS:
        label = f"equities_{schema}"
        df = _download_batch(
            client,
            dataset=dataset,
            symbols=EQUITY_TICKERS,
            schema=schema,
            start=args.start,
            end=args.end,
            stype_in="raw_symbol",
            raw_dir=EQUITIES_DIR / "raw",
            force=args.force,
            dry_cost_only=args.dry_cost_only,
            label=label,
        )
        if schema == "trades" and df is not None and hasattr(df, "columns"):
            trades_df = df

    if not args.dry_cost_only and trades_df is not None:
        rth = _filter_rth_equities(trades_df)
        # Full RTH 1-min + small-lot 1-min helpers
        sym_col = "symbol" if "symbol" in rth.columns else None
        if sym_col:
            for sym, part in rth.groupby(sym_col):
                ohlc = _trades_to_1min_ohlc(part, str(sym))
                path = EQUITIES_DIR / f"{sym}_1min_ohlc.csv"
                ohlc.to_csv(path, index=False)
                print(f"Wrote {path.relative_to(REPO_ROOT)} ({len(ohlc)} bars)")

                small = _filter_small_lot(part)
                sohlc = _trades_to_1min_ohlc(small, str(sym))
                spath = EQUITIES_DIR / f"{sym}_1min_ohlc_small_lot.csv"
                sohlc.to_csv(spath, index=False)
                print(f"Wrote {spath.relative_to(REPO_ROOT)} ({len(sohlc)} bars)")
        else:
            ohlc = _trades_to_1min_ohlc(rth, "MIXED")
            path = EQUITIES_DIR / "equities_1min_ohlc.csv"
            ohlc.to_csv(path, index=False)
            print(f"Wrote {path.relative_to(REPO_ROOT)}")

    _write_sizes(EQUITIES_DIR)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Pull Databento data into data_disk/")
    p.add_argument(
        "--dry-cost-only",
        action="store_true",
        help="Print USD cost via metadata.get_cost; do not download",
    )
    p.add_argument(
        "--task",
        choices=["futures", "equities", "all"],
        default="all",
        help="Which pull task to run",
    )
    p.add_argument("--start", default="2024-09-01", help="Inclusive start date (UTC)")
    p.add_argument("--end", default="2026-09-01", help="Exclusive end date (UTC)")
    p.add_argument(
        "--force",
        action="store_true",
        help=f"Allow batches costing more than ${COST_ABORT_USD:.0f}",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _require_databento()
    # Import pandas early so resample helpers fail clearly if missing
    try:
        import pandas as pd  # noqa: F401
    except ImportError:
        print("ERROR: pandas is required. pip install pandas", file=sys.stderr)
        return 1

    client = _client()
    print(f"Task={args.task} start={args.start} end={args.end} dry_cost_only={args.dry_cost_only}")

    if args.task in ("futures", "all"):
        run_futures(client, args)
    if args.task in ("equities", "all"):
        run_equities(client, args)

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
