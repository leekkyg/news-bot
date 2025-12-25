import feedparser
import requests
from datetime import datetime
import pytz
import os
import anthropic

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

def summarize_with_claude(news_list):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    news_text = ""
    for i, news in enumerate(news_list, 1):
        news_text += f"{i}. [{news['source']}] {news['title']}\n{news['summary']}\n\n"
    
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    weekdays = ['월', '화', '수', '목', '금', '토', '일']
    date_str = f"{now.strftime('%y')}년 {now.strftime('%m')}월 {now.strftime('%d')}일 {weekdays[now.weekday()]}요일"
    
    prompt = f"""너는 지역 언론사의 뉴스 편집 기자다.
아래 뉴스들을 바탕으로 '간추린 숏뉴스'를 작성해라.

[작성 규칙]
- 첫 줄: "{date_str} 간추린 숏뉴스입니다." 로 시작
- 각 뉴스는 "■ (분류)" 로 시작 (정치/경제/사회/국제/날씨)
- 일반 뉴스는 1~2문장, 중요한 뉴스는 3~4문장까지 허용
- 기사 제목 그대로 쓰지 말고, 기자가 직접 정리한 것처럼 자연스럽게 작성
- 딱딱한 보도체가 아닌, 사람이 읽기 편한 문체로 작성
- 감정적·선동적 표현 금지
- HTML 태그 없이 순수 텍스트로 작성
- 줄바꿈으로 각 뉴스 구분

[입력 데이터]
{news_text}

텍스트만 출력하세요."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return message.content[0].text

def post_to_wordpress(title, content):
    # 이미지 태그 추가
    image_url = "https://pub-d5e485446b5c4e8d900036e639bf8d6c.r2.dev/wp-content/uploads/2025/12/news.jpg"
    full_content = f'<img src="{image_url}" alt="간추린 숏뉴스" />\n\n{content}'
    
    endpoint = f"{WP_URL}/wp-json/wp/v2/posts"
    post_data = {
        "title": title,
        "content": full_content,
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
    
    print("[2/3] Claude로 요약 생성 중...")
    article_content = summarize_with_claude(news_list)
    
    print("[3/3] WordPress 발행 중...")
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    weekdays = ['월', '화', '수', '목', '금', '토', '일']
    title = f"{now.strftime('%y')}년 {now.strftime('%m')}월 {now.strftime('%d')}일 {weekdays[now.weekday()]}요일 간추린 숏뉴스"
    post_to_wordpress(title, article_content)
    print("=== 완료 ===")

if __name__ == "__main__":
    main()
