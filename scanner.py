#!/usr/bin/env python3
"""
智能搜尋引擎 v7.2（已修復 KeyError: 'emoji'）
"""

import os
import sys
import logging
import threading
import warnings
import concurrent.futures
from typing import Any, Dict, List, Tuple, Optional

import requests
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

warnings.filterwarnings("ignore")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class Config:
    API_TIMEOUT = int(os.environ.get("API_TIMEOUT", "20"))
    MAX_WORKERS = 12
    DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")
    NOTIFY_THRESHOLD = 80.0

    STOCKS = [
        {"code": "MU", "name": "美光科技"}, {"code": "WDC", "name": "Western Digital"},
        {"code": "STX", "name": "Seagate"}, {"code": "AVGO", "name": "博通"},
        {"code": "AMD", "name": "超微"}, {"code": "INTC", "name": "英特爾"},
        {"code": "QCOM", "name": "高通"}, {"code": "RMBS", "name": "Rambus"},
        {"code": "LRCX", "name": "Lam Research"}, {"code": "KLAC", "name": "KLA"},
        {"code": "AMAT", "name": "Applied Materials"}, {"code": "TER", "name": "Teradyne"},
        {"code": "PLAB", "name": "Photronics"}, {"code": "GLW", "name": "Corning"},
        {"code": "AAOI", "name": "Applied Optoelectronics"}, {"code": "LITE", "name": "Lumentum"},
        {"code": "COHR", "name": "Coherent"}, {"code": "MTSI", "name": "MACOM"},
        {"code": "VIAV", "name": "Viavi Solutions"}, {"code": "NVDA", "name": "英偉達"},
        {"code": "AAPL", "name": "蘋果"}, {"code": "MSFT", "name": "微軟"},
        {"code": "AMZN", "name": "亞馬遜"}, {"code": "META", "name": "Meta"},
        {"code": "GOOGL", "name": "谷歌"}, {"code": "TSLA", "name": "特斯拉"},
        {"code": "COST", "name": "好市多"}, {"code": "NFLX", "name": "Netflix"},
        {"code": "ADBE", "name": "Adobe"}, {"code": "CRM", "name": "Salesforce"},
        {"code": "PLTR", "name": "Palantir"}, {"code": "SNOW", "name": "Snowflake"},
        {"code": "COIN", "name": "Coinbase"}, {"code": "UBER", "name": "Uber"},
        {"code": "PYPL", "name": "PayPal"}, {"code": "DIS", "name": "迪士尼"},
        {"code": "JPM", "name": "摩根大通"}, {"code": "V", "name": "Visa"},
    ]

    LOGO_MAP = {
        "NVDA": "nvidia.com", "AAPL": "apple.com", "MSFT": "microsoft.com",
        "AMZN": "amazon.com", "META": "meta.com", "GOOGL": "google.com",
        "TSLA": "tesla.com", "MU": "micron.com", "WDC": "wdc.com",
        "STX": "seagate.com", "AVGO": "broadcom.com", "AMD": "amd.com",
        "INTC": "intel.com", "QCOM": "qualcomm.com", "COST": "costco.com",
        "NFLX": "netflix.com", "ADBE": "adobe.com", "CRM": "salesforce.com",
        "PLTR": "palantir.com", "SNOW": "snowflake.com", "COIN": "coinbase.com",
        "UBER": "uber.com", "PYPL": "paypal.com", "DIS": "disney.com",
        "JPM": "jpmorganchase.com", "V": "visa.com", "GLW": "corning.com",
        "AAOI": "aaoi.com", "LITE": "lumentum.com", "COHR": "coherent.com",
        "MTSI": "macom.com", "VIAV": "viavisolutions.com",
    }


class SessionManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    obj = super().__new__(cls)
                    obj.session = cls._create_session()
                    cls._instance = obj
        return cls._instance

    @staticmethod
    def _create_session():
        session = requests.Session()
        retry = Retry(total=4, backoff_factor=0.6, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=Config.MAX_WORKERS * 2)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def get(self, *args, **kwargs): return self.session.get(*args, **kwargs)
    def post(self, *args, **kwargs): return self.session.post(*args, **kwargs)


