import pytest

from nonprofit_archive.infrai_gateway import InfraiError, InfraiGateway


class FakeResponse:
    status_code = 400
    headers: dict[str, str] = {}

    def json(self) -> dict:
        return {"ok": False, "data": None, "error": {"code": "BAD_SCAN", "message": "scan rejected"}, "metadata": {}}

    def raise_for_status(self) -> None:
        raise AssertionError("status handling ran before envelope handling")


class FakeSession:
    def __init__(self) -> None:
        self.request_kwargs: dict = {}

    def request(self, **kwargs: object) -> FakeResponse:
        self.request_kwargs = kwargs
        return FakeResponse()


def test_business_envelope_is_read_before_http_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("nonprofit_archive.infrai_gateway.OpenAI", lambda **_: object())
    session = FakeSession()
    gateway = InfraiGateway(api_key="test-key", session=session)

    with pytest.raises(InfraiError) as raised:
        gateway.create_collection("test-archive", 3)

    assert raised.value.code == "BAD_SCAN"
    assert session.request_kwargs["method"] == "POST"
    assert session.request_kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert session.request_kwargs["headers"]["Idempotency-Key"] == "collection-test-archive"
