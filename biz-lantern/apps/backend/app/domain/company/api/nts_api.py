import requests
import logging
from typing import List, Dict, Optional
from urllib.parse import unquote

from app.common.config import settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def read_company_status(b_no_list: List[str]) -> Optional[Dict]:
    """
    국세청 API를 활용하여 사업자등록상태를 조회합니다.

    ### response.json()
    ```JSON
        {
        "request_cnt": 2,
        "match_cnt": 2,
        "status_code": "OK",
        "data": [
            {
                "b_no": "1248100998",
                "b_stt": "계속사업자",
                "b_stt_cd": "01",
                "tax_type": "부가가치세 일반과세자",
                "tax_type_cd": "01",
                "end_dt": "",
                "utcc_yn": "N",
                "tax_type_change_dt": "",
                "invoice_apply_dt": "",
                "rbf_tax_type": "해당없음",
                "rbf_tax_type_cd": "99",
            },
            {
                "b_no": "1268103725",
                "b_stt": "계속사업자",
                "b_stt_cd": "01",
                "tax_type": "부가가치세 일반과세자",
                "tax_type_cd": "01",
                "end_dt": "",
                "utcc_yn": "N",
                "tax_type_change_dt": "",
                "invoice_apply_dt": "",
                "rbf_tax_type": "해당없음",
                "rbf_tax_type_cd": "99",
            },
        ],
    }
    ```
    """
    # 1. pydantic_settings 객체에서 API 키 안전하게 가져오기
    # 이미 config 로드 단계에서 검증되었으므로 None 체크를 생략할 수 있습니다.
    api_key = settings.nts_api_key

    base_url = "https://api.odcloud.kr/api/nts-businessman/v1/status"
    params = {"serviceKey": unquote(api_key), "returnType": "JSON"}
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    payload = {"b_no": b_no_list}

    # 2. API 요청 및 예외 처리
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
