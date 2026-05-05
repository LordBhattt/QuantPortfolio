from __future__ import annotations

import uuid

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("jose")
pytest.importorskip("multipart")
pytest.importorskip("passlib")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.database import get_db
from backend.models.investor_profile import investor_profiles
from backend.models.portfolio import portfolios
from backend.routers import auth as auth_router
from backend.routers import onboarding as onboarding_router


def _create_test_app(session_factory) -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router.router)
    app.include_router(onboarding_router.router)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    return app


def _register_user(client: TestClient, email: str = "investor@example.com") -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "full_name": "Investor"},
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
async def test_onboarding_profile_upsert_and_risk_score(sqlite_session_factory) -> None:
    app = _create_test_app(sqlite_session_factory)
    client = TestClient(app)

    user_id = _register_user(client)
    initial_payload = {
        "investment_amount": 250000,
        "investment_horizon": "long_term",
        "risk_appetite": "aggressive",
        "income_stability": "stable",
        "existing_investments": True,
        "age_group": "26-35",
    }

    first_response = client.post("/api/v1/onboarding/profile", json=initial_payload)
    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["user_id"] == user_id
    assert 8 <= first_payload["risk_score"] <= 10

    updated_payload = {
        "investment_amount": 500000,
        "investment_horizon": "medium_term",
        "risk_appetite": "moderate",
        "income_stability": "variable",
        "existing_investments": False,
        "age_group": "36-50",
    }

    second_response = client.post("/api/v1/onboarding/profile", json=updated_payload)
    assert second_response.status_code == 200
    second_payload = second_response.json()
    assert second_payload["id"] == first_payload["id"]
    assert 5 <= second_payload["risk_score"] <= 7

    async with sqlite_session_factory() as session:
        result = await session.execute(select(investor_profiles).where(investor_profiles.c.user_id == uuid.UUID(user_id)))
        rows = result.mappings().all()

    assert len(rows) == 1
    assert rows[0]["investment_amount"] == 500000


@pytest.mark.asyncio
async def test_recommend_route_creates_portfolio_once(sqlite_session_factory) -> None:
    app = _create_test_app(sqlite_session_factory)
    client = TestClient(app)

    _register_user(client, email="reco@example.com")
    profile_payload = {
        "investment_amount": 100000,
        "investment_horizon": "short_term",
        "risk_appetite": "conservative",
        "income_stability": "variable",
        "existing_investments": False,
        "age_group": "50+",
    }

    profile_response = client.post("/api/v1/onboarding/profile", json=profile_payload)
    assert profile_response.status_code == 200

    first_response = client.post("/api/v1/onboarding/recommend")
    assert first_response.status_code == 200
    allocations = first_response.json()
    assert allocations[0]["ticker"] == "LIQUIDBEES.NS"
    assert round(sum(item["recommended_weight"] for item in allocations), 10) == 1.0

    second_response = client.post("/api/v1/onboarding/recommend")
    assert second_response.status_code == 200

    async with sqlite_session_factory() as session:
        result = await session.execute(select(portfolios).where(portfolios.c.user_id == uuid.UUID(profile_response.json()["user_id"])))
        rows = result.mappings().all()

    assert len(rows) == 1
    assert rows[0]["name"] == "My Recommended Portfolio"