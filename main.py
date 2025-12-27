import feedparser
import requests
from datetime import datetime
import pytz
import os
import anthropic
from bs4 import BeautifulSoup

# 환경변수
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
WP_URL = os.environ.get("WP_URL")
WP_USER = os.environ.get("WP_USER")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# RSS 피드 목록 (속보/이슈/정치 중심)
RSS_FEEDS = [
    ("연합뉴스 속보", "https://www.yna.co.kr/rss/news.xml"),
    ("연합뉴스 정치", "https://www.yna.co.kr/rss/politics.xml"),
    ("SBS 정치", "https://news.sbs.co.kr/news/rss/rss_01.xml"),
    ("MBC 정치", "https://imnews.imbc.com/rss/news/news_01.xml"),
    ("KBS 정치", "https://world.kbs.co.kr/rss/rss_news.htm?lang=k"),
    ("조선일보", "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("중앙일보", "https://rss.joins.com/joins_news_list.xml"),
    ("구글뉴스 국회", "https://news.google.com/rss/search?q=국회+여야+민주당+국민의힘&hl=ko&gl=KR&ceid=KR:ko"),
    ("구글뉴스 정치이슈", "https://news.google.com/rss/search?q=이재명+한덕수+윤석열&hl=ko&gl=KR&ceid=KR:ko"),
]

def fetch_news():
    all_news = []
    for source_name, feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                all_news.append({
                    "source": source_name,
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", entry.get("description", "")),
                })
        except Exception as e:
            print(f"[ERROR] {source_name} 피드 수집 실패: {e}")
    return all_news

def fetch_stock_info():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        kospi_url = "https://finance.naver.com/sise/sise_index.naver?code=KOSPI"
        res = requests.get(kospi_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        kospi = soup.select_one('#now_value').text.strip()
        kospi_change = soup.select_one('#change_value_and_rate').text.strip()
        
        kosdaq_url = "https://finance.naver.com/sise/sise_index.naver?code=KOSDAQ"
        res = requests.get(kosdaq_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        kosdaq = soup.select_one('#now_value').text.strip()
        kosdaq_change = soup.select_one('#change_value_and_rate').text.strip()
        
        exchange_url = "https://finance.naver.com/marketindex/"
        res = requests.get(exchange_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        usd = soup.select_one('.usd .value').text.strip()
        
        return f"코스피 {kospi} ({kospi_change}) | 코스닥 {kosdaq} ({kosdaq_change}) | 원/달러 {usd}원"
    except Exception as e:
        print(f"[ERROR] 주식 정보 수집 실패: {e}")
        return ""

def summarize_with_claude(news_list):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    news_text = ""
    for i, news in enumerate(news_list, 1):
        news_text += f"제목: {news['title']}\n내용: {news['summary']}\n\n"
    
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    weekdays = ['월', '화', '수', '목', '금', '토', '일']
    date_str = f"{now.strftime('%y')}년 {now.strftime('%m')}월 {now.strftime('%d')}일 {weekdays[now.weekday()]}요일"
    
    prompt = f"""너는 실제 뉴스 편집국에서 일하는 편집 기자다.
아래에 여러 개의 뉴스 기사가 주어진다.
이를 바탕으로 아침에 보는 '간추린 뉴스' 형태로 재작성하라.

[작성 규칙]
- 첫 줄: "{date_str} 간추린 뉴스입니다." 로 시작
- 정치 / 경제 / 사회 / 국제 / 연예 / 스포츠 /날씨로 분류해서 묶을 것
- 분류명은 <strong>정치</strong> 형식으로 HTML 굵은 태그 사용
- 정치 5개, 경제 3개, 사회 5개, 국제 3개, 연예, 3개, 스포츠 3개, 날씨 (총 23개 이상)
- 각 뉴스는 "ㆍ" 기호로 시작
- 일반 뉴스는 1~2문장 요약
- 매우 중요한 뉴스는 3~4문장까지 허용
- 기사 제목을 그대로 쓰지 말고 기자가 요약한 문장처럼 작성
- 감정적·선동적 표현 금지, 정보 전달 위주
- 전체 톤은 shortnews.co.kr처럼 차분하고 명확하게
- 오타, 띄워쓰기 확인 필수
- 날씨는 구체적인 기온과 지역별 날씨 정보 포함 (한국 날씨만, 북한 날씨 제외)

[팩트체크 필수 - 직함 및 표기 규칙]
- 트럼프: "미국 대통령" (2025년 1월 20일 취임 완료, "당선인" 표기 금지)
- 이재명: "대통령" 또는 "이재명 대통령" (2025년 5월 취임)
- 윤석열: "전 대통령" 또는 "윤석열 전 대통령" (탄핵 인용)
- 한덕수: 직함 확인 후 정확히 표기
- 바이든: "전 대통령" 또는 "바이든 전 대통령"
- 기타 인물: 현재 직함 기준으로 정확히 표기

[북한 관련 보도 원칙]
- 북한 날씨 정보 포함 금지 (한국 날씨만 보도)
- 북한 체제 미화, 선전성 표현 절대 금지
- 북한 관련 뉴스는 객관적 팩트만 서술
- "북한이 ~했다"는 사실 전달, "북한의 훌륭한~" 같은 평가 금지
- 김정은 관련: 직함 없이 "김정은" 또는 "북한 김정은"으로 표기

[중요: 뉴스 선별 기준]
- 여야 갈등, 국회 공방, 정치권 논란 뉴스 반드시 포함
- 민주당/국민의힘 간 대립, 정쟁, 비판 관련 뉴스 우선 배치
- 현 정부/정권 관련 비판 및 논란 기사 포함
- 속보성 뉴스, 사건사고, 사회 이슈 포함
- 단순 행사/홍보성/기업 보도자료 뉴스는 제외
- 사람들이 관심 가질 만한 핫한 뉴스 위주로 구성
- 북한 선전성 기사, 체제 미화 기사는 제외

[제외할 뉴스 유형]
- 북한 날씨 정보
- 북한 체제/정책을 긍정적으로 묘사하는 기사
- 단순 의전/행사 보도
- 기업 홍보성 보도자료

[입력 데이터]
{news_text}

HTML 형식으로 출력하세요. (p 태그로 문단 구분)"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return message.content[0].text

def send_telegram(title, url):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[SKIP] 텔레그램 설정 없음")
        return
    
    message = f"📰 새 글 발행!\n\n{title}\n\n{url}"
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    try:
        response = requests.post(telegram_url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        })
        if response.status_code == 200:
            print("[SUCCESS] 텔레그램 알림 전송 완료")
        else:
            print(f"[ERROR] 텔레그램 알림 실패: {response.text}")
    except Exception as e:
        print(f"[ERROR] 텔레그램 알림 실패: {e}")

def post_to_wordpress(title, content, stock_info):
    image_url = "https://pub-d5e485446b5c4e8d900036e639bf8d6c.r2.dev/wp-content/uploads/2025/12/newss.jpg"
    full_content = f'<img src="{image_url}" alt="간추린 뉴스" />\n\n{content}\n\n<p><strong>📈 오늘의 증시</strong><br>{stock_info}</p>'
    
    endpoint = f"{WP_URL}/wp-json/wp/v2/posts"
    post_data = {
        "title": title,
        "content": full_content,
        "status": "publish",
        "featured_media": 2801,
        "categories": [127],
    }
    response = requests.post(
        endpoint,
        json=post_data,
        auth=(WP_USER, WP_APP_PASSWORD),
        headers={"Content-Type": "application/json"}
    )
    if response.status_code == 201:
        post_url = response.json().get('link')
        print(f"[SUCCESS] 발행 완료: {post_url}")
        send_telegram(title, post_url)
        return post_url
    else:
        print(f"[ERROR] 발행 실패: {response.status_code} - {response.text}")
        return None

def main():
    print("=== 뉴스 자동 발행 시작 ===")
    news_list = fetch_news()
    print(f"[1/4] {len(news_list)}개 뉴스 수집 완료")
    
    if not news_list:
        print("[ERROR] 수집된 뉴스가 없습니다.")
        return
    
    print("[2/4] 주식 정보 수집 중...")
    stock_info = fetch_stock_info()
    print(f"주식 정보: {stock_info}")
    
    print("[3/4] Claude로 요약 생성 중...")
    article_content = summarize_with_claude(news_list)
    
    print("[4/4] WordPress 발행 중...")
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    weekdays = ['월', '화', '수', '목', '금', '토', '일']
    title = f"{now.strftime('%y')}년 {now.strftime('%m')}월 {now.strftime('%d')}일 {weekdays[now.weekday()]}요일 간추린 뉴스"
    post_to_wordpress(title, article_content, stock_info)
    print("=== 완료 ===")

if __name__ == "__main__":
    main()
