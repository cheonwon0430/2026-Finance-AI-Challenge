import json
import requests
import xmltodict

from app.common.config import settings

# 1. API 설정
ACCESS_KEY = settings.kipris_api_key  # 환경변수로 뽑기
URL = "http://plus.kipris.or.kr/openapi/rest/patUtiModInfoSearchSevice/freeSearchInfo"

# 2. 기업명 리스트
# COMPANIES = ["삼성전자", "LG전자"]
# print(f"검색할 기업명 리스트: {COMPANIES}\n")

def get_company_by_company_name(company: str):
    # 3. 요청 파라미터 설정 (출원인: company)
    params = {
        "word": f"AP=[{company}]",  # 출원인 검색식
        "accessKey": ACCESS_KEY,
        "docsStart": "1",  # 검색 시작 번호 (1페이지부터)
        "docsCount": "10",  # 가져올 검색 결과 개수
    }

    try:
        print(f"{company} 특허/실용 공개·등록공보 정보를 조회 중입니다...\n")
        response = requests.get(URL, params=params)
        response.raise_for_status()

        # XML -> Python dict 변환
        dict_data = xmltodict.parse(response.content)

        # (필요시) dict -> JSON 문자열 변환 및 출력
        json_data = json.dumps(dict_data, ensure_ascii=False, indent=2)
        print("JSON 변환 결과:\n", json_data)
        
        return json_data

        # # 4. 데이터 파싱 및 안전한 탐색
        # body = dict_data.get("response", {}).get("body", {})
        # items = body.get("items", {})

        # if not items or "PatentUtilityInfo" not in items:
        #     print("검색 결과가 없습니다.\n")
        #     continue

        # patent_info = items["PatentUtilityInfo"]

        # # xmltodict 특성상 검색 결과가 1건이면 dict, 여러 건이면 list로 반환되므로 리스트로 통일
        # if isinstance(patent_info, dict):
        #     patent_info = [patent_info]

        # print(f"총 {len(patent_info)}건의 특허 정보를 조회했습니다.\n")
        # for i, item in enumerate(patent_info, 1):
        #     title = item.get("InventionName") or "N/A"
        #     applicant = item.get("Applicant") or "N/A"
        #     app_number = item.get("ApplicationNumber") or "N/A"
        #     app_date = item.get("ApplicationDate") or "N/A"
        #     status = item.get("RegistrationStatus") or "N/A"

        #     print(f"[{i}] {title}")
        #     print(f"    출원인: {applicant}")
        #     print(f"    출원번호: {app_number}")
        #     print(f"    출원일: {app_date}")
        #     print(f"    상태: {status}\n")

    except requests.exceptions.RequestException as e:
        print(f"API 요청 오류: {e}")
    except Exception as e:
        print(f"데이터 파싱 오류: {e}")