import requests
import logging
from typing import List, Dict, Optional
from urllib.parse import unquote


def get_business_status(b_no_list: List[str]) -> Optional[Dict]:
    """
    국세청 API를 활용하여 사업자등록상태를 조회합니다.
    """
    # 1. 입력값 검증
    if not b_no_list:
        logging.warning("조회할 사업자번호가 없습니다.")
        return None

    if len(b_no_list) > 100:
        logging.error("한 번에 최대 100개의 사업자번호만 조회할 수 있습니다.")
        return None

    # 2. pydantic_settings 객체에서 API 키 안전하게 가져오기
    # 이미 config 로드 단계에서 검증되었으므로 None 체크를 생략할 수 있습니다.
    api_key = "vw2EnZ0GgIZHggwDsu7aUHke764BQdqeKf5lKhPTeHutsRpAtgmD7OJlVeTbpbB2TIZ4RavZN01PSlcYZx%2B2aA%3D%3D"

    base_url = "https://api.odcloud.kr/api/nts-businessman/v1/status"
    params = {"serviceKey": unquote(api_key), "returnType": "JSON"}
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    payload = {"b_no": b_no_list}

    # 3. API 요청 및 예외 처리
    try:
        response = requests.post(
            base_url, params=params, headers=headers, json=payload, timeout=10
        )

        response.raise_for_status()

        logging.info(f"API 호출 성공! ({len(b_no_list)}건 조회)")
        return response.json()

    except requests.exceptions.Timeout:
        logging.error("API 요청 시간이 초과되었습니다. (Timeout)")
    except requests.exceptions.RequestException as e:
        logging.error(f"API 요청 중 오류가 발생했습니다: {e}")
    except ValueError:
        logging.error("응답 데이터를 JSON으로 변환하는 데 실패했습니다.")

    return None


# ==========================================
# 실행 테스트 (테스트 시 .env 파일이 같은 경로에 있어야 함)
# ==========================================
if __name__ == "__main__":
    test_b_no_list = ["1248100998", "1268103725"]
    result_data = get_business_status(test_b_no_list)

    if result_data:
        for item in result_data.get("data", []):
            b_no = item.get("b_no")
            status = item.get("b_stt", "상태불명")
            print(f"사업자번호: {b_no} -> 운영상태: {status}")
