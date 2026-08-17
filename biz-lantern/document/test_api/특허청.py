import requests
import xml.etree.ElementTree as ET

# 1. API 설정
ACCESS_KEY = "0j3nuZMw8Y4dBPF3Y0B2KGfn4jRO7d4FRNle3pjafSA="  # 발급받으신 REST AccessKey
URL = "http://plus.kipris.or.kr/openapi/rest/patUtiModInfoSearchSevice/freeSearchInfo"

# 2. 요청 파라미터 설정 (출원인: 삼성전자)
params = {
    "word": "AP=[삼성전자]",  # 출원인 검색식
    "accessKey": ACCESS_KEY,
    "docsStart": "1",        # 검색 시작 번호 (1페이지부터)
    "docsCount": "10"        # 가져올 검색 결과 개수
}

try:
    print("삼성전자 특허/실용 공개·등록공보 정보를 조회 중입니다...\n")
    response = requests.get(URL, params=params)
    response.raise_for_status()

    # XML 응답 파싱
    root = ET.fromstring(response.content)
    items = root.findall('.//PatentUtilityInfo')

    if items:
        print(f"총 {len(items)}건의 특허 정보를 조회했습니다.\n")
        for i, item in enumerate(items, 1):
            title = item.findtext('InventionName', 'N/A')
            applicant = item.findtext('Applicant', 'N/A')
            app_number = item.findtext('ApplicationNumber', 'N/A')
            app_date = item.findtext('ApplicationDate', 'N/A')
            status = item.findtext('RegistrationStatus', 'N/A')
            print(f"[{i}] {title}")
            print(f"    출원인: {applicant}")
            print(f"    출원번호: {app_number}")
            print(f"    출원일: {app_date}")
            print(f"    상태: {status}\n")
    else:
        print("검색 결과가 없습니다.")

except requests.exceptions.RequestException as e:
    print(f"API 요청 오류: {e}")
except ET.ParseError:
    print("XML 파싱에 실패했습니다.")
    print("응답 내용:", response.text)