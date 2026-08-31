import os
import smtplib
import requests
from bs4 import BeautifulSoup
from email.mime.text import MIMEText

HISTORY_FILE = "sent_ids.txt"
TARGET_URL = "https://ppomppu.co.kr/zboard/zboard.php?id=money&page=1"
THRESHOLD = 10  # 알림 기준 추천수

def load_sent_ids():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_sent_id(post_id):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{post_id}\n")

def send_email(posts):
    user = os.environ.get("MAIL_USER")
    password = os.environ.get("MAIL_PASS")
    if not user or not password:
        return

    body = "<h3>[뽐뿌 재테크 포럼] 추천수 10 이상 게시글</h3><ul>"
    for post in posts:
        body += f"<li><b>[{post['votes']}추천]</b> <a href='{post['link']}'>{post['title']}</a></li>"
    body += "</ul>"

    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = f"[뽐뿌 알림] 새로운 인기글 {len(posts)}건"
    msg["From"] = user
    msg["To"] = user

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(user, password)
        server.send_message(msg)

def check_posts():
    sent_ids = load_sent_ids()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    res = requests.get(TARGET_URL, headers=headers)
    res.encoding = "euc-kr"  # 뽐뿌 기본 인코딩 대응
    soup = BeautifulSoup(res.text, "html.parser")
    
    rows = soup.select("tr.baseList")
    new_alerts = []

    for row in rows:
        try:
            # 추천수 파싱 (추천 - 비추천 형식)
            votes_elem = row.select_one("td.baseList-rec")
            if not votes_elem:
                continue
            
            votes_text = votes_elem.get_text(strip=True)
            if "-" in votes_text:
                upvotes = int(votes_text.split("-")[0].strip())
            else:
                upvotes = int(votes_text) if votes_text.isdigit() else 0

            if upvotes >= THRESHOLD:
                title_elem = row.select_one("a.baseList-title")
                if not title_elem:
                    continue
                
                href = title_elem.get("href", "")
                title = title_elem.get_text(strip=True)
                
                # 게시글 번호(no) 추출
                post_id = href.split("no=")[-1].split("&")[0] if "no=" in href else href
                
                if post_id not in sent_ids:
                    full_link = f"https://ppomppu.co.kr/zboard/{href}" if not href.startswith("http") else href
                    new_alerts.append({"id": post_id, "title": title, "link": full_link, "votes": upvotes})
                    save_sent_id(post_id)
        except Exception:
            continue

    if new_alerts:
        send_email(new_alerts)
        print(f"새로운 게시글 {len(new_alerts)}건 발송 완료")
    else:
        print("신규 알림 대상 없음")

if __name__ == "__main__":
    check_posts()
