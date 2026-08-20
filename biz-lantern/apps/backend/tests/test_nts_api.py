from unittest.mock import Mock, patch

import requests

from apps.backend.app.domain.company.api.nts_api import read_business_status


def test_read_business_status_success():
    business_numbers = ["1248100998"]
    expected_response = {
        "status_code": "OK",
        "data": [
            {
                "b_no": "1248100998",
                "b_stt": "계속사업자",
            }
        ],
    }

    mock_response = Mock()
    mock_response.json.return_value = expected_response
    mock_response.raise_for_status.return_value = None

    with patch("app.domain.company.api.nts_api.settings.nts_api_key", "encoded%2Bapi%2Fkey"):
        with patch(
            "app.domain.company.api.nts_api.requests.post",
            return_value=mock_response,
        ) as mock_post:
            result = read_business_status(business_numbers)

    assert result == expected_response
    mock_post.assert_called_once_with(
        "https://api.odcloud.kr/api/nts-businessman/v1/status",
        params={
            "serviceKey": "encoded+api/key",
            "returnType": "JSON",
        },
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json={"b_no": business_numbers},
        timeout=10,
    )


def test_read_business_status_empty_list():
    result = read_business_status([])

    assert result is None


def test_read_business_status_over_100_numbers():
    business_numbers = [str(number) for number in range(101)]

    result = read_business_status(business_numbers)

    assert result is None


def test_read_business_status_timeout():
    with patch(
        "app.domain.company.api.nts_api.requests.post",
        side_effect=requests.exceptions.Timeout,
    ):
        result = read_business_status(["1248100998"])

    assert result is None


def test_read_business_status_request_error():
    with patch(
        "app.domain.company.api.nts_api.requests.post",
        side_effect=requests.exceptions.RequestException("API error"),
    ):
        result = read_business_status(["1248100998"])

    assert result is None


def test_read_business_status_invalid_json():
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.side_effect = ValueError

    with patch(
        "app.domain.company.api.nts_api.requests.post",
        return_value=mock_response,
    ):
        result = read_business_status(["1248100998"])

    assert result is None