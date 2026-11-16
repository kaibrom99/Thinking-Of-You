import itertools
import base64
import io
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

os.environ["TOY_DB"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "test.db")  # never touches your real data
import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, select  # noqa: E402
from PIL import Image  # noqa: E402

client = TestClient(main.app)
_n = itertools.count()
TARGET = "https://www.target.com/p/thing/-/A-1234"


@pytest.fixture(autouse=True)
def fresh_limits():
    main._hits.clear()


def signup(name="Alex", pw="pass1234"):
    email = f"user{next(_n)}@test.com"
    r = client.post("/register", json={"email": email, "name": name, "password": pw, "age_confirmed": True})
    assert r.status_code == 200, r.text
    return {"email": email, "pw": pw, "h": {"Authorization": "Bearer " + r.json()["token"]}}


def link(a, b, label="Partner"):
    code = client.post("/invites", headers=a["h"], json={"label": label}).json()["code"]
    r = client.post("/invites/accept", json={"code": code}, headers=b["h"])
    assert r.status_code == 200, r.text
    return r.json()


def uid(u):
    return client.get("/me", headers=u["h"]).json()["id"]


def seen_by(viewer, owner):
    return client.get(f"/people/{uid(owner)}/items", headers=viewer["h"])


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
    assert seen_by(b, a).json() == []
    assert len(mine(a)) == 1
    client.patch(f"/items/{item['id']}/private", headers=a["h"], json={"private": False})
    assert len(seen_by(b, a).json()) == 1


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


def test_view_cooldown_uses_last_counted_view_not_last_event():
    u = tracker()
    event(u)
    with Session(main.engine) as s:
        item = s.exec(select(main.Item).where(main.Item.owner_id == uid(u))).first()
        item.last_view_counted_at = datetime.now(timezone.utc) - timedelta(minutes=11)
        item.last_seen = datetime.now(timezone.utc)
        s.add(item)
        s.commit()
    event(u)
    assert mine(u)[0]["score"] == 2


def test_owner_can_adjust_priority_points():
    owner, other = signup(), signup()
    link(owner, other)
    first = client.post("/items", headers=owner["h"], json={"title": "Book"}).json()
    item = client.post("/items", headers=owner["h"], json={"title": "Lamp"}).json()
    path = f"/items/{item['id']}/score-adjustment"
    assert [i["id"] for i in mine(owner)] == [first["id"], item["id"]]
    changed = client.post(path, headers=owner["h"], json={"delta": 8})
    assert changed.status_code == 200 and changed.json()["score"] == 13
    assert mine(owner)[0]["id"] == item["id"]
    assert seen_by(other, owner).json()[0]["id"] == item["id"]
    assert client.post(path, headers=other["h"], json={"delta": -2}).status_code == 404
    assert client.post(path, json={"delta": 1}).status_code == 401
    assert client.post(path, headers=owner["h"], json={"delta": -9}).json()["score"] == 4
    assert mine(owner)[-1]["id"] == item["id"]
    assert seen_by(other, owner).json()[-1]["score"] == 4
    assert client.post(path, headers=owner["h"], json={"delta": -100}).json()["score"] == 0
    assert client.post(path, headers=owner["h"], json={"delta": 1}).json()["score"] == 1


def test_gift_claim_and_purchased_status_are_hidden_from_list_owner():
    owner, gifter, other = signup("Owner"), signup("Gifter"), signup("Other")
    link(owner, gifter)
    link(owner, other)
    item = client.post("/items", headers=owner["h"], json={"title": "Book"}).json()
    claim_path = f"/people/{uid(owner)}/items/{item['id']}/claim"
    assert client.post(claim_path, headers=gifter["h"]).status_code == 200
    owner_items = mine(owner)
    assert "gift_status" not in owner_items[0]
    shared = seen_by(other, owner).json()[0]
    assert shared["gift_status"] == "claimed" and not shared["claimed_by_me"]
    assert client.post(claim_path, headers=other["h"]).status_code == 409
    assert client.patch(claim_path, headers=gifter["h"], json={"purchased": True}).json()["gift_status"] == "purchased"
    assert seen_by(other, owner).json()[0]["gift_status"] == "purchased"
    assert client.delete(claim_path, headers=gifter["h"]).status_code == 200
    assert seen_by(other, owner).json()[0]["gift_status"] == "available"


def test_curator_sublists_are_not_visible_to_the_list_owner():
    owner, curator = signup("Owner"), signup("Curator")
    link(owner, curator)
    item = client.post("/items", headers=owner["h"], json={"title": "Mug"}).json()
    base = f"/people/{uid(owner)}/sublists"
    created = client.post(base, headers=curator["h"], json={"title": "Small spontaneous gifts"})
    assert created.status_code == 200
    sublist_id = created.json()["id"]
    assert client.post(f"/sublists/{sublist_id}/items", headers=curator["h"], json={"item_id": item["id"]}).status_code == 200
    assert len(client.get(base, headers=curator["h"]).json()[0]["items"]) == 1
    assert client.get(f"/people/{uid(curator)}/sublists", headers=owner["h"]).json() == []


