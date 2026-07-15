#!/usr/bin/env python3
"""
智能搜尋引擎 · VIX 整合版（極簡實戰版）
"""

import os
import sys
import time
import random
import logging
import threading
import warnings
import concurrent.futures
from datetime import datetime, timezone

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
    MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "10"))
    DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")
    NOTIFY_SCORE_THRESHOLD = 80.0
    KELLY_BASE = 0.3

    STOCKS = [
        {"code": "MU", "name": "美光"}, {"code": "WDC", "name": "Western Digital"},
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


class SimpleRateLimiter:
    def __init__(self, delay=0.1):
        self.delay = delay
        self.last_req = 0.0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = time.time()
            if now - self.last_req < self.delay:
                time.sleep(self.delay - (now - self.last_req))
            self.last_req = time.time()


class SessionManager:
    _instance = None
    _lock = threading.Lock()
    rate_limiter = SimpleRateLimiter(delay=0.1)

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
        retry = Retry(total=3, backoff_factor=0.8, status_forcelist=[403, 429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=Config.MAX_WORKERS * 2)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def get(self, url, **kwargs):
        self.rate_limiter.wait()
        headers = kwargs.pop("headers", {})
        headers.update({
            "User-Agent": random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"
            ]),
            "Accept": "application/json"
        })
        return self.session.get(url, headers=headers, **kwargs)

    def post(self, url, **kwargs):
        return self.session.post(url, **kwargs)


SESSION = SessionManager()


class TaskRepeater:
    @staticmethod
    def fetch_data(ticker):
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
        resp = SESSION.get(url, params={"interval": "1d", "range": "1y"}, timeout=Config.API_TIMEOUT)
        resp.raise_for_status()

        result = resp.json().get("chart", {}).get("result", [])
        if not result or result[0].get("error"):
            raise ValueError("API 回傳異常")

        quote = result[0]["indicators"]["quote"][0]
        df = pd.DataFrame({
            "close": quote.get("close", []),
            "high": quote.get("high", []),
            "low": quote.get("low", [])
        }).dropna()

        if len(df) < 180:
            raise ValueError("歷史資料不足")

        return df.reset_index(drop=True)

    @staticmethod
    def fetch_vix():
        try:
            resp = SESSION.get(
                "https://query2.finance.yahoo.com/v8/finance/chart/^VIX",
                params={"interval": "1d", "range": "1d"},
                timeout=Config.API_TIMEOUT
            )
            return round(float(resp.json()["chart"]["result"][0]["meta"]["regularMarketPrice"]), 2)
        except Exception:
            logger.warning("VIX 獲取失敗，使用預設值 20.0")
            return 20.0


class TechnicalEngine:
    @staticmethod
    def calculate_rsi(closes, period=14):
        delta = closes.diff()
        up = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
        down = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()

        last_down = down.iloc[-1]
        if last_down == 0:
            return 100.0 if up.iloc[-1] > 0 else 50.0

        rs = up.iloc[-1] / last_down
        return float(100.0 - (100.0 / (1.0 + rs)))

    @staticmethod
    def evaluate_stock(df, price, vix):
        closes = df["close"]
        current = float(closes.iloc[-1])

        sma20 = closes.rolling(20).mean().iloc[-1]
        sma50 = closes.rolling(50).mean().iloc[-1]
        sma200 = closes.rolling(200).mean().iloc[-1]

        trend_sig = 3 if sma20 > sma50 > sma200 else -3 if sma20 < sma50 < sma200 else 0
        align = "多頭排列" if trend_sig == 3 else "空頭排列" if trend_sig == -3 else "震盪整理"

        rsi = TechnicalEngine.calculate_rsi(closes)
        rsi_sig = 3 if rsi <= 30 else -3 if rsi >= 70 else 0
        rsi_state = "超賣" if rsi_sig == 3 else "超買" if rsi_sig == -3 else "中立"

        high_20 = df["high"].rolling(20).max().iloc[-1]
        low_20 = df["low"].rolling(20).min().iloc[-1]
        atr_pct = (high_20 - low_20) / current if current > 0 else 0.03

        indicators = {
            "trend": {"alignment": align, "signal": trend_sig},
            "rsi": {"rsi": round(rsi, 1), "state": rsi_state}
        }

        score = max(0, min(100, 50 + trend_sig * 10 + rsi_sig * 5))
        rules = [(75, "STRONG_BUY", "🚀🚀🚀"), (60, "BUY", "🚀🚀"), (50, "WEAK_BUY", "🚀"),
                 (45, "NEUTRAL", "➡️"), (30, "WEAK_SELL", "🔻"), (15, "SELL", "🔻🔻")]
        rec, emoji = next(((r, e) for t, r, e in rules if score >= t), ("STRONG_SELL", "🔻🔻🔻"))
        composite = {"score": round(score, 1), "recommendation": rec, "emoji": emoji}

        is_short = rec in {"WEAK_SELL", "SELL", "STRONG_SELL"}
        entry = price * (1.02 if is_short else 0.98)
        stop_loss = entry * (1.05 if is_short else 0.95)
        take_profit = entry * (0.92 if is_short else 1.08)

        win_rate = max(0.35, min(0.75, score / 100))
        risk_amt = max(abs(entry - stop_loss), entry * 0.005)
        rr = abs(take_profit - entry) / risk_amt
        kelly = max(0, min(0.30, ((win_rate * rr) - (1 - win_rate)) / rr * Config.KELLY_BASE)) if rr > 0 else 0

        vol_factor = max(0.4, min(1.2, 0.04 / atr_pct)) if atr_pct > 0 else 1.0
        vix_factor = 0.5 if vix > 30 else 0.7 if vix > 25 else 0.9 if vix > 20 else 1.0
        final_kelly = round(kelly * vol_factor * vix_factor * 100, 1)

        risk = {
            "entry": round(entry, 2),
            "stop_loss": round(stop_loss, 2),
            "take_profit": round(take_profit, 2),
            "kelly_pct": final_kelly,
            "is_short": is_short,
            "vix_factor": round(vix_factor, 2),
            "risk_note": f"VIX乘數:{vix_factor:.1f}"
        }

        return indicators, composite, risk


