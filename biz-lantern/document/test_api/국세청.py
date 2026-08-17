####################################################
# 사용법 리스트의 배열만 수정하면 됩니다.
# payload = {
#     "b_no": ["1248100998"] # 조회할 사업자번호를 리스트 형태로 입력하세요. 최대 100개까지 가능.
# }
####################################################

import requests
import json

# 1. API 기본 정보 설정
base_url = "https://api.odcloud.kr/api/nts-businessman/v1/status"
# 페이지에 명시된 일반 인증키
service_key = "vw2EnZ0GgIZHggwDsu7aUHke764BQdqeKf5lKhPTeHutsRpAtgmD7OJlVeTbpbB2TIZ4RavZN01PSlcYZx%2B2aA%3D%3D"

# 2. 쿼리 파라미터 설정 (URL 뒤에 붙는 값)
# 주의: API 환경에 따라 인코딩/디코딩된 키 적용 방식이 다를 수 있으나, 
# requests의 params로 넘길 때 자동 인코딩 문제가 발생할 수 있어 URL에 직접 붙이는 방식도 권장됩니다.
params = {
    "serviceKey": requests.utils.unquote(service_key), # requests가 다시 인코딩하므로 디코딩된 값을 넘기거나 URL 스트링에 직접 결합
    "returnType": "JSON"
}

# 3. HTTP 헤더 설정
headers = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# 4. 요청 바디 데이터 설정 (하이픈 '-'을 제외한 사업자등록번호 10자리 입력)
payload = {
    "b_no": ["1248100990"] # 조회할 사업자번호를 리스트 형태로 입력하세요. 최대 100개까지 가능.
}

# 5. POST 방식으로 API 요청
response = requests.post(base_url, params=params, headers=headers, data=json.dumps(payload))

# 6. 응답 결과 출력
if response.status_code == 200:
    print("API 호출 성공!")
    # JSON 형태의 응답 데이터를 파이썬 딕셔너리로 변환하여 출력
    result = response.json()
    print(json.dumps(result, indent=4, ensure_ascii=False))
else:
    print(f"API 호출 실패 (상태 코드: {response.status_code})")
    print(response.text)


# 삭제된 사업자등록정보는 조회되지 않으며, 해당 정보를 요청시에는 아래와 같은 메세지가 return됩니다:
# 상태조회: '국세청에 등록되지 않은 사업자등록번호입니다'