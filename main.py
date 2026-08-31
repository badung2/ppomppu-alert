import os
import requests
from bs4 import BeautifulSoup

TARGET_URL = "https://ppomppu.co.kr/zboard/zboard.php?id=money&page=1"

def debug_check():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    res = requests.get(TARGET_URL, headers=headers, timeout=10)
    res.encoding = "euc-kr"
    soup = BeautifulSoup(res.text, "html.parser")
    
    # 게시글 링크 전체 탐색
    links = soup.find_all("a")
    post_links = [a for a in links if a.get("href") and "view.php?id=money" in a.get("href")]
    
    print(f"=== [디버그] 수집된 게시글 링크 총 {len(post_links)}개 ===")
    
    count = 0
    for a in post_links:
        title = a.get_text(strip=True)
        # 빈 텍스트(댓글수 링크 등) 제외
        if not title or title.isdigit():
            continue
            
        href = a.get("href")
        parent_tr = a.find_parent("tr")
        tr_text = parent_tr.get_text(" | ", strip=True) if parent_tr else "TR 없음"
        
        print(f"[{count+1}] 제목: {title}")
        print(f"    행 전체 텍스트: {tr_text[:100]}...")
        count += 1
        if count >= 5:  # 상위 5개만 샘플 출력
            break

if __name__ == "__main__":
    debug_check()
