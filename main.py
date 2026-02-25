import re
import time
import requests
from bs4 import BeautifulSoup

url = "https://webapp.yuntech.edu.tw/WebNewCAS/Course/QueryCour.aspx"

while True:
    try:
        targetID = ["1234", "1235", "1236", "1237"] # TODO: 動態更新
        
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        get_response = session.get(url)
        soup = BeautifulSoup(get_response.text, 'html.parser')
        payload = {}
        for tag in soup.find_all('input', type='hidden'):
            name = tag.get('name')
            if name:
                payload[name] = tag.get('value', '')

        payload.update({
            "ctl00$MainContent$AcadSeme": "1142",
            "ctl00$MainContent$College": "",
            "ctl00$MainContent$DeptCode": "",
            # "ctl00$MainContent$MajOp$2": "on",
            "ctl00$MainContent$CurrentSubj": "",
            "ctl00$MainContent$SubjName": "",
            "ctl00$MainContent$Instructor": "",
            # "ctl00$MainContent$Weeks$1": "on",
            # "ctl00$MainContent$Sections$4": "on",
            # "ctl00$MainContent$Sections$5": "on",
            # "ctl00$MainContent$Sections$6": "on",
            # "ctl00$MainContent$Sections$7": "on",
            "ctl00$MainContent$Submit": "執行查詢"
        })
        
        for courseID in targetID:
            payload["ctl00$MainContent$CurrentSubj"] = courseID
            post_response = session.post(url, data=payload)

            # debug
            # with open("debug.html", "w", encoding="utf-8") as f:
            #     f.write(post_response.text)
                
            if post_response.status_code == 200:
                print("Success")
                result_soup = BeautifulSoup(post_response.text, 'html.parser')
                
                table = result_soup.find("table", id="ctl00_MainContent_Course_GridView")
                if table:
                    for row in table.find_all("tr")[1:]:
                        cols = row.find_all("td")
                        if len(cols) >= 11:
                            course_ID = cols[0].text.strip()
                            course_cname = cols[2].get_text(separator="\n").strip().split('\n')[0]
                            # course_ename = cols[2].get_text(separator="\n").strip().split('\n')[1]
                            course_type = cols[5].text.strip()
                            current_students = cols[9].text.strip()
                            limit_text = cols[10].text.strip()
                            limit_match = re.search(r'\d+', limit_text)
                            max_limit = limit_match.group() if limit_match else "無限制"
                            print({
                                "課號": course_ID,
                                "課名": course_cname,
                                # "英文課名": course_ename,
                                "課程類別": course_type,
                                "修課人數": current_students,
                                "人數限制(Max)": max_limit
                            })
                else:
                    print("找不到表格，請確認 HTML 內容是否正確。")
            else:
                print(f"Error:{post_response.status_code}")
                
            time.sleep(0.25)
        
        time.sleep(10)
    except Exception as e:
        print(f"發生錯誤，略過此次查詢: {e}")