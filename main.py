import re
import time
import requests
from bs4 import BeautifulSoup

url = "https://webapp.yuntech.edu.tw/WebNewCAS/Course/QueryCour.aspx"

while True:
    try:
        targetSemester = "1142"
        targetCollege = ["1", "2", "3", "4", "5"]

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

        get_response = session.get(url)
        soup = BeautifulSoup(get_response.text, 'html.parser')

        def get_hidden_fields(s):
            return {tag.get('name'): tag.get('value', '') for tag in s.find_all('input', type='hidden') if tag.get('name')}

        payload = get_hidden_fields(soup)
        payload.update({
            "ctl00$MainContent$AcadSeme": targetSemester,
            "ctl00$MainContent$College": "1",
            "ctl00$MainContent$Submit": "執行查詢"
        })
        
        for college in targetCollege:
            payload["ctl00$MainContent$College"] = college
            post_response = session.post(url, data=payload)

            # Ajax異步請求
            soup2 = BeautifulSoup(post_response.text, 'html.parser')
            ajax_payload = get_hidden_fields(soup2)

            # 模擬Ajax標頭
            # session.headers.update({
            #     "X-MicrosoftAjax": "Delta=true",
            #     "X-Requested-With": "XMLHttpRequest",
            #     "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
            # })

            ajax_payload.update({
                "ctl00$MainContent$ToolkitScriptManager1": "ctl00$MainContent$UpdatePanel2|ctl00$MainContent$PageControl1$PageSize",
                "__EVENTTARGET": "ctl00$MainContent$PageControl1$PageSize",
                "__EVENTARGUMENT": "",
                "ctl00$MainContent$PageControl1$PageSize": "100",
                # "__ASYNCPOST": "true"
            })

            ajax_response = session.post(url, data=ajax_payload)
            current_page = 0

            while True:
                # debug
                with open("debug.html", "w", encoding="utf-8") as f:
                    f.write(ajax_response.text)
                
                if ajax_response.status_code == 200:
                    print("Success")
                    result_soup = BeautifulSoup(ajax_response.text, 'html.parser')
                    
                    total_page = result_soup.find('span', id='ctl00_MainContent_PageControl1_TotalPage').text.strip()
                    total_page = int(total_page) if total_page.isdigit() else 1
                    
                    table = result_soup.find("table", id="ctl00_MainContent_Course_GridView")
                    if table:
                        for row in table.find_all("tr")[1:]:
                            cols = row.find_all("td")
                            if len(cols) >= 11:
                                course_ID = cols[0].text.strip()
                                course_cname = cols[2].get_text(separator="\n").strip().split('\n')[0]
                                # course_ename = cols[2].get_text(separator="\n").strip().split('\n')[1]
                                course_type = cols[5].text.strip().splitlines()[0]
                                current_students = cols[9].text.strip()
                                limit_text = cols[10].text.strip()
                                limit_match = re.search(r'\d+', limit_text)
                                max_limit = limit_match.group() if limit_match else None
                                print({
                                    "學期": targetSemester,
                                    "課號": course_ID,
                                    "課名": course_cname,
                                    # "英文課名": course_ename,
                                    "課程類別": course_type,
                                    "修課人數": current_students,
                                    "人數限制(Max)": max_limit
                                })
                    else:
                        print("HTML Failed")
                    
                    payload = get_hidden_fields(result_soup)
                    next_page = current_page + 1
                    
                    if next_page >= total_page:
                        break
                    
                    payload.update({
                        "ctl00$MainContent$ToolkitScriptManager1": "ctl00$MainContent$UpdatePanel2|ctl00$MainContent$PageControl1$NextPage",
                        "__EVENTTARGET": "ctl00$MainContent$PageControl1$NextPage",
                        "__EVENTARGUMENT": "",
                        "ctl00$MainContent$PageControl1$Pages": str(next_page),
                    })
                    
                    # time.sleep(1)
                    ajax_response = session.post(url, data=payload)
                    current_page = next_page
                else:
                    print(f"Error:{ajax_response.status_code}")
                    break
    except Exception as e:
        print(f"Error: {e}")
        continue