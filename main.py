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

# RSS 피드 목록
RSS_FEEDS = [
    ("연합뉴스", "https://www.yonhapnewstv.co.kr/browse/feed/"),
    ("YTN", "https://www.ytn.co.kr/rss/headline.xml"),
    ("KBS", "https://world.kbs.co.kr/rss/rss_news.htm?lang=k"),
    ("MBC", "https://imnews.imbc.com/rss/news/news_00.xml"),
    ("SBS", "https://news.sbs.co.kr/news/rss/rss_01.xml"),
    ("한겨레", "https://www.hani.co.kr/rss/"),
    ("경향신문", "https://www.khan.co.kr/rss/rssdata/total_news.xml"),
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
        
        # 코스피
        kospi_url = "https://finance.naver.com/sise/sise_index.naver?code=KOSPI"
        res = requests.get(kospi_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        kospi = soup.select_one('#now_value').text.strip()
        kospi_change = soup.select_one('#change_value_and_rate').text.strip()
        
        # 코스닥
        kosdaq_url = "https://finance.naver.com/sise/sise_index.naver?code=KOSDAQ"
        res = requests.get(kosdaq_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        kosdaq = soup.select_one('#now_value').text.strip()
        kosdaq_change = soup.select_one('#change_value_and_rate').text.strip()
        
        # 환율
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
- 정치 / 경제 / 사회 / 국제 / 날씨로 분류해서 묶을 것
- 분류명은 <strong>정치</strong> 형식으로 HTML 굵은 태그 사용
- 정치 5개, 경제 3개, 사회 5개, 국제 3개, 날씨 1개 (총 17개 이상)
- 각 뉴스는 "ㆍ" 기호로 시작
- 일반 뉴스는 1~2문장 요약
- 매우 중요한 뉴스는 3~4문장까지 허용
- 기사 제목을 그대로 쓰지 말고 기자가 요약한 문장처럼 작성
- 감정적·선동적 표현 금지, 정보 전달 위주
- 전체 톤은 shortnews.co.kr처럼 차분하고 명확하게
- 날씨는 구체적인 기온과 지역별 날씨 정보 포함

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
        print(f"[SUCCESS] 발행 완료: {response.json().get('link')}")
    else:
        print(f"[ERROR] 발행 실패: {response.status_code} - {response.text}")

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