def test_profile_photo_can_be_added_at_signup_edited_and_seen_by_connections():
    buf = io.BytesIO()
    Image.new("RGB", (300, 180), "purple").save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    email = f"photo{next(_n)}@test.com"
    created = client.post("/register", json={"email": email, "name": "Photo User", "password": "pass1234",
                                             "age_confirmed": True, "profile_photo": encoded})
    assert created.status_code == 200
    user = {"email": email, "pw": "pass1234", "h": {"Authorization": "Bearer " + created.json()["token"]}}
    friend = signup("Friend")
    link(user, friend)
    photo = client.get("/me", headers=user["h"]).json()["profile_photo"]
    assert photo and base64.b64decode(photo).startswith(b"\xff\xd8")
    assert client.get("/connections", headers=friend["h"]).json()[0]["profile_photo"] == photo
    assert client.put("/profile/photo", headers=user["h"], json={"photo": "not-an-image"}).status_code == 422
    assert client.delete("/profile/photo", headers=user["h"]).json()["profile_photo"] == ""
    assert client.get("/connections", headers=friend["h"]).json()[0]["profile_photo"] == ""


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
    assert client.get("/connections", headers=b["h"]).json() == []


def test_one_parent_many_kids_and_kids_cannot_see_each_other():
    parent, kid1, kid2 = signup("Mom"), signup("Ann"), signup("Bob")
    link(parent, kid1, "Child")
    link(parent, kid2, "Child")
    client.post("/items", headers=kid1["h"], json={"title": "Skates"})
    client.post("/items", headers=kid2["h"], json={"title": "Lego set"})
    client.post("/items", headers=parent["h"], json={"title": "Book"})
    assert len(client.get("/connections", headers=parent["h"]).json()) == 2
    assert [c["label"] for c in client.get("/connections", headers=kid1["h"]).json()] == ["Parent"]
    assert seen_by(parent, kid1).json()[0]["title"] == "Skates"
    assert seen_by(kid1, parent).json()[0]["title"] == "Book"
    assert seen_by(kid1, kid2).status_code == 404


def test_strangers_cannot_see_lists():
    a, b = signup(), signup()
    assert seen_by(a, b).status_code == 404


def test_invite_codes_work_once():
    a, b, c = signup(), signup(), signup()
    code = client.post("/invites", headers=a["h"], json={"label": "Friend"}).json()["code"]
    assert len(code) == 24
    assert client.post("/invites/accept", json={"code": code}, headers=b["h"]).status_code == 200
    assert client.post("/invites/accept", json={"code": code}, headers=c["h"]).status_code == 400


def test_disconnect_removes_access():
    a, b = signup(), signup()
    conn = link(a, b)
    assert client.delete(f"/connections/{conn['id']}", headers=b["h"]).status_code == 200
    assert seen_by(a, b).status_code == 404


def test_sign_up_requires_age_confirmation():
    r = client.post("/register", json={"email": "kid@test.com", "name": "K", "password": "pass1234"})
    assert r.status_code == 400


def test_categories_store_and_images():
    u = tracker()
    client.post("/events", headers=u["h"], json={"url": TARGET, "title": "Gentle Facial Cleanser 8 oz", "price": 9.5,
                                                 "event": "view", "image": "https://img.example.com/a.jpg"})
    item = mine(u)[0]
    assert item["category"] == "Self-care & beauty" and item["store"] == "Target"
    assert item["image_url"] == "https://img.example.com/a.jpg"
    client.patch(f"/items/{item['id']}/category", headers=u["h"], json={"category": "Other"})
    assert mine(u)[0]["category"] == "Other"
    assert client.patch(f"/items/{item['id']}/category", headers=u["h"], json={"category": "Nope"}).status_code == 422


def test_category_guessing_examples():
    from catalog import guess_category
    assert guess_category("Weight Lifting Wrist Strap, Leather") == "Sports & fitness"
    assert guess_category("Women's Fleece Lined Loose Sweatshirt") == "Clothes"
    assert guess_category("Air Zoom Running Shoes") == "Shoes"
    assert guess_category("Unknown thing xyz", "", "https://www.sephora.com/product/x-P123") == "Self-care & beauty"


def test_checkout_pages_are_not_products():
    from catalog import is_product_url, looks_like_product
    assert not is_product_url("https://poshmark.com/listing/x-0123456789abcdef01234567/checkout")
    assert is_product_url("https://poshmark.com/listing/x-0123456789abcdef01234567")
    assert not looks_like_product("Checkout - Poshmark")
    u = tracker()
    r = client.post("/events", headers=u["h"], json={"url": TARGET, "title": "Checkout - Target", "event": "view"})
    assert r.json() == {"tracked": False}


def test_specialty_stores_and_new_keywords():
    from catalog import guess_category
    assert guess_category("The Love Hypothesis", "a bestseller ... mirror", "https://www.barnesandnoble.com/w/x/123") == "Books & media"
    assert guess_category("Iconic Trainer Moments Pok\u00e9 Ball", "gamer decor", "https://www.lego.com/en-us/product/x-1") == "Toys & games"
    assert guess_category("Hermes Gold and Black H-Logo Enamel Bangle") == "Accessories & jewelry"
    assert guess_category("Taylor Farms Snap Peas & Tomatoes Vegetable Tray with Ranch Dip") == "Food & drink"


def test_newer_photo_replaces_older_one():
    u = tracker()
    for img in ("https://img.example.com/old.jpg", "https://img.example.com/new.jpg"):
        client.post("/events", headers=u["h"], json={"url": TARGET, "title": "Thing", "price": 9.5, "event": "view", "image": img})
    assert mine(u)[0]["image_url"] == "https://img.example.com/new.jpg"
