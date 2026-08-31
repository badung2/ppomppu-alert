import os
import smtplib
import requests
from bs4 import BeautifulSoup
from email.mime.text import MIMEText

HISTORY_FILE = "sent_ids.txt"
TARGET_URL = "https://ppomppu.co.kr/zboard/zboard.php?id=money&page=1"
THRESHOLD = 0  # 알림 기준 추천수 (테스트 시 0으로 변경 가능)

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
    msg["Subject"] = f"[뽐뿌 알림] 새로운 인기글 {len(posts)}건"
    msg["From"] = user
    msg["To"] = user

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(user, password)
            server.send_message(msg)
        print("메일 발송 성공")
    except Exception as e:
        print(f"메일 발송 실패: {e}")

def check_posts():
    sent_ids = load_sent_ids()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        res = requests.get(TARGET_URL, headers=headers, timeout=10)
        res.encoding = "euc-kr"
        soup = BeautifulSoup(res.text, "html.parser")
    except Exception as e:
        print(f"웹 요청 실패: {e}")
        return

    new_alerts = []
    # 뽐뿌 게시글 행 목록 탐색
    rows = soup.select("tr.list0, tr.list1, tr.baseList")
    
    for row in rows:
        try:
            # 제목 태그 찾기
            title_tag = row.select_one("a[href*='view.php?id=money']")
            if not title_tag:
                continue

            href = title_tag.get("href", "")
            title = title_tag.get_text(strip=True)
            if not title:
                continue

            # 글 번호(no=...) 추출
            post_id = ""
            if "no=" in href:
                post_id = href.split("no=")[-1].split("&")[0]
            if not post_id:
                continue

            # 추천수 영역 탐색 (보통 td 중 숫자 - 숫자 형태)
            upvotes = 0
            tds = row.find_all("td")
            for td in tds:
                txt = td.get_text(strip=True)
                if "-" in txt:
                    parts = txt.split("-")
                    if parts[0].strip().isdigit():
                        upvotes = int(parts[0].strip())
                        break

            # 추천수가 기준치 이상이고 아직 안 보낸 글인 경우
            if upvotes >= THRESHOLD and post_id not in sent_ids:
                full_link = f"https://ppomppu.co.kr/zboard/{href}" if not href.startswith("http") else href
                new_alerts.append({"id": post_id, "title": title, "link": full_link, "votes": upvotes})
        except Exception as e:
            continue

    if new_alerts:
        print(f"대상 게시글 발견: {len(new_alerts)}건")
        send_email(new_alerts)
        save_sent_ids([p["id"] for p in new_alerts])
    else:
        print("신규 알림 대상 없음 (조건 만족 글 없음)")

if __name__ == "__main__":
    check_posts()
