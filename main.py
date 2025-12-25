import feedparser
import requests
from datetime import datetime
import pytz
import os
import google.generativeai as genai

# 환경변수
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
WP_URL = os.environ.get("WP_URL")
WP_USER = os.environ.get("WP_USER")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD")

# RSS 피드 목록
RSS_FEEDS = [
    ("연합뉴스", "https://www.yonhapnewstv.co.kr/browse/feed/"),
    ("YTN", "https://www.ytn.co.kr/rss/headline.xml"),
    ("KBS", "https://world.kbs.co.kr/rss/rss_news.htm?lang=k"),
    ("MBC", "https://imnews.imbc.com/rss/news/news_00.xml"),
]

def fetch_news():
    all_news = []
    for source_name, feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:
                all_news.append({
                    "source": source_name,
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", entry.get("description", "")),
                })
        except Exception as e:
            print(f"[ERROR] {source_name} 피드 수집 실패: {e}")
    return all_news

def summarize_with_gemini(news_list):
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    news_text = ""
    for i, news in enumerate(news_list, 1):
        news_text += f"{i}. [{news['source']}] {news['title']}\n{news['summary']}\n\n"
    
    kst = pytz.timezone('Asia/Seoul')
    today = datetime.now(kst).strftime("%Y년 %m월 %d일")
    
    prompt = f"""너는 실제 뉴스 편집국에서 일하는 편집 기자다.
아래에 여러 개의 뉴스 기사가 주어진다.
이를 바탕으로 아침에 보는 '간추린 뉴스' 형태로 재작성하라.

[작성 규칙]
- 정치 / 경제 / 사회 / 국제 / 기타로 분류해서 묶을 것
- 각 뉴스는 "ㆍ" 기호로 시작
- 일반 뉴스는 1문장 요약
- 매우 중요한 뉴스는 2문장까지 허용
- 기사 제목을 그대로 쓰지 말고 기자가 요약한 문장처럼 작성
- 감정적·선동적 표현 금지, 정보 전달 위주
- 전체 톤은 차분하고 명확하게
- HTML 형식으로 작성 (h3으로 분류명, p 태그 사용)


[입력 데이터]
{news_text}

HTML 본문만 출력하세요."""

    response = model.generate_content(prompt)
    return response.text

def post_to_wordpress(title, content):
    endpoint = f"{WP_URL}/wp-json/wp/v2/posts"
    post_data = {
        "title": title,
        "content": content,
        "status": "publish",
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
    print(f"[1/3] {len(news_list)}개 뉴스 수집 완료")
    
    if not news_list:
        print("[ERROR] 수집된 뉴스가 없습니다.")
        return
    
    print("[2/3] Gemini로 요약 생성 중...")
    article_content = summarize_with_gemini(news_list)
    
    print("[3/3] WordPress 발행 중...")
    kst = pytz.timezone('Asia/Seoul')
    today = datetime.now(kst).strftime("%Y년 %m월 %d일")
    post_to_wordpress(f"오늘의 주요뉴스 ({today})", article_content)
    print("=== 완료 ===")

if __name__ == "__main__":
    main()
