import streamlit as st
import json
from datetime import datetime, timedelta

st.set_page_config(page_title="美股智能掃描器", page_icon="📈", layout="wide")

# 自動刷新
st.markdown("""<meta http-equiv="refresh" content="90">""", unsafe_allow_html=True)

st.title("📊 美股每日智能掃描")
st.caption("每日自動掃描 + Discord 警報 + 風險控制")

if st.button("🔄 手動刷新", use_container_width=True):
    st.rerun()

# ===================== Greed & Fear Index（置中 + 更好看） =====================
st.subheader("市場情緒指數（CNN Greed & Fear）")

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    # 暫時用固定值 50 做示範（之後可以接真實 API）
    fear_greed = 50
    st.metric("Greed & Fear Index", f"{fear_greed} ⚪")
    st.markdown("**目前狀態：中性**")

# ===================== 載入掃描結果 =====================
try:
    with open("latest_scan.json", "r", encoding="utf-8") as f:
        data = json.load(f)
except:
    st.error("尚未有掃描結果")
    st.stop()

# 時間轉香港時間
try:
    utc_time = datetime.strptime(data['scan_time'], "%Y-%m-%d %H:%M:%S")
    hkt_time = utc_time + timedelta(hours=8)
    display_time = hkt_time.strftime("%Y-%m-%d %H:%M:%S")
except:
    display_time = data['scan_time']

st.success(f"最後掃描時間（香港時間）：{display_time} ｜ VIX：{data['vix']}")

triggered = [r for r in data["results"] if r["composite"]["score"] >= 80]

if not triggered:
    st.info("今日沒有達到 80 分的股票。")
else:
    st.subheader(f"今日觸發股票（共 {len(triggered)} 檔）")

    for stock in triggered:
        with st.container(border=True):
            ticker = stock['code'].lower()
            logo_url = f"https://logo.clearbit.com/{ticker}.com"

            # Logo + 名稱
            col1, col2 = st.columns([1, 5])
            with col1:
                try:
                    st.image(logo_url, width=38)
                except:
                    st.write("📈")

            with col2:
                st.markdown(f"**{stock['name']} ({stock['code']})**")

            score = stock['composite']['score']
            is_bullish = not stock['risk']['is_short']

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("評分", score)
            with c2:
                direction = "🔺 多頭" if is_bullish else "🔻 空頭"
                st.metric("方向", direction)
            with c3:
                st.metric("倉位", f"{stock['risk']['kelly_pct']}%")

            st.markdown(f"**訊號**：{stock['composite']['emoji']} {stock['composite']['recommendation']}")
            st.markdown(f"**現價**：**${stock['price']:.2f}**")

            with st.expander("風險控制詳情"):
                st.write(f"入場：${stock['risk']['entry']:.2f}")
                st.write(f"止盈：${stock['risk']['take_profit']:.2f}")
                st.write(f"止損：${stock['risk']['stop_loss']:.2f}")