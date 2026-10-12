"""Unit test: create_draft / create_reply_draft (exchange_mcp/tools/email.py).

No mailbox, no browser: a fake OWAClient records every request and scripts the
CreateItem answer. The tools are called directly with a stand-in MCP Context.

What this pins - above all, the one guarantee these tools exist for:
1. **Nothing is ever sent.** Every CreateItem a draft tool issues carries
   MessageDisposition "SaveOnly" and targets the Drafts folder, and no request
   anywhere contains a Send* disposition. A deployment that hides send_email
   via EXCHANGE_MCP_TOOLS relies on exactly this.
2. create_draft accepts a draft with no recipients and only writes the
   recipient fields it was given.
3. create_reply_draft maps reply / reply_all / forward to the right EWS
   response-object type, carries the ChangeKey it looked up, and rejects an
   unknown mode or a recipient-less forward *before* any request.
4. Results: the new draft's item_id is returned; an Error response surfaces
   as an error, not as success.

Run:
    python -m tests.unit.test_drafts
"""

import json
import sys
from types import SimpleNamespace

from exchange_mcp.owa_client import OWAClient
from exchange_mcp.tools.email import create_draft, create_reply_draft

_failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  OK   {name}")
        return
    _failures.append(f"{name}{': ' + detail if detail else ''}")
    print(f"  FAIL {name}{': ' + detail if detail else ''}")


class FakeBrowser:
    owa_url = "https://owa.example.com"
    profile_dir = "/tmp/profile"
    auth_mode = "canary"

    def identity_hints(self) -> dict:
        return {}


class FakeClient(OWAClient):
    def __init__(self, *, create_error: str = ""):
        super().__init__(FakeBrowser())
        self.create_error = create_error
        self.calls: list[tuple[str, dict]] = []

    def request(self, action, payload, *, timeout=30):
        self.calls.append((action, payload))
        if action == "GetItem":
            item_id = payload["Body"]["ItemIds"][0]["Id"]
            return {"Body": {"ResponseMessages": {"Items": [
                {"Items": [{"ItemId": {"Id": item_id, "ChangeKey": f"ck-{item_id}"}}]}
            ]}}}
        if action == "CreateItem":
            if self.create_error:
                return {"Body": {"ResponseMessages": {"Items": [
                    {"ResponseClass": "Error", "MessageText": self.create_error,
                     "ResponseCode": "ErrorInvalidRecipients"}
                ]}}}
            return {"Body": {"ResponseMessages": {"Items": [
                {"ResponseClass": "Success", "Items": [{"ItemId": {"Id": "draft-1", "ChangeKey": "x"}}]}
            ]}}}
        raise AssertionError(f"unexpected action: {action}")

    def creates(self) -> list[dict]:
        return [p["Body"] for a, p in self.calls if a == "CreateItem"]


def _ctx(client: OWAClient):
    return SimpleNamespace(request_context=SimpleNamespace(lifespan_context=SimpleNamespace(client=client)))


def _assert_saved_never_sent(label: str, client: FakeClient) -> None:
    creates = client.creates()
    check(f"{label}: exactly one CreateItem", len(creates) == 1, str(len(creates)))
    for body in creates:
        check(f"{label}: SaveOnly", body.get("MessageDisposition") == "SaveOnly", repr(body.get("MessageDisposition")))
        check(f"{label}: saved to Drafts",
              body.get("SavedItemFolderId", {}).get("BaseFolderId") ==
              {"__type": "DistinguishedFolderId:#Exchange", "Id": "drafts"},
              repr(body.get("SavedItemFolderId")))
    wire = json.dumps([p for _, p in client.calls])
    check(f"{label}: no Send* disposition anywhere", "SendAndSaveCopy" not in wire and "SendOnly" not in wire)


def test_create_draft() -> None:
    print("create_draft")
    client = FakeClient()
    result = json.loads(create_draft("Hallo", "Text", to="a@example.com, b@example.com", ctx=_ctx(client)))
    _assert_saved_never_sent("with recipients", client)
    item = client.creates()[0]["Items"][0]
    check("Message type", item["__type"] == "Message:#Exchange")
    check("two To recipients", [r["EmailAddress"] for r in item["ToRecipients"]] == ["a@example.com", "b@example.com"])
    check("no empty Cc/Bcc written", "CcRecipients" not in item and "BccRecipients" not in item, repr(item.keys()))
    check("plain text body", item["Body"]["BodyType"] == "Text")
    check("returns draft item_id", result.get("success") is True and result.get("item_id") == "draft-1", repr(result))
    check("says it was not sent", "NOT been sent" in result.get("message", ""), repr(result))

    client = FakeClient()
    result = json.loads(create_draft("Notiz", "<b>x</b>", is_html=True, ctx=_ctx(client)))
    _assert_saved_never_sent("no recipients", client)
    item = client.creates()[0]["Items"][0]
    check("no recipients is fine for a draft", "ToRecipients" not in item and result.get("success") is True, repr(result))
    check("html body", item["Body"]["BodyType"] == "HTML")

    client = FakeClient(create_error="The recipient is invalid.")
    result = json.loads(create_draft("x", "y", to="nope", ctx=_ctx(client)))
    check("Error response surfaces as error", result.get("error") == "The recipient is invalid." and "success" not in result,
          repr(result))


def test_create_reply_draft() -> None:
    print("create_reply_draft")
    for mode, ews_type, to in (
        ("reply", "ReplyToItem:#Exchange", ""),
        ("reply_all", "ReplyAllToItem:#Exchange", ""),
        ("forward", "ForwardItem:#Exchange", "c@example.com"),
    ):
        client = FakeClient()
        result = json.loads(create_reply_draft("orig-1", "Danke!", mode=mode, to=to, ctx=_ctx(client)))
        _assert_saved_never_sent(mode, client)
        item = client.creates()[0]["Items"][0]
        check(f"{mode}: EWS type", item["__type"] == ews_type, item["__type"])
        check(f"{mode}: references original with its ChangeKey",
              item["ReferenceItemId"] == {"__type": "ItemId:#Exchange", "Id": "orig-1", "ChangeKey": "ck-orig-1"},
              repr(item["ReferenceItemId"]))
        check(f"{mode}: new body text", item["NewBodyContent"]["Value"] == "Danke!")
        check(f"{mode}: recipients only when given", ("ToRecipients" in item) == bool(to), repr(item.keys()))
        check(f"{mode}: returns draft item_id", result.get("item_id") == "draft-1", repr(result))

    client = FakeClient()
    result = json.loads(create_reply_draft("orig-1", "x", mode="forward", ctx=_ctx(client)))
    check("forward without recipient rejected", "error" in result, repr(result))
    check("...before any request", client.calls == [], repr(client.calls))

    client = FakeClient()
    result = json.loads(create_reply_draft("orig-1", "x", mode="send", ctx=_ctx(client)))
    check("unknown mode rejected", "error" in result and "mode" in result["error"], repr(result))
    check("...before any request", client.calls == [], repr(client.calls))


def main() -> bool:
    for test in (test_create_draft, test_create_reply_draft):
        test()
    print()
    if _failures:
        print(f"{len(_failures)} check(s) failed:")
        for failure in _failures:
            print(f"  - {failure}")
        return False
    print("All checks passed.")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
