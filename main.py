import os
import re
import smtplib
import requests
from bs4 import BeautifulSoup
from email.mime.text import MIMEText

HISTORY_FILE = "sent_ids.txt"
TARGET_URL = "https://m.ppomppu.co.kr/new/bbs_list.php?id=money"
THRESHOLD = 10  # 알림 기준 추천수

def load_sent_ids():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_sent_ids(post_ids):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        for pid in post_ids:
            f.write(f"{pid}\n")

def send_email(posts):
    user = os.environ.get("MAIL_USER")
    password = os.environ.get("MAIL_PASS")
    if not user or not password:
        print("메일 환경변수(MAIL_USER/MAIL_PASS) 누락")
        return

    body = "<h3>[뽐뿌 재테크 포럼] 인기 게시글 알림</h3><ul>"
    for post in posts:
        body += f"<li><b>[추천 {post['votes']}]</b> <a href='{post['link']}'>{post['title']}</a></li>"
    body += "</ul>"

    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = f"[뽐뿌 알림] 추천 10 이상 인기글 {len(posts)}건"
    msg["From"] = user
    msg["To"] = "badungi@naver.com"

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(user, password)
            server.send_message(msg)
        print("이메일 발송 성공!")
    except Exception as e:
        print(f"이메일 발송 실패: {e}")

def check_posts():
    sent_ids = load_sent_ids()
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
        "Referer": "https://m.ppomppu.co.kr/",
        "Accept-Language": "ko-KR,ko;q=0.9"
    }
    
    try:
        res = requests.get(TARGET_URL, headers=headers, timeout=10)
        res.encoding = "euc-kr"
        soup = BeautifulSoup(res.text, "html.parser")
    except Exception as e:
        print(f"웹 요청 실패: {e}")
        return

    list_items = soup.select("ul.bbsList li")
    new_alerts = []
    
    print(f"총 {len(list_items)}개 항목 탐색 시작")

    for li in list_items:
        try:
            # 공지글/배너 제외
            classes = li.get("class", [])
            if "notice" in classes or "line" in classes:
                continue
                
            # 링크 태그 탐색
            link_tag = li.select_one("a[href*='bbs_view.php']")
            if not link_tag:
                continue

            href = link_tag.get("href", "")
            
            # 글 번호(no=...) 추출
            match_no = re.search(r'no=(\d+)', href)
            if not match_no:
                continue
            post_id = match_no.group(1)

            # 제목 추출
            title_tag = li.select_one(".title, .cont, strong") or link_tag
            title = title_tag.get_text(strip=True)

            # li 전체 텍스트에서 '숫자 - 숫자' 형태의 추천-비추천 패턴 추출
            li_text = li.get_text(" ", strip=True)
            vote_match = re.search(r'(\d+)\s*-\s*(\d+)', li_text)
            
            upvotes = 0
            if vote_match:
                upvotes = int(vote_match.group(1))
            
            # 디버깅 출력
            print(f"  [확인] 글번호: {post_id} | 추천수: {upvotes} | 제목: {title[:20]}...")

            if upvotes >= THRESHOLD and post_id not in sent_ids:
                full_link = f"https://www.ppomppu.co.kr/zboard/view.php?id=money&no={post_id}"
                new_alerts.append({"id": post_id, "title": title, "link": full_link, "votes": upvotes})
                print(f"    ★ 조건 만족 대상 추가: [{upvotes}추천] {title[:25]}")
        except Exception as e:
            continue

    if new_alerts:
        print(f"총 {len(new_alerts)}건 알림 대상 발견 -> 메일 전송 시작")
        send_email(new_alerts)
        save_sent_ids([p["id"] for p in new_alerts])
    else:
        print("신규 알림 대상 없음")

if __name__ == "__main__":
    check_posts()
