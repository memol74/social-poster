from uploaders.tiktok import _init_upload


class FakeResponse:
    def __init__(self, ok, status_code, text, payload):
        self.ok = ok
        self.status_code = status_code
        self.text = text
        self._payload = payload

    def json(self):
        return self._payload


responses = [
    FakeResponse(True, 200, "", {"error": {"code": "unaudited_client_can_only_post_to_private_accounts"}}),
    FakeResponse(True, 200, "", {"error": {"code": "ok"}, "data": {"publish_id": "pub123", "upload_url": "https://example.com/upload"}}),
]


def fake_post(*args, **kwargs):
    return responses.pop(0)


import uploaders.tiktok as tiktok

original_post = tiktok.requests.post
tiktok.requests.post = fake_post

try:
    try:
        _init_upload({}, "desc", "PUBLIC_TO_EVERYONE", 100, 100, 1)
    except Exception as exc:
        print(str(exc))

    resp = _init_upload({}, "desc", "SELF_ONLY", 100, 100, 1)
    print(resp["data"]["publish_id"])
finally:
    tiktok.requests.post = original_post