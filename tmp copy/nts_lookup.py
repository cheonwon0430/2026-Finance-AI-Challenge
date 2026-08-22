"""
국세청 사업자등록정보 상태조회 (공공데이터포털 odcloud.kr).
DART에서 확보한 bizr_no(사업자등록번호, 10자리 숫자)를 넣어 폐업/휴업 여부를 확인한다.
"""
import json
import requests

BASE_URL = "https://api.odcloud.kr/api/nts-businessman/v1/status"
SERVICE_KEY = "f2c6d4368f027c88545f53a4b820545b1f26538ca6c5c8ceccaf98c1be827ea6"


def check_business_status(b_no_list: list[str], service_key: str = SERVICE_KEY) -> dict:
    params = {"serviceKey": service_key, "returnType": "JSON"}
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    payload = {"b_no": b_no_list}
    resp = requests.post(BASE_URL, params=params, headers=headers, data=json.dumps(payload))
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    import sys

    result = check_business_status(sys.argv[1:])
    print(json.dumps(result, ensure_ascii=False, indent=2))