class WorkflowMapper:
    @staticmethod
    def _process_single_stock(stock, vix):
        try:
            df = TaskRepeater.fetch_data(stock["code"])
            price = float(df["close"].iloc[-1])
            indicators, composite, risk = TechnicalEngine.evaluate_stock(df, price, vix)
            logger.info(f"✅ {stock['code']:<5} | 評分: {composite['score']:5.1f} {composite['emoji']}")
            return {**stock, "price": price, "indicators": indicators, "composite": composite, "risk": risk}
        except Exception as e:
            logger.warning(f"⚠️ {stock['code']} 失敗: {str(e)[:50]}")
            return None

    @staticmethod
    def trigger_run():
        vix = TaskRepeater.fetch_vix()
        results = []

        logger.info(f"🚀 開始分析（VIX: {vix}）")

        with concurrent.futures.ThreadPoolExecutor(max_workers=Config.MAX_WORKERS) as executor:
            futures = [executor.submit(WorkflowMapper._process_single_stock, stock, vix) for stock in Config.STOCKS]
            for future in concurrent.futures.as_completed(futures):
                if res := future.result():
                    results.append(res)

        return results, vix


class RunnerHome:
    @staticmethod
    def runner_cowork_discord(results, vix):
        if not Config.DISCORD_WEBHOOK:
            return

        top = sorted([r for r in results if r["composite"]["score"] >= Config.NOTIFY_SCORE_THRESHOLD],
                     key=lambda x: x["composite"]["score"], reverse=True)[:5]

        if not top:
            logger.info("今日無達標推薦。")
            return

        embeds = []
        for r in top:
            comp, risk, ind = r["composite"], r["risk"], r["indicators"]
            is_short = risk["is_short"]

            # 方向與訊號文字
            direction = "空頭（Short）" if is_short else "多頭（Long）"
            signal_text = "強烈沽空" if is_short else "強烈買入"

            tech = f"• 趨勢：`{ind['trend']['alignment']}`\n• RSI：`{ind['rsi']['rsi']}` ({ind['rsi']['state']})"

            domain = Config.LOGO_MAP.get(r["code"])
            logo = f"https://logo.clearbit.com/{domain}" if domain else None

            # 新格式描述
            desc = f"""**評分：** **`{comp['score']}`**  
**方向：** {direction}  
**訊號：** {comp['emoji']}（{signal_text}）

**【技術面 摘要】**
{tech}

**【風險控制】**
• 現價：`${r['price']:,.2f}`
• 入場：`${risk['entry']:,.2f}`
• 止盈：`${risk['take_profit']:,.2f}`
• 止損：`${risk['stop_loss']:,.2f}`

**建議倉位：** `{risk['kelly_pct']:.1f}%`  
**市場恐慌（VIX）：** `{vix}`"""

            embed = {
                "title": f"📈 {r['name']} ({r['code']})",
                "description": desc,
                "color": 0xFF0000 if is_short else 0x00FF41
            }
            if logo:
                embed["thumbnail"] = {"url": logo}

            embeds.append(embed)

        try:
            SESSION.post(Config.DISCORD_WEBHOOK, json={"embeds": embeds}, timeout=15)
            logger.info(f"✅ Discord 推播成功（{len(embeds)} 檔）")
        except Exception as e:
            logger.error(f"Discord 推播失敗: {e}")

    @staticmethod
    def print_local_results(results, vix):
        logger.info("\n" + "="*70)
        logger.info(f"📊 本地分析結果（VIX: {vix}）")
        logger.info("="*70)
        for i, r in enumerate(sorted(results, key=lambda x: x["composite"]["score"], reverse=True)[:8], 1):
            logger.info(
                f"{i}. {r['code']:<5} | 價: ${r['price']:<8.2f} | "
                f"評分: {r['composite']['score']:5.1f} {r['composite']['emoji']} | "
                f"Kelly: {r['risk']['kelly_pct']:5.1f}%"
            )
        logger.info("="*70 + "\n")


def main():
    logger.info("🤖 智能搜尋引擎啟動...")
    start = time.time()

    try:
        results, vix = WorkflowMapper.trigger_run()
        if results:
            RunnerHome.print_local_results(results, vix)
            if Config.DISCORD_WEBHOOK:
                RunnerHome.runner_cowork_discord(results, vix)
        logger.info(f"🏁 執行完成，耗時 {time.time() - start:.1f}s")
    except Exception as e:
        logger.error(f"執行錯誤: {e}", exc_info=True)


if __name__ == "__main__":
    main()