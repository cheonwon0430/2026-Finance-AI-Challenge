"""app/domain/company/exceptions.py 의 예외 클래스 동작을 검증한다."""
from app.domain.company.exceptions import (
    AmbiguousCompanyNameError,
    CompanyNotFoundError,
    ExternalAPIError,
)


def test_ambiguous_company_name_error_는_기업명과_후보목록을_담는다():
    candidates = [
        {
            "corp_code": "00126380",
            "corp_name": "삼성전자",
            "stock_code": "005930",
            "modify_date": "20230101",
        },
        {
            "corp_code": "00164779",
            "corp_name": "삼성전자서비스",
            "stock_code": "",
            "modify_date": "20230101",
        },
    ]

    error = AmbiguousCompanyNameError("삼성", candidates)

    assert error.company_name == "삼성"
    assert error.candidates == candidates
    assert "삼성" in str(error)
    assert "2건" in str(error)


def test_company_not_found_error_는_일반_예외처럼_동작한다():
    error = CompanyNotFoundError("'없는회사' 에 매칭되는 기업이 없습니다.")

    assert isinstance(error, Exception)
    assert "없는회사" in str(error)


def test_external_api_error_는_일반_예외처럼_동작한다():
    error = ExternalAPIError("KIPRIS 특허 조회 실패: company_name=핀샷")

    assert isinstance(error, Exception)
    assert "핀샷" in str(error)
