"""End-to-end REST API tests covering auth, RBAC and the review lifecycle."""
from __future__ import annotations

from tests.conftest import API, auth_headers, simulate_generation


async def test_login_and_me(client):
    headers = await auth_headers(client, "artist", "artist123")
    r = await client.get(f"{API}/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["role"] == "executor"


async def test_login_bad_credentials(client):
    r = await client.post(
        f"{API}/auth/login", json={"username": "artist", "password": "nope"}
    )
    assert r.status_code == 401


async def test_requires_auth(client):
    r = await client.get(f"{API}/packages")
    assert r.status_code in (401, 403)


async def test_director_cannot_create_package(client):
    headers = await auth_headers(client, "director", "director123")
    r = await client.post(f"{API}/packages", json={"name": "X"}, headers=headers)
    assert r.status_code == 403


async def test_executor_cannot_review(client):
    headers = await auth_headers(client, "artist", "artist123")
    r = await client.post(
        f"{API}/packages/000000000000000000000000/review",
        json={"decision": "approve"},
        headers=headers,
    )
    assert r.status_code == 403


async def test_generate_enqueues_job(client):
    headers = await auth_headers(client, "artist", "artist123")
    pid = (
        await client.post(f"{API}/packages", json={"name": "P"}, headers=headers)
    ).json()["id"]
    r = await client.post(
        f"{API}/packages/{pid}/generate",
        json={
            "prompt": "a cat",
            "batch_size": 2,
            "llm_expand": False,
            "params": {"workflow_type": "character"},
        },
        headers=headers,
    )
    assert r.status_code == 202
    job = r.json()
    assert job["status"] == "pending"
    assert job["batch_size"] == 2
    r = await client.get(f"{API}/jobs/{job['id']}", headers=headers)
    assert r.status_code == 200


async def test_full_package_lifecycle(client, storage):
    artist = await auth_headers(client, "artist", "artist123")
    director = await auth_headers(client, "director", "director123")

    me = (await client.get(f"{API}/auth/me", headers=artist)).json()
    owner_id = me["id"]

    created = await client.post(
        f"{API}/packages",
        json={"name": "Goblins", "description": "enemy set"},
        headers=artist,
    )
    assert created.status_code == 201
    pid = created.json()["id"]
    assert created.json()["status"] == "draft"

    # Cannot submit an empty package.
    r = await client.post(f"{API}/packages/{pid}/submit", headers=artist)
    assert r.status_code == 409

    # Simulate a finished generation of 3 assets.
    await simulate_generation(pid, owner_id, storage, n=3)
    imgs = await client.get(f"{API}/packages/{pid}/images", headers=artist)
    assert len(imgs.json()) == 3

    # Submit for review.
    r = await client.post(f"{API}/packages/{pid}/submit", headers=artist)
    assert r.status_code == 200 and r.json()["status"] == "pending_review"

    # Director sees it and cannot download before approval.
    listing = await client.get(f"{API}/packages?status=pending_review", headers=director)
    assert any(p["id"] == pid for p in listing.json())
    early = await client.get(f"{API}/packages/{pid}/download", headers=director)
    assert early.status_code == 409

    # Approve and download the production zip.
    approved = await client.post(
        f"{API}/packages/{pid}/review",
        json={"decision": "approve", "comment": "on-brand"},
        headers=director,
    )
    assert approved.status_code == 200 and approved.json()["status"] == "approved"

    zipped = await client.get(f"{API}/packages/{pid}/download", headers=director)
    assert zipped.status_code == 200
    assert zipped.headers["content-type"] == "application/zip"
    assert zipped.content[:2] == b"PK"


async def test_reject_flow_allows_resubmit(client, storage):
    artist = await auth_headers(client, "artist", "artist123")
    director = await auth_headers(client, "director", "director123")
    owner_id = (await client.get(f"{API}/auth/me", headers=artist)).json()["id"]

    pid = (
        await client.post(f"{API}/packages", json={"name": "Props"}, headers=artist)
    ).json()["id"]
    await simulate_generation(pid, owner_id, storage, n=1)
    await client.post(f"{API}/packages/{pid}/submit", headers=artist)

    rejected = await client.post(
        f"{API}/packages/{pid}/review",
        json={"decision": "reject", "comment": "fix outlines"},
        headers=director,
    )
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["review_comment"] == "fix outlines"

    # Rejected package can be re-submitted after edits.
    r = await client.post(f"{API}/packages/{pid}/submit", headers=artist)
    assert r.status_code == 200 and r.json()["status"] == "pending_review"
