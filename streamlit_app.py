import streamlit as st
import json

st.set_page_config(page_title="美股智能掃描器", page_icon="📈", layout="wide")

st.title("📈 美股智能掃描器 Dashboard")
st.caption("每日自動掃描 + Discord 警報")

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

    for stock in triggered:
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"### ✅ {stock['name']} ({stock['code']})")
                st.markdown(f"**評分**：**{stock['composite']['score']}**")
                direction = "🔺 多頭（Long）" if not stock['risk']['is_short'] else "🔻 空頭（Short）"
                st.markdown(f"**方向**：{direction}")
                st.markdown(f"**訊號**：{stock['composite']['emoji']} ({stock['composite']['recommendation']})")

            with col2:
                st.metric("建議倉位", f"{stock['risk']['kelly_pct']}%")
                st.metric("現價", f"${stock['price']:.2f}")

            with st.expander("詳細風險控制"):
                st.write(f"入場：${stock['risk']['entry']:.2f}")
                st.write(f"止盈：${stock['risk']['take_profit']:.2f}")
                st.write(f"止損：${stock['risk']['stop_loss']:.2f}")
                st.write(f"RS Rating：{stock['indicators'].get('rs_rating', 'N/A')}")