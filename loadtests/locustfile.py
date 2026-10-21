"""Locust scenario for Galactic Auction (Lab 4).

Each virtual user registers, logs in, tops up the balance and then behaves
like a typical bidder: browses lots, looks at details and places bids.
"""

import os
import random
import uuid
from datetime import datetime, timedelta, timezone

import requests
from locust import HttpUser, between, events, task

PASSWORD = "LoadTest-123!"
ADMIN_USERNAME = os.getenv("LOAD_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("LOAD_ADMIN_PASSWORD")
# business rejections (price too low, outbid yourself...) are not server errors
EXPECTED_REJECTIONS = {400, 402, 409, 422}

state = {"auction_id": None, "accepted": 0, "rejected": 0}


@events.test_start.add_listener
def prepare_auction(environment, **_):
    """Create one long-running auction that all virtual users bid on."""
    preset = os.getenv("LOAD_AUCTION_ID")
    if preset:
        state["auction_id"] = int(preset)
        return
    if not ADMIN_PASSWORD:
        raise RuntimeError("Set LOAD_ADMIN_PASSWORD (admin password)")

    host = environment.host.rstrip("/")
    login = requests.post(
        f"{host}/auth/login",
        data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    login.raise_for_status()
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    artifact = requests.post(
        f"{host}/artifacts",
        json={"name": "Load test artifact"},
        headers=headers,
        timeout=30,
    )
    artifact.raise_for_status()

    now = datetime.now(timezone.utc)
    auction = requests.post(
        f"{host}/auctions",
        json={
            "artifact_id": artifact.json()["id"],
            "starting_price": "100",
            "starts_at": (now - timedelta(minutes=1)).isoformat(),
            "ends_at": (now + timedelta(hours=3)).isoformat(),
        },
        headers=headers,
        timeout=30,
    )
    auction.raise_for_status()
    state["auction_id"] = auction.json()["id"]
    print(f"Load-test auction id: {state['auction_id']}")


@events.test_stop.add_listener
def report_bids(environment, **_):
    print(f"Bids accepted: {state['accepted']}, rejected: {state['rejected']}")


class Bidder(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        username = f"lt_{uuid.uuid4().hex[:12]}"
        self.client.post(
            "/auth/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": PASSWORD,
            },
            name="[setup] POST /auth/register",
        )
        login = self.client.post(
            "/auth/login",
            data={"username": username, "password": PASSWORD},
            name="POST /auth/login",
        )
        if login.status_code != 200:
            self.stop()
            return
        self.client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        me = self.client.get("/users/me", name="GET /users/me")
        self.user_id = me.json()["id"]
        self.client.post(
            f"/users/{self.user_id}/deposit",
            json={"amount": "500000"},
            name="[setup] POST /users/[id]/deposit",
        )

    @task(5)
    def list_auctions(self):
        self.client.get("/auctions", params={"limit": 20}, name="GET /auctions")

    @task(4)
    def view_auction(self):
        self.client.get(f"/auctions/{state['auction_id']}", name="GET /auctions/[id]")

    @task(3)
    def view_bids(self):
        self.client.get(
            f"/auctions/{state['auction_id']}/bids",
            params={"limit": 50},
            name="GET /auctions/[id]/bids",
        )

    @task(1)
    def profile(self):
        self.client.get("/users/me", name="GET /users/me")

    @task(1)
    def index(self):
        self.client.get("/", name="GET /")

    @task(2)
    def place_bid(self):
        auction_id = state["auction_id"]
        auction = self.client.get(f"/auctions/{auction_id}", name="GET /auctions/[id]")
        if auction.status_code != 200:
            return
        amount = float(auction.json()["current_price"]) + random.randint(1, 25)
        with self.client.post(
            f"/auctions/{auction_id}/bids",
            json={"amount": f"{amount:.2f}"},
            name="POST /auctions/[id]/bids",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 201):
                state["accepted"] += 1
                response.success()
            elif response.status_code in EXPECTED_REJECTIONS:
                state["rejected"] += 1
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")