SESSION = SessionManager()


class TaskRepeater:
    @staticmethod
    def fetch_data(ticker: str, period: str = "2y") -> pd.DataFrame:
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
        params = {"interval": "1d", "range": period}
        headers = {"User-Agent": "Mozilla/5.0"}

        resp = SESSION.get(url, params=params, headers=headers, timeout=Config.API_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json().get("chart", {})

        if payload.get("error"):
            raise ValueError(f"Yahoo API Error for {ticker}")

        result = payload.get("result", [{}])[0]
        quote = result.get("indicators", {}).get("quote", [{}])[0]

        df = pd.DataFrame({
            col: quote.get(col, []) for col in ["close", "high", "low", "open", "volume"]
        }).dropna()

        if df.empty:
            raise ValueError(f"No valid data for {ticker}")
        return df

    @staticmethod
    def fetch_benchmark() -> Optional[pd.DataFrame]:
        try:
            return TaskRepeater.fetch_data("QQQ", period="1y")
        except Exception as e:
            logger.warning(f"無法獲取 QQQ 數據: {e}")
            return None

    @staticmethod
    def calculate_macd(closes: pd.Series) -> Dict[str, Any]:
        if len(closes) < 35:
            return {"status": "數據不足", "signal_strength": 0}

        ema_fast = closes.ewm(span=12, adjust=False).mean()
        ema_slow = closes.ewm(span=26, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line

        golden_cross = any(
            macd_line.iloc[i-1] < signal_line.iloc[i-1] and macd_line.iloc[i] >= signal_line.iloc[i]
            for i in range(max(1, len(macd_line) - 5), len(macd_line))
        )
        death_cross = any(
            macd_line.iloc[i-1] > signal_line.iloc[i-1] and macd_line.iloc[i] <= signal_line.iloc[i]
            for i in range(max(1, len(macd_line) - 5), len(macd_line))
        )

        if golden_cross:
            return {"status": "金叉 📈", "signal_strength": 2}
        elif death_cross:
            return {"status": "死叉 📉", "signal_strength": -2}
        elif histogram.iloc[-1] > 0:
            return {"status": "多頭動能", "signal_strength": 1}
        elif histogram.iloc[-1] < 0:
            return {"status": "空頭動能", "signal_strength": -1}
        else:
            return {"status": "中性", "signal_strength": 0}

    @staticmethod
    def calculate_rs_rating(stock_df: pd.DataFrame, benchmark_df: Optional[pd.DataFrame]) -> int:
        if benchmark_df is None or len(stock_df) < 200 or len(benchmark_df) < 200:
            return 50
        try:
            stock_return = (stock_df["close"].iloc[-1] / stock_df["close"].iloc[0] - 1) * 100
            bench_return = (benchmark_df["close"].iloc[-1] / benchmark_df["close"].iloc[0] - 1) * 100
            relative = stock_return - bench_return
            return int(max(1, min(99, round(50 + relative * 1.8))))
        except Exception:
            return 50

    @staticmethod
    def calculate_indicators(df: pd.DataFrame, benchmark_df: Optional[pd.DataFrame]) -> Dict[str, Any]:
        closes = df["close"]
        current = float(closes.iloc[-1])

        sma20 = closes.rolling(20).mean().iloc[-1]
        sma50 = closes.rolling(50).mean().iloc[-1]
        sma200 = closes.rolling(200).mean().iloc[-1]

        trend_sig = 3 if sma20 > sma50 > sma200 else -3 if sma20 < sma50 < sma200 else 0
        align = "多頭排列" if trend_sig == 3 else "空頭排列" if trend_sig == -3 else "震盪整理"

        alpha = 1.0 / 14
        deltas = closes.diff()
        avg_up = deltas.clip(lower=0).fillna(0).ewm(alpha=alpha, adjust=False).mean().iloc[-1]
        avg_down = (-deltas.clip(upper=0)).fillna(0).ewm(alpha=alpha, adjust=False).mean().iloc[-1]

        if avg_down == 0:
            rsi_val = 100 if avg_up > 0 else 50
        elif avg_up == 0:
            rsi_val = 0
        else:
            rsi_val = 100 - (100 / (1 + avg_up / avg_down))

        rsi_sig = 3 if rsi_val <= 30 else -3 if rsi_val >= 70 else 0

        high_max = df["high"].rolling(20).max().iloc[-1]
        low_min = df["low"].rolling(20).min().iloc[-1]
        atr_pct = (high_max - low_min) / current if current > 0 else 0.03

        macd_data = TaskRepeater.calculate_macd(closes)
        rs_rating = TaskRepeater.calculate_rs_rating(df, benchmark_df)

        return {
            "trend": {"alignment": align, "signal": trend_sig},
            "rsi": {"rsi": round(rsi_val, 1), "signal": rsi_sig},
            "macd": macd_data,
            "rs_rating": rs_rating,
            "atr_pct": round(atr_pct, 4)
        }


class DecisionBoard:
    @staticmethod
    def evaluate_score(indicators: Dict[str, Any]) -> Dict[str, Any]:
        trend_sig = indicators["trend"]["signal"]
        rsi_sig = indicators["rsi"]["signal"]
        macd_strength = indicators["macd"]["signal_strength"]
        rs_rating = indicators.get("rs_rating", 50)

        score = 50 + (trend_sig * 8) + (rsi_sig * 6) + (macd_strength * 7)

        if rs_rating >= 90: score += 18
        elif rs_rating >= 80: score += 12
        elif rs_rating >= 70: score += 6

        score = max(0, min(100, round(score, 1)))

        if score >= 80:
            rec, emoji = "STRONG_BUY", "🚀🚀🚀"
        elif score >= 65:
            rec, emoji = "BUY", "🚀🚀"
        elif score >= 45:
            rec, emoji = "NEUTRAL", "➡️"
        else:
            rec, emoji = "SELL", "🔻🔻"

        return {"score": score, "recommendation": rec, "emoji": emoji}

    @staticmethod
    def calculate_risk(price: float, score: float, rec: str, atr_pct: float, vix: float) -> Dict[str, Any]:
        is_short = rec == "SELL"

        if not is_short:
            entry = price * 0.98
            stop_loss = entry * 0.95
            take_profit = entry * 1.08
        else:
            entry = price * 1.02
            stop_loss = entry * 1.05
            take_profit = entry * 0.92

        win_rate = max(0.35, min(0.75, score / 100))
        actual_rr = abs(take_profit - entry) / abs(entry - stop_loss) if stop_loss != entry else 2.0

        kelly = (win_rate * actual_rr - (1 - win_rate)) / actual_rr * 0.3 if actual_rr > 0 else 0

        vol_factor = max(0.4, min(1.2, 0.04 / atr_pct)) if atr_pct > 0 else 1.0
        vix_factor = 0.5 if vix > 30 else 0.7 if vix > 25 else 0.9 if vix > 20 else 1.0

        kelly = max(0.0, min(0.30, kelly * vol_factor * vix_factor))

        return {
            "entry": round(entry, 2),
            "stop_loss": round(stop_loss, 2),
            "take_profit": round(take_profit, 2),
            "kelly_pct": round(kelly * 100, 1),
            "is_short": is_short,
            "risk_note": f"VIX乘數:{vix_factor:.1f}"
        }


class WorkflowMapper:
    @staticmethod
    def _process_single_stock(stock: Dict[str, str], vix: float, benchmark_df: Optional[pd.DataFrame]) -> Optional[Dict[str, Any]]:
        try:
            df = TaskRepeater.fetch_data(stock["code"])
            price = float(df["close"].iloc[-1])
            indicators = TaskRepeater.calculate_indicators(df, benchmark_df)
            composite = DecisionBoard.evaluate_score(indicators)
            risk = DecisionBoard.calculate_risk(price, composite["score"], composite["recommendation"], indicators["atr_pct"], vix)
            return {**stock, "price": price, "indicators": indicators, "composite": composite, "risk": risk}
        except Exception as e:
            logger.error(f"❌ 處理 {stock['code']} 失敗: {str(e)[:80]}")
            return None

    @staticmethod
    def trigger_run() -> Tuple[List[Dict], float]:
        try:
            vix_df = TaskRepeater.fetch_data("^VIX", period="6mo")
            vix = round(float(vix_df["close"].iloc[-1]), 2)
        except:
            vix = 20.0

        benchmark_df = TaskRepeater.fetch_benchmark()

        logger.info(f"🚀 開始並行分析（共 {len(Config.STOCKS)} 檔）| VIX: {vix}")

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=Config.MAX_WORKERS) as executor:
            future_to_stock = {
                executor.submit(WorkflowMapper._process_single_stock, stock, vix, benchmark_df): stock
                for stock in Config.STOCKS
            }
            for future in concurrent.futures.as_completed(future_to_stock):
                result = future.result()
                if result:
                    results.append(result)

        logger.info(f"✅ 完成 {len(results)}/{len(Config.STOCKS)} 檔")
        return results, vix


class RunnerHome:
    @staticmethod
    def runner_cowork_discord(results: List[Dict], vix: float):
        if not Config.DISCORD_WEBHOOK:
            return

        high_score = sorted(
            [r for r in results if r["composite"]["score"] >= Config.NOTIFY_THRESHOLD],
            key=lambda x: x["composite"]["score"],
            reverse=True
        )

        if not high_score:
            logger.info(f"沒有達到通知門檻 (≥{Config.NOTIFY_THRESHOLD}) 的股票。")
            return

        embeds = []
        for r in high_score[:5]:
            comp = r["composite"]
            risk = r["risk"]
            ind = r.get("indicators", {})
            is_short = risk.get("is_short", False)

            direction = "🔻 空頭（Short）" if is_short else "🔺 多頭（Long）"
            direction_emoji = "🔻" if is_short else "▲"
            rec_cn = "強烈買入" if comp["recommendation"] == "STRONG_BUY" else "買入" if comp["recommendation"] == "BUY" else "中性"

            macd_status = ind.get("macd", {}).get("status", "")
            macd_line = f"• MACD : {macd_status}\n" if ("金叉" in macd_status or "死叉" in macd_status) else ""

            tech = (
                f"• 趨勢 : {ind.get('trend', {}).get('alignment', '震盪整理')}\n"
                f"• RSI : {ind.get('rsi', {}).get('rsi', 50)}（{ind.get('rsi', {}).get('state', '中立')}）\n"
                f"{macd_line}"
                f"• RS Rating : {ind.get('rs_rating', 50)}"
            )

            domain = Config.LOGO_MAP.get(r["code"])
            logo_url = f"https://logo.clearbit.com/{domain}" if domain else None

            desc = (
                f"評分 : {comp['score']}\n"
                f"方向 : {direction_emoji} {direction}\n"
                f"訊號 : {comp['emoji']} ({rec_cn})\n\n"
                f"【技術面 摘要】\n{tech}\n\n"
                f"【風險控制】\n"
                f"• 現價 : ${r['price']:.2f}\n"
                f"• 入場 : ${risk['entry']:.2f}\n"
                f"• 止盈 : ${risk['take_profit']:.2f}\n"
                f"• 止損 : ${risk['stop_loss']:.2f}\n\n"
                f"建議倉位 : {risk['kelly_pct']:.1f}%\n"
                f"市場恐慌 (VIX) : {vix}"
            )

            embed = {
                "title": f"✅ {r['name']} ({r['code']})",
                "description": desc,
                "color": 0xFF1744 if is_short else 0x00C853,
                "footer": {"text": f"VIX: {vix} | RS Rating 參考 QQQ"}
            }
            if logo_url:
                embed["thumbnail"] = {"url": logo_url}

            embeds.append(embed)

        try:
            SESSION.post(Config.DISCORD_WEBHOOK, json={"embeds": embeds}, timeout=12)
            logger.info(f"✓ Discord 推播成功（{len(embeds)} 檔）")
        except Exception as e:
            logger.error(f"Discord 推送失敗: {e}")


def main():
    if os.environ.get("GITHUB_ACTIONS") == "true":
        logger.info("🤖 智能搜尋引擎 v7.2 啟動")
        results, vix = WorkflowMapper.trigger_run()
        RunnerHome.runner_cowork_discord(results, vix)
    else:
        logger.warning("請使用 GitHub Actions 運行")


if __name__ == "__main__":
    main()