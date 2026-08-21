import requests

from app.common.config import settings

NTS_VALIDATE_URL = "https://api.odcloud.kr/api/nts-businessman/v1/validate"

NTS_VALID_MATCH = "01"  # 진위확인(valid): 사업자번호/대표자/개업일이 국세청 기록과 일치
NTS_STATUS_ACTIVE = "01"  # 상태조회(status.b_stt_cd): 계속사업자


def is_operating_business(bizr_no: str, ceo_nm: str, est_dt: str) -> bool:
    # DART는 공동대표를 "홍길동, 김철수"처럼 쉼표로 합쳐 주지만, 국세청 API는
    # 대표자를 p_nm(1인)/p_nm2(공동대표 2인째)로 나눠 받으므로 분리해서 넣는다.
    ceo_names = [name.strip() for name in ceo_nm.split(",") if name.strip()]

    business = {
        "b_no": bizr_no,
        "start_dt": est_dt,
        "p_nm": ceo_names[0],
    }
    if len(ceo_names) > 1:
        business["p_nm2"] = ceo_names[1]

    params = {"serviceKey": settings.nts_api_key}
    response = requests.post(NTS_VALIDATE_URL, params=params, json={"businesses": [business]})
    response.raise_for_status()

    data = response.json()["data"]
    if not data:
        return False

    result = data[0]

    # 1) 진위확인을 먼저 본다: 대표자/개업일이 국세청 기록과 다르면 상태와 무관하게
    #    "실존 확인 불가"이므로 상태값은 확인할 필요가 없다.
    valid_code = result.get("valid")
    if valid_code != NTS_VALID_MATCH:
        return False

    # 2) 진위확인을 통과한 경우에만 상태조회 값을 본다: 계속사업자(01)여야 "운영 중".
    status_code = result.get("status", {}).get("b_stt_cd")
    return status_code == NTS_STATUS_ACTIVE


if __name__ == "__main__":
    result = is_operating_business(
        bizr_no="1248100998",
        ceo_nm="김기남, 김현석, 고동진",
        est_dt="19690113",
    )
    print(result)
