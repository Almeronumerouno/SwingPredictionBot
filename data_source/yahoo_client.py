"""
Client data trading historis via Yahoo Finance — pengganti endpoint IDX
`GetTradingInfoSS` yang sudah mati (404) sejak IDX migrasi ke Nuxt.js.

Kode saham IDX (mis. "BBCA") perlu ditambah suffix ".JK" untuk query ke
Yahoo Finance (mis. "BBCA.JK") -- ini format ticker Yahoo untuk saham
Bursa Efek Indonesia.

PENTING - Field yang HILANG dibanding endpoint IDX asli:
- Value (nilai transaksi Rupiah) -> Yahoo tidak menyediakan ini secara
  langsung. Kita approximate dengan Close x Volume (`approx_value` di
  DailyBar), TAPI ini estimasi kasar, BUKAN data transaksi riil (real
  value memperhitungkan harga di tiap harga transaksi, bukan cuma close).
- Frequency (jumlah kali transaksi) -> tidak ada di Yahoo, di-set 0.
- Bid/Offer, Bid Volume/Offer Volume -> tidak ada di data historis Yahoo
  (itu data order book real-time, bukan historical), di-set 0.
- Foreign Buy/Sell -> tidak ada di Yahoo sama sekali, di-set 0.

Dampak ke scoring nanti (Fase 2): komponen yang mengandalkan Value asli,
Frequency, atau Foreign Flow perlu didrop atau diganti proxy lain
(misal RVOL dari Volume tetap valid, itu satu-satunya volume metric yang
robust dari sumber ini).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import yfinance as yf

import config


class YahooClientError(Exception):
    """Raised saat fetch data dari Yahoo Finance gagal."""


@dataclass
class DailyBar:
    """Satu baris data trading harian untuk satu saham (dari Yahoo Finance)."""
    date: str
    previous: float          # close hari sebelumnya, dipakai buat pct_change
    open_price: float
    high: float
    low: float
    close: float
    volume: float
    approx_value: float = 0.0    # estimasi kasar: close x volume, BUKAN data riil
    frequency: float = 0.0       # tidak tersedia dari Yahoo, selalu 0
    bid: float = 0.0             # tidak tersedia dari Yahoo, selalu 0
    offer: float = 0.0           # tidak tersedia dari Yahoo, selalu 0
    foreign_buy: float = 0.0     # tidak tersedia dari Yahoo, selalu 0
    foreign_sell: float = 0.0    # tidak tersedia dari Yahoo, selalu 0

    @property
    def pct_change(self) -> float:
        """Persentase perubahan harga (Close hari ini vs Close hari sebelumnya)."""
        if not self.previous:
            return 0.0
        return (self.close - self.previous) / self.previous * 100.0


def _to_yahoo_ticker(code: str) -> str:
    code = code.strip().upper()
    if code.endswith(config.YAHOO_TICKER_SUFFIX):
        return code
    return code + config.YAHOO_TICKER_SUFFIX


def fetch_trading_info(code: str, length: int = 60) -> list[DailyBar]:
    """
    Ambil data trading harian untuk satu kode saham dari Yahoo Finance.

    Args:
        code: kode saham IDX tanpa suffix, mis. "BBCA"
        length: jumlah hari KALENDER ke belakang yang diminta (bukan hari
                kerja - Yahoo akan otomatis skip weekend/libur, jadi minta
                buffer lebih banyak dari hari kerja yang sebenarnya
                dibutuhkan, mis. minta 90 hari kalender untuk dapat ~60
                hari kerja).

    Returns:
        List DailyBar terurut dari yang PALING LAMA ke PALING BARU
        (index terakhir = data terbaru). List kosong kalau kode saham
        tidak ditemukan / tidak ada data (mis. baru IPO, atau delisted).
    """
    ticker = _to_yahoo_ticker(code)
    end = date.today() + timedelta(days=1)
    start = date.today() - timedelta(days=length)

    try:
        df = yf.Ticker(ticker).history(start=start.isoformat(), end=end.isoformat(), interval="1d")
    except Exception as e:  # noqa: BLE001
        raise YahooClientError(f"Gagal fetch {ticker} dari Yahoo Finance: {e}") from e

    if df is None or df.empty:
        return []

    df = df.reset_index()
    # Kolom Date bisa bernama "Date" atau punya timezone info tergantung versi yfinance
    date_col = "Date" if "Date" in df.columns else df.columns[0]

    bars: list[DailyBar] = []
    prev_close: Optional[float] = None

    for _, row in df.iterrows():
        close = float(row["Close"])
        volume = float(row["Volume"])
        if not (math.isfinite(close) and math.isfinite(volume)):
            continue
        bar = DailyBar(
            date=str(row[date_col].date()) if hasattr(row[date_col], "date") else str(row[date_col]),
            previous=prev_close if prev_close is not None else close,
            open_price=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=close,
            volume=volume,
            approx_value=close * volume,
        )
        bars.append(bar)
        prev_close = close

    return bars


if __name__ == "__main__":
    # Quick manual test: python -m data_source.yahoo_client
    test_code = "BBCA"
    print(f"Fetching {test_code}...")
    bars = fetch_trading_info(test_code, length=15)
    for b in bars:
        print(f"{b.date}: Close={b.close} Vol={b.volume} %chg={b.pct_change:.2f}%")
