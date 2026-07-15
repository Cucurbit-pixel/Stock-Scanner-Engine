import streamlit as st
import json
import time

st.set_page_config(page_title="美股智能掃描器", page_icon="📈", layout="wide")

# ===================== 自動刷新 =====================
st.markdown(
    """
    <meta http-equiv="refresh" content="120">
    """,
    unsafe_allow_html=True
)
# 每 120 秒自動刷新一次（可改數字）

st.title("📈 美股智能掃描器 Dashboard")
st.caption("每日自動掃描 + Discord 警報")

# 手動刷新按鈕
if st.button("🔄 手動刷新", use_container_width=True):
    st.rerun()

try:
    with open("latest_scan.json", "r", encoding="utf-8") as f:
        data = json.load(f)
except FileNotFoundError:
    st.error("尚未有掃描結果。請先運行 scanner.py")
    st.stop()

st.success(f"最後掃描時間：{data['scan_time']} ｜ VIX：{data['vix']}")

triggered = [r for r in data["results"] if r["composite"]["score"] >= 80]

if not triggered:
    st.info("今日沒有達到 80 分的股票。")
else:
    st.subheader(f"今日觸發股票（共 {len(triggered)} 檔）")

    # 用 2 欄排版
    cols = st.columns(2)

    for idx, stock in enumerate(triggered):
        with cols[idx % 2]:
            with st.container(border=True):
                # 標題
                st.markdown(f"### ✅ {stock['name']} ({stock['code']})")

                score = stock['composite']['score']
                is_bullish = not stock['risk']['is_short']

                # 評分 + 方向
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("評分", f"{score}")
                with col2:
                    direction = "🔺 多頭" if is_bullish else "🔻 空頭"
                    st.metric("方向", direction)

                # 訊號
                st.markdown(f"**訊號**：{stock['composite']['emoji']} {stock['composite']['recommendation']}")

                # 建議倉位 + 現價
                st.markdown(f"**建議倉位**：**{stock['risk']['kelly_pct']}%**")
                st.markdown(f"**現價**：**${stock['price']:.2f}**")

                # 展開詳細風險控制
                with st.expander("風險控制詳情"):
                    st.write(f"入場：${stock['risk']['entry']:.2f}")
                    st.write(f"止盈：${stock['risk']['take_profit']:.2f}")
                    st.write(f"止損：${stock['risk']['stop_loss']:.2f}")
                    st.write(f"RS Rating：{stock['indicators'].get('rs_rating', 'N/A')}")