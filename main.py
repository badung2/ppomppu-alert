import os
import smtplib
import requests
from bs4 import BeautifulSoup
from email.mime.text import MIMEText

HISTORY_FILE = "sent_ids.txt"
# 클라우드 차단 우회 및 파싱이 간결한 모바일 주소 사용
TARGET_URL = "https://m.ppomppu.co.kr/new/bbs_list.php?id=money"
THRESHOLD = 10  # 알림 기준 추천수 (테스트 시 0으로 변경 가능)

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

    body = "<h3>[뽐뿌 재테크 포럼] 추천수 알림</h3><ul>"
    for post in posts:
        body += f"<li><b>[추천 {post['votes']}]</b> <a href='{post['link']}'>{post['title']}</a></li>"
    body += "</ul>"

    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = f"[뽐뿌 알림] 추천 10 이상 인기글 {len(posts)}건"
    msg["From"] = user
    msg["To"] = user

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(user, password)
            server.send_message(msg)
        print("이메일 발송 성공")
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

    # 모바일 뽐뿌 게시글 리스트 항목 탐색
    list_items = soup.select("ul.bbsList li")
    new_alerts = []
    
    print(f"총 {len(list_items)}개 항목 탐색 시작")

    for li in list_items:
        try:
            # 공지글 제외
            if "notice" in li.get("class", []):
                continue
                
            link_tag = li.select_one("a.title")
            if not link_tag:
                continue

            href = link_tag.get("href", "")
            title_span = link_tag.select_one("span.cont") or link_tag
            title = title_span.get_text(strip=True)

            # 글 번호(no=...) 추출
            post_id = ""
            if "no=" in href:
                post_id = href.split("no=")[-1].split("&")[0]
            if not post_id:
                continue

            # 추천수 영역 확인 (span.rec 또는 숫자-숫자 텍스트)
            upvotes = 0
            rec_tag = li.select_one("span.rec")
            if rec_tag:
                txt = rec_tag.get_text(strip=True)
                if "-" in txt:
                    txt = txt.split("-")[0].strip()
                upvotes = int(txt) if txt.isdigit() else 0
            else:
                # 일반 텍스트에서 추천수 파싱
                for span in li.select("span"):
                    txt = span.get_text(strip=True)
                    if "-" in txt and txt.replace("-", "").isdigit():
                        upvotes = int(txt.split("-")[0].strip())
                        break

            # 추천 기준 확인 및 미발송 건 필터링
            if upvotes >= THRESHOLD and post_id not in sent_ids:
                full_link = f"https://www.ppomppu.co.kr/zboard/view.php?id=money&no={post_id}"
                new_alerts.append({"id": post_id, "title": title, "link": full_link, "votes": upvotes})
                print(f"-> 대상 발견: [{upvotes}추천] {title} (번호: {post_id})")
        except Exception as e:
            continue

    if new_alerts:
        print(f"총 {len(new_alerts)}건 알림 발송 진행")
        send_email(new_alerts)
        save_sent_ids([p["id"] for p in new_alerts])
    else:
        print("신규 알림 대상 없음 (조건 만족 글 없음)")

if __name__ == "__main__":
    check_posts()
