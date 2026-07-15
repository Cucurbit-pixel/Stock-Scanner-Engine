import streamlit as st
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

st.set_page_config(page_title="美股智能掃描器", page_icon="📈", layout="wide")

st.markdown("""<meta http-equiv="refresh" content="90">""", unsafe_allow_html=True)

st.title("📊 美股每日智能掃描")
st.caption("每日自動掃描 + Discord 警報 + 風險控制")

if st.button("🔄 手動刷新", use_container_width=True):
    st.rerun()

# ===================== Greed & Fear Index（置中 + 更好看） =====================
@st.cache_data(ttl=3600)
def get_fear_greed_index():
    try:
        url = "https://www.cnn.com/markets/fear-and-greed"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        fear_greed = soup.find("div", {"class": "fear-greed-index"})
        if fear_greed:
            value = fear_greed.find("span", {"class": "index-value"}).text.strip()
            return int(value)
        return 50
    except:
        return 50

fear_greed_value = get_fear_greed_index()

st.subheader("市場情緒指數（CNN Greed & Fear）")

# 置中顯示
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if fear_greed_value >= 75:
        emoji = "🟢"
        status = "極度貪婪"
        color = "normal"
    elif fear_greed_value >= 55:
        emoji = "🟡"
        status = "貪婪"
        color = "normal"
    elif fear_greed_value >= 45:
        emoji = "⚪"
        status = "中性"
        color = "off"
    elif fear_greed_value >= 25:
        emoji = "🟠"
        status = "恐懼"
        color = "normal"
    else:
        emoji = "🔴"
        status = "極度恐懼"
        color = "normal"

    st.metric(label="Greed & Fear Index", value=f"{fear_greed_value} {emoji}")
    st.markdown(f"**目前狀態：{status}**")

# ===================== 載入掃描結果 =====================
try:
    with open("latest_scan.json", "r", encoding="utf-8") as f:
        data = json.load(f)
except FileNotFoundError:
    st.error("尚未有掃描結果")
    st.stop()

# 時間轉香港時間
scan_time_str = data['scan_time']
try:
    utc_time = datetime.strptime(scan_time_str, "%Y-%m-%d %H:%M:%S")
    hkt_time = utc_time + timedelta(hours=8)
    display_time = hkt_time.strftime("%Y-%m-%d %H:%M:%S")
except:
    display_time = scan_time_str

st.success(f"最後掃描時間（香港時間）：{display_time} ｜ VIX：{data['vix']}")

triggered = [r for r in data["results"] if r["composite"]["score"] >= 80]

if not triggered:
    st.info("今日沒有達到 80 分的股票。")
else:
    st.subheader(f"今日觸發股票（共 {len(triggered)} 檔）")

    # 使用 1 欄，卡片更緊湊
    for stock in triggered:
        with st.container(border=True):
            ticker = stock['code'].lower()
            logo_url = f"https://logo.clearbit.com/{ticker}.com"

            # Logo + 名稱
            col_logo, col_info = st.columns([1, 6])
            with col_logo:
                try:
                    st.image(logo_url, width=40)
                except:
                    st.write("📈")

            with col_info:
                st.markdown(f"**{stock['name']} ({stock['code']})**")

            score = stock['composite']['score']
            is_bullish = not stock['risk']['is_short']

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("評分", f"{score}")
            with col2:
                direction = "🔺 多頭" if is_bullish else "🔻 空頭"
                st.metric("方向", direction)
            with col3:
                st.metric("建議倉位", f"{stock['risk']['kelly_pct']}%")

            st.markdown(f"**訊號**：{stock['composite']['emoji']} {stock['composite']['recommendation']}")
            st.markdown(f"**現價**：**${stock['price']:.2f}**")

            with st.expander("風險控制詳情"):
                st.write(f"入場：${stock['risk']['entry']:.2f}")
                st.write(f"止盈：${stock['risk']['take_profit']:.2f}")
                st.write(f"止損：${stock['risk']['stop_loss']:.2f}")
                st.write(f"RS Rating：{stock['indicators'].get('rs_rating', 'N/A')}")