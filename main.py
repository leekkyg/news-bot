import feedparser
import anthropic
import requests
from datetime import datetime
import pytz
import os

# 환경변수
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
WP_URL = os.environ.get("WP_URL")  # https://yeojugoodnews.com
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
    """RSS에서 최신 뉴스 수집"""
    all_news = []
    
    for source_name, feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:  # 각 소스별 5개씩
                all_news.append({
                    "source": source_name,
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", entry.get("description", "")),
                    "published": entry.get("published", ""),
                })
        except Exception as e:
            print(f"[ERROR] {source_name} 피드 수집 실패: {e}")
    
    return all_news

def summarize_with_claude(news_list):
    """Claude로 뉴스 요약 생성"""
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    
    # 뉴스 목록을 텍스트로 변환
    news_text = ""
    for i, news in enumerate(news_list, 1):
        news_text += f"{i}. [{news['source']}] {news['title']}\n{news['summary']}\n\n"
    
    kst = pytz.timezone('Asia/Seoul')
    today = datetime.now(kst).strftime("%Y년 %m월 %d일")
    
    prompt = f"""오늘({today}) 주요 뉴스를 바탕으로 아침 뉴스 브리핑 기사를 작성해주세요.

[수집된 뉴스]
{news_text}

작성 규칙:
1. 제목: "오늘의 주요뉴스 ({today})" 형식
2. 중요한 뉴스 5-7개를 선별해서 요약
3. 각 뉴스는 2-3문장으로 핵심만
4. 친근하지만 신뢰감 있는 톤
5. HTML 형식으로 작성 (h3, p, ul 태그 사용)
6. 마지막에 "여주굿뉴스가 전해드렸습니다" 마무리

기사 본문만 출력하세요."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.content[0].text

def post_to_wordpress(title, content):
    """WordPress에 포스트 발행"""
    endpoint = f"{WP_URL}/wp-json/wp/v2/posts"
    
    kst = pytz.timezone('Asia/Seoul')
    today = datetime.now(kst).strftime("%Y년 %m월 %d일")
    
    post_data = {
        "title": f"오늘의 주요뉴스 ({today})",
        "content": content,
        "status": "publish",
        "categories": [],  # 카테고리 ID 필요시 추가
    }
    
    response = requests.post(
        endpoint,
        json=post_data,
        auth=(WP_USER, WP_APP_PASSWORD),
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 201:
        post_url = response.json().get("link")
        print(f"[SUCCESS] 발행 완료: {post_url}")
        return post_url
    else:
        print(f"[ERROR] 발행 실패: {response.status_code} - {response.text}")
        return None

def main():
    print("=== 뉴스 자동 발행 시작 ===")
    
    # 1. 뉴스 수집
    print("[1/3] 뉴스 수집 중...")
    news_list = fetch_news()
    print(f"  → {len(news_list)}개 뉴스 수집 완료")
    
    if not news_list:
        print("[ERROR] 수집된 뉴스가 없습니다.")
        return
    
    # 2. Claude로 요약
    print("[2/3] Claude로 요약 생성 중...")
    article_content = summarize_with_claude(news_list)
    print("  → 요약 완료")
    
    # 3. WordPress 발행
    print("[3/3] WordPress 발행 중...")
    kst = pytz.timezone('Asia/Seoul')
    today = datetime.now(kst).strftime("%Y년 %m월 %d일")
    post_to_wordpress(f"오늘의 주요뉴스 ({today})", article_content)
    
    print("=== 완료 ===")

if __name__ == "__main__":
    main()
