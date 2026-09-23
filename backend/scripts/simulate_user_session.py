import asyncio
import httpx
import sys

BASE_URL = "http://127.0.0.1:8000/api/v1"

async def main():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        print("1. Registering user...")
        res = await client.post("/auth/register", json={"email": "test_e2e@example.com", "password": "Password123"})
        if res.status_code not in (201, 400):  # 400 if already exists
            print(f"Failed to register: {res.text}")
            sys.exit(1)
            
        print("2. Logging in...")
        res = await client.post("/auth/token", data={"username": "test_e2e@example.com", "password": "Password123"})
        if res.status_code != 200:
            print(f"Failed to login: {res.text}")
            sys.exit(1)
        
        print("3. Creating portfolio...")
        res = await client.post("/portfolios/", json={"name": "Demo Portfolio", "description": "E2E Test", "base_currency": "INR"})
        if res.status_code not in (200, 201):
            print(f"Failed to create portfolio: {res.text}")
            sys.exit(1)
        portfolio_id = res.json()["id"]
        print(f"Portfolio ID: {portfolio_id}")
        
        print("4. Adding holdings...")
        holdings = [
            {"ticker": "AAPL", "quantity": 10.0, "avg_buy_price": 150.0, "buy_currency": "USD"},
            {"ticker": "SPY", "quantity": 5.0, "avg_buy_price": 400.0, "buy_currency": "USD"},
            {"ticker": "RELIANCE.NS", "quantity": 15.0, "avg_buy_price": 2500.0, "buy_currency": "INR"},
            {"ticker": "TLT", "quantity": 10.0, "avg_buy_price": 90.0, "buy_currency": "USD"},
            {"ticker": "GLD", "quantity": 5.0, "avg_buy_price": 180.0, "buy_currency": "USD"},
            {"ticker": "bitcoin", "quantity": 0.5, "avg_buy_price": 30000.0, "buy_currency": "USD"},
        ]
        res = await client.post(f"/portfolios/{portfolio_id}/holdings/bulk", json=holdings)
        if res.status_code not in (200, 201):
            print(f"Failed to add holdings: {res.text}")
            sys.exit(1)
            
        print("5. Hitting Analytics...")
        res = await client.get(f"/analytics/{portfolio_id}")
        if res.status_code != 200:
            print(f"Analytics failed: {res.text}")
            sys.exit(1)
        print("Analytics OK.")
        
        print("6. Hitting Risk...")
        res = await client.get(f"/risk/{portfolio_id}/metrics")
        if res.status_code != 200:
            print(f"Risk metrics failed: {res.text}")
            sys.exit(1)
        res = await client.get(f"/risk/{portfolio_id}/monte-carlo?horizon_days=252&paths=100")
        if res.status_code != 200:
            print(f"Monte Carlo failed: {res.text}")
            sys.exit(1)
        print("Risk OK.")
        
        print("7. Hitting Optimize...")
        res = await client.post(f"/optimization/{portfolio_id}/run", json={"risk_tolerance": 0.5, "use_regime_scaling": True, "use_lstm_forecasts": False, "user_views": []})
        if res.status_code != 200:
            print(f"Optimization failed: {res.text}")
            sys.exit(1)
        print("Optimization OK.")
        
        print("8. Hitting Backtest...")
        res = await client.post(f"/backtest/", json={
            "assets": [
                {"ticker": "AAPL", "target_weight": 0.2},
                {"ticker": "SPY", "target_weight": 0.2},
                {"ticker": "RELIANCE.NS", "target_weight": 0.2},
                {"ticker": "TLT", "target_weight": 0.2},
                {"ticker": "GLD", "target_weight": 0.1},
                {"ticker": "bitcoin", "target_weight": 0.1}
            ],
            "initial_capital": 100000.0,
            "rebalance_frequency": "M"
        })
        if res.status_code != 200:
            print(f"Backtest failed: {res.text}")
            sys.exit(1)
        print("Backtest OK.")
        
        print("ALL TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(main())
