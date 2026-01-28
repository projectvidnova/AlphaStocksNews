#!/usr/bin/env python3
"""
Fetch 15-minute historical data for a symbol and plot 5-period EMA on close price.
Saves output PNG to `plots/`.

Usage:
    python scripts\plot_ema5_nifty_bank.py --symbol "NIFTY BANK" --timeframe 15minute --days 30

Notes:
- Requires project dependencies: `clickhouse_connect`, `pandas`, `matplotlib`.
- Script uses `config/database.json` (development) by default.
"""

import argparse
import asyncio
import json
import os
from datetime import timedelta
import logging

import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf

import sys
from pathlib import Path

# Ensure project root is on sys.path so `from src...` works when running
# this script from the `scripts/` directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.clickhouse_data_layer import ClickHouseDataLayer
from src.utils.timezone_utils import get_current_time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("plot_ema5")


async def fetch_and_plot(symbol: str, timeframe: str, days: int, out_path: str, db_config_path: str):
    # Load DB config
    if not os.path.exists(db_config_path):
        logger.error(f"Database config not found: {db_config_path}")
        return 1

    with open(db_config_path, 'r', encoding='utf-8') as fh:
        cfg = json.load(fh)

    env = cfg.get('default', 'development')
    env_cfg = cfg.get(env, {}).get('clickhouse', {})

    host = env_cfg.get('host', 'localhost')
    port = int(env_cfg.get('port', 8123))
    database = env_cfg.get('database', 'alphastock')
    username = env_cfg.get('username', 'default')
    password = env_cfg.get('password', '')

    data_layer = ClickHouseDataLayer(host=host, port=port, database=database, username=username, password=password)
    ok = await data_layer.initialize()
    if not ok:
        logger.error("Failed to initialize ClickHouse data layer. Check connection and dependencies.")
        return 1

    end = get_current_time()
    start = end - timedelta(days=days)

    logger.info(f"Fetching historical data for {symbol} ({timeframe}) from {start} to {end}")
    df_hist = await data_layer.get_historical_data(symbol=symbol, timeframe=timeframe, start_date=start, end_date=end)

    # Normalize historical DataFrame
    if df_hist is None:
        df_hist = pd.DataFrame()

    if not df_hist.empty:
        # Ensure timestamp column is datetime and set as index
        if 'timestamp' in df_hist.columns:
            df_hist['timestamp'] = pd.to_datetime(df_hist['timestamp'])
            df_hist.set_index('timestamp', inplace=True)
            df_hist.sort_index(inplace=True)

    # If historical data ends before `end`, fetch recent ticks from market_data
    # and resample into timeframe candles, then append to historical data.
    def timeframe_to_offset(tf: str) -> str:
        # Expect formats like '15minute' or '5minute' or '1minute'
        tf = tf.lower().strip()
        if tf.endswith('minute'):
            num = tf.replace('minute', '')
            try:
                n = int(num)
                return f"{n}min"
            except Exception:
                return '15min'
        # default
        return '15min'

    pandas_offset = timeframe_to_offset(timeframe)

    need_ticks_from = None
    if df_hist.empty:
        # No historical data; fetch ticks from start..end
        need_ticks_from = start
    else:
        last_hist_ts = df_hist.index.max()
        # If last historical timestamp is older than end - one timeframe, fetch ticks from last_hist_ts
        if last_hist_ts < end - pd.Timedelta(pandas_offset):
            # start fetching ticks just after last historical candle
            need_ticks_from = last_hist_ts + pd.Timedelta(seconds=1)

    ticks_df = pd.DataFrame()
    if need_ticks_from is not None:
        logger.info(f"Fetching ticks from market_data for {symbol} from {need_ticks_from} to {end}")
        ticks_df = await data_layer.get_market_data(symbol=symbol, start_time=need_ticks_from, end_time=end)

        if ticks_df is None:
            ticks_df = pd.DataFrame()

        if not ticks_df.empty:
            # Ensure index is datetime
            if 'timestamp' in ticks_df.columns and not isinstance(ticks_df.index, pd.DatetimeIndex):
                ticks_df['timestamp'] = pd.to_datetime(ticks_df['timestamp'])
                ticks_df.set_index('timestamp', inplace=True)
            ticks_df.sort_index(inplace=True)

            # Use 'ltp' as tick price if present, otherwise 'close'
            if 'ltp' in ticks_df.columns:
                ticks_df['tick_price'] = ticks_df['ltp']
            elif 'close' in ticks_df.columns:
                ticks_df['tick_price'] = ticks_df['close']
            else:
                # fallback: try first numeric column
                numeric_cols = ticks_df.select_dtypes(include=['number']).columns.tolist()
                if numeric_cols:
                    ticks_df['tick_price'] = ticks_df[numeric_cols[0]]
                else:
                    ticks_df['tick_price'] = 0.0

            # Resample ticks into OHLCV for the requested timeframe
            ohlc = ticks_df['tick_price'].resample(pandas_offset).ohlc()
            # Volume: sum if present
            if 'volume' in ticks_df.columns:
                vol = ticks_df['volume'].resample(pandas_offset).sum()
            else:
                vol = pd.Series(0, index=ohlc.index)

            resampled = ohlc.copy()
            resampled['volume'] = vol
            # Name columns to match historical_data (lowercase)
            resampled.rename(columns={'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close'}, inplace=True)

            # Attach timeframe & symbol columns
            resampled['timeframe'] = timeframe
            resampled['symbol'] = symbol

            # Drop rows with NaN close (partial intervals)
            resampled.dropna(subset=['close'], inplace=True)

            # Append to historical
            if df_hist.empty:
                df_combined = resampled
            else:
                # Combine and de-duplicate by index
                df_combined = pd.concat([df_hist[['open','high','low','close','volume']], resampled[['open','high','low','close','volume']]])
                df_combined = df_combined[~df_combined.index.duplicated(keep='first')]
                df_combined.sort_index(inplace=True)
        else:
            df_combined = df_hist.copy()
    else:
        df_combined = df_hist.copy()

    # (removed stray check for `df` which was undefined in this scope)

    # Use df_combined (which contains historical + today's resampled candles)
    if df_combined is None or df_combined.empty:
        logger.warning("No candle data available to plot.")
        await data_layer.close()
        return 1

    df = df_combined.copy()

    # Ensure index is datetime and sorted
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)

    # matplotlib and mplfinance work best with tz-naive datetimes.
    # If the index is timezone-aware, convert to UTC and drop tzinfo.
    try:
        if getattr(df.index, 'tz', None) is not None:
            df.index = df.index.tz_convert('UTC').tz_localize(None)
    except Exception:
        # Fallback: remove tzinfo if possible
        try:
            df.index = df.index.tz_localize(None)
        except Exception:
            # As a last resort, coerce to naive datetimes
            df.index = pd.to_datetime(df.index).tz_convert('UTC').tz_localize(None) if getattr(df.index, 'tz', None) is not None else pd.to_datetime(df.index)

    # Convert index to Python native datetimes (not numpy datetime64) — matplotlib
    # / mplfinance works more reliably with `datetime.datetime` objects.
    try:
        df.index = df.index.to_pydatetime()
    except Exception:
        # If conversion fails, keep the index as-is
        pass

    # Compute 5-period EMA on close
    df['EMA5'] = df['close'].ewm(span=5, adjust=False).mean()
    
    # Prepare OHLC DataFrame for mplfinance (rename columns)
    ohlc = df[['open', 'high', 'low', 'close', 'volume']].copy()
    ohlc.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True)

    # Attach EMA as an addplot (mplfinance reads Series indexed by datetime)
    ema_series = df['EMA5'].copy()
    ema_series.index = df.index

    add_plots = [mpf.make_addplot(ema_series, color='tab:blue', width=1.0, secondary_y=False)]

    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # Plot candlesticks with EMA overlay and volume; return figure to customize x-axis
    fig, axes = mpf.plot(
        ohlc,
        type='candle',
        style='yahoo',
        title=f"{symbol} - {timeframe} - Candles and EMA(5)",
        ylabel='Price',
        addplot=add_plots,
        volume=True,
        tight_layout=True,
        returnfig=True
    )

    # Customize x-axis labels: show time as usual, but include the date only when the date changes
    try:
        import matplotlib.dates as mdates

        ax = axes[0]
        # Get current tick positions (in matplotlib datenums)
        ticks = ax.get_xticks()
        if len(ticks) > 0:
            times = mdates.num2date(ticks)
            labels = []
            prev_date = None
            for dt in times:
                # Convert to local/display timezone aware datetime if needed
                # Use time label
                time_label = dt.strftime('%H:%M')
                # If date changed compared to previous tick, include date on second line
                date_label = ''
                if prev_date is None or dt.date() != prev_date:
                    date_label = dt.strftime('%Y-%m-%d')
                if date_label:
                    labels.append(f"{time_label}\n{date_label}")
                else:
                    labels.append(time_label)
                prev_date = dt.date()

            ax.set_xticks(ticks)
            ax.set_xticklabels(labels, rotation=0)

        # Save the figure (we used returnfig so save manually)
        fig.savefig(out_path, dpi=150, bbox_inches='tight')

    except Exception as e:
        # Fallback: save via mplfinance kwargs if customization fails
        logger.warning(f"Could not customize x-axis labels: {e}")
        fig.savefig(out_path, dpi=150, bbox_inches='tight')

    logger.info(f"Saved plot to {out_path}")

    # Optionally show (commented out for headless environments)
    # plt.show()

    await data_layer.close()
    return 0


def cli():
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', default='NIFTY BANK')
    p.add_argument('--timeframe', default='15minute')
    p.add_argument('--days', type=int, default=30, help='Days of history to fetch')
    p.add_argument('--out', default='plots/nifty_bank_15m_ema5.png')
    p.add_argument('--db-config', default='config/database.json')
    args = p.parse_args()

    return asyncio.run(fetch_and_plot(args.symbol, args.timeframe, args.days, args.out, args.db_config))


if __name__ == '__main__':
    raise SystemExit(cli())
