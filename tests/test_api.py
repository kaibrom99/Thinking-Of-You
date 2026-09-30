import itertools
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

os.environ["TOY_DB"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "test.db")  # never touches your real data
import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

client = TestClient(main.app)
_n = itertools.count()
TARGET = "https://www.target.com/p/thing/-/A-1234"


@pytest.fixture(autouse=True)
def fresh_limits():
    main._hits.clear()


def signup(name="Alex", pw="pass1234"):
    email = f"user{next(_n)}@test.com"
    r = client.post("/register", json={"email": email, "name": name, "password": pw})
    assert r.status_code == 200, r.text
    return {"email": email, "pw": pw, "h": {"Authorization": "Bearer " + r.json()["token"]}}


def link(a, b):
    code = client.post("/partner/invite", headers=a["h"]).json()["code"]
    assert client.post("/partner/accept", json={"code": code}, headers=b["h"]).status_code == 200


def event(u, url=TARGET, kind="view"):
    return client.post("/events", headers=u["h"], json={"url": url, "title": "Thing", "price": 9.5, "event": kind})


def tracker():
    u = signup()
    client.post("/consent", headers=u["h"])
    return u


def mine(u):
    return client.get("/items/me", headers=u["h"]).json()


def test_weak_password_rejected():
    r = client.post("/register", json={"email": "weak@test.com", "name": "W", "password": "short"})
    assert r.status_code == 422


def test_login_works_and_wrong_password_fails():
    u = signup()
    assert client.post("/login", json={"email": u["email"], "password": "nope"}).status_code == 401
    assert client.post("/login", json={"email": u["email"], "password": u["pw"]}).status_code == 200


def test_expired_login_is_rejected():
    u = signup()
    assert client.get("/me", headers=u["h"]).status_code == 200
    with Session(main.engine) as s:
        for row in s.exec(select(main.LoginToken)).all():
            row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
            s.add(row)
        s.commit()
    assert client.get("/me", headers=u["h"]).status_code == 401


def test_logout_ends_the_login():
    u = signup()
    client.post("/logout", headers=u["h"])
    assert client.get("/me", headers=u["h"]).status_code == 401


def test_login_rate_limit():
    u = signup()
    bad = {"email": u["email"], "password": "wrong-password"}
    for _ in range(8):
        assert client.post("/login", json=bad).status_code == 401
    assert client.post("/login", json=bad).status_code == 429


def test_private_items_are_hidden_from_partner():
    a, b = signup("Alex"), signup("Sam")
    link(a, b)
    item = client.post("/items", headers=a["h"], json={"title": "Gift", "private": True}).json()
    assert client.get("/items/partner", headers=b["h"]).json() == []
    assert len(mine(a)) == 1
    client.patch(f"/items/{item['id']}/private", headers=a["h"], json={"private": False})
    assert len(client.get("/items/partner", headers=b["h"]).json()) == 1


def test_bad_link_is_rejected():
    u = signup()
    r = client.post("/items", headers=u["h"], json={"title": "X", "url": "javascript:alert(1)"})
    assert r.status_code == 422


def test_tracking_needs_consent():
    u = signup()
    assert event(u).json() == {"tracked": False}
    client.post("/consent", headers=u["h"])
    assert event(u).json() == {"tracked": True}
    assert mine(u)[0]["score"] == 1


def test_views_cooldown_and_cart_weight():
    u = tracker()
    event(u)
    event(u)  # repeat view inside the cooldown: not counted
    assert mine(u)[0]["score"] == 1
    event(u, kind="cart")
    assert mine(u)[0]["score"] == 4


def test_non_product_pages_are_ignored():
    u = tracker()
    assert event(u, url="https://www.target.com/").json() == {"tracked": False}
    assert mine(u) == []


def test_same_product_different_links_is_one_item():
    u = tracker()
    event(u, url="https://www.target.com/p/thing/-/A-1234?preselect=99#lnk=x")
    event(u, url="https://target.com/p/other-slug/-/A-1234")
    assert len(mine(u)) == 1


def test_deleted_product_stays_deleted():
    u = tracker()
    event(u)
    client.delete(f"/items/{mine(u)[0]['id']}", headers=u["h"])
    assert mine(u) == []
    assert event(u).json() == {"tracked": False}


def test_delete_account():
    a, b = signup("Alex"), signup("Sam")
    link(a, b)
    assert client.request("DELETE", "/account", headers=a["h"], json={"password": "wrong-pass"}).status_code == 403
    assert client.request("DELETE", "/account", headers=a["h"], json={"password": a["pw"]}).status_code == 200
    assert client.post("/login", json={"email": a["email"], "password": a["pw"]}).status_code == 401
    assert client.get("/items/partner", headers=b["h"]).status_code == 404