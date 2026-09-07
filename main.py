import os
import re
import smtplib
import time
import requests
from bs4 import BeautifulSoup
from email.mime.text import MIMEText

HISTORY_FILE = "sent_ids.txt"

# [설정] 뽐뿌
PPOMPPU_URL = "https://m.ppomppu.co.kr/new/bbs_list.php?id=money&page="
PPOMPPU_THRESHOLD = 10  # 알림 기준 추천수
PPOMPPU_MAX_PAGES = 2   # 탐색할 페이지 수

# [설정] 디시인사이드 (추후 원하는 갤러리 URL을 배열에 추가 가능)
DC_TARGET_URLS = [
    "https://gall.dcinside.com/mgallery/board/lists/?id=mounjaro&sort_type=N&search_head=80&page=1"
]

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
    target_mail = os.environ.get("TARGET_MAIL")

    if not user or not password or not target_mail:
        print("메일 환경변수(MAIL_USER/MAIL_PASS/TARGET_MAIL) 누락")
        return

    body = "<h3>[통합 알림] 신규 인기글 및 새 글 목록</h3><ul>"
    for post in posts:
        if post["source"] == "ppomppu":
            body += f"<li><b>[뽐뿌 재포 | 추천 {post['votes']}]</b> <a href='{post['link']}'>{post['title']}</a></li>"
        elif post["source"] == "dcinside":
            body += f"<li><b>[디시 {post['board_name']}]</b> <a href='{post['link']}'>{post['title']}</a></li>"
    body += "</ul>"

    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = f"[통합 알림] 신규 게시글 {len(posts)}건 감지"
    msg["From"] = user
    msg["To"] = target_mail

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(user, password)
            server.send_message(msg)
        print("이메일 발송 성공!")
    except Exception as e:
        print(f"이메일 발송 실패: {e}")

def check_ppomppu(sent_ids):
    print("=== [1. 뽐뿌 재테크 포럼 탐색] ===")
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
        "Referer": "https://m.ppomppu.co.kr/",
        "Accept-Language": "ko-KR,ko;q=0.9"
    }
    
    alerts = []

    for page in range(1, PPOMPPU_MAX_PAGES + 1):
        target_url = f"{PPOMPPU_URL}{page}"
        try:
            res = requests.get(target_url, headers=headers, timeout=10)
            res.encoding = "euc-kr"
            soup = BeautifulSoup(res.text, "html.parser")
        except Exception as e:
            print(f"뽐뿌 {page}페이지 요청 실패: {e}")
            continue

        for li in soup.select("ul.bbsList li"):
            try:
                classes = li.get("class", [])
                if "notice" in classes or "line" in classes:
                    continue
                    
                link_tag = li.select_one("a[href*='bbs_view.php']")
                if not link_tag:
                    continue

                match_no = re.search(r'no=(\d+)', link_tag.get("href", ""))
                if not match_no:
                    continue
                post_id = f"ppomppu_{match_no.group(1)}"

                title_tag = li.select_one(".title, .cont, strong") or link_tag
                title = title_tag.get_text(strip=True)

                upvotes = 0
                rec_elem = li.select_one("span.rec, span.recom, span.recom_num, span.vote")
                
                if not rec_elem:
                    for sp in li.select(".info span, .desc span, span"):
                        txt = sp.get_text(strip=True)
                        if "-" in txt and not any(sep in txt for sep in [":", "/", "."]):
                            parts = txt.split("-")
                            if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
                                upvotes = int(parts[0].strip())
                                break
                else:
                    match_rec = re.search(r'(\d+)', rec_elem.get_text(strip=True))
                    if match_rec:
                        upvotes = int(match_rec.group(1))

                if upvotes >= PPOMPPU_THRESHOLD and post_id not in sent_ids:
                    if not any(p["id"] == post_id for p in alerts):
                        real_no = match_no.group(1)
                        full_link = f"https://www.ppomppu.co.kr/zboard/view.php?id=money&no={real_no}"
                        alerts.append({
                            "id": post_id,
                            "source": "ppomppu",
                            "title": title,
                            "link": full_link,
                            "votes": upvotes
                        })
                        print(f"  ★ [뽐뿌] 대상 추가: [{upvotes}추천] {title[:20]}")
            except Exception:
                continue

        time.sleep(0.5)

    return alerts

def check_dcinside(sent_ids):
    print("=== [2. 디시인사이드 탐색] ===")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://gall.dcinside.com/",
        "Accept-Language": "ko-KR,ko;q=0.9"
    }

    alerts = []

    for target_url in DC_TARGET_URLS:
        try:
            res = requests.get(target_url, headers=headers, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")
        except Exception as e:
            print(f"디시 요청 실패: {e}")
            continue

        gallery_title_elem = soup.select_one(".page_head .fl h2, .gall_title")
        board_name = gallery_title_elem.get_text(strip=True) if gallery_title_elem else "마이너 갤러리"

        rows = soup.select("table.gall_list tbody tr.ub-content")

        for tr in rows:
            try:
                if "notice" in tr.get("class", []):
                    continue

                num_td = tr.select_one("td.gall_num")
                if not num_td or not num_td.get_text(strip=True).isdigit():
                    continue
                post_num = num_td.get_text(strip=True)
                post_id = f"dc_{board_name}_{post_num}"

                title_tag = tr.select_one("td.gall_tit a")
                if not title_tag:
                    continue

                title = title_tag.get_text(strip=True)
                reply_span = title_tag.select_one(".reply_num")
                if reply_span:
                    title = title.replace(reply_span.get_text(strip=True), "").strip()

                href = title_tag.get("href", "")
                link = f"https://gall.dcinside.com{href}" if href.startswith("/") else href

                if post_id not in sent_ids and not any(p["id"] == post_id for p in alerts):
                    alerts.append({
                        "id": post_id,
                        "source": "dcinside",
                        "board_name": board_name,
                        "title": title,
                        "link": link
                    })
                    print(f"  ★ [디시] 새 글 발견: {title[:20]}")
            except Exception:
                continue

        time.sleep(0.5)

    return alerts

def main():
    sent_ids = load_sent_ids()
    new_alerts = []

    # 1. 뽐뿌 검사
    new_alerts.extend(check_ppomppu(sent_ids))
    # 2. 디시 검사
    new_alerts.extend(check_dcinside(sent_ids))

    if new_alerts:
        print(f"\n총 {len(new_alerts)}건 알림 발송 시작")
        send_email(new_alerts)
        save_sent_ids([p["id"] for p in new_alerts])
    else:
        print("\n새로운 알림 대상 없음")

if __name__ == "__main__":
    main()
