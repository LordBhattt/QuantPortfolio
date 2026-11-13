"""
Integration smoke test for all new endpoints.
Uses cookie-based auth matching the actual app behaviour.
Run: python backend/scripts/endpoint_smoke_test.py
"""
import sys
import time
import json
from pathlib import Path

try:
    import httpx
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "httpx", "-q"], check=True)
    import httpx

BASE = "http://localhost:8000"
DEMO_EMAIL = "demo@quantportfolio.in"
DEMO_PASS  = "Demo@1234"
COOKIE_NAME = "qp_access_token"

results: dict[str, dict] = {}

def _call(client: httpx.Client, method: str, url: str, label: str, **kwargs) -> dict | list | None:
    t0 = time.time()
    try:
        r = client.request(method, url, timeout=90.0, **kwargs)
        elapsed = time.time() - t0
        status = r.status_code
        ok_str = "OK  " if status < 300 else "FAIL"
        body = None
        body_preview = ""
        try:
            body = r.json()
            if isinstance(body, dict):
                body_preview = str(list(body.keys()))[:70]
            elif isinstance(body, list):
                body_preview = f"list[{len(body)}]"
        except Exception:
            body_preview = r.text[:50]
        timing = "SLOW(>30s)!" if elapsed > 30 else ("SLOW(>10s)" if elapsed > 10 else "")
        line = f"  [{ok_str}] {label:<50}  {status}  {elapsed:5.1f}s  {timing}  {body_preview}"
        print(line)
        results[label] = {"status": status, "elapsed": round(elapsed, 1), "ok": status < 300}
        return body
    except Exception as exc:
        elapsed = time.time() - t0
        print(f"  [ERR ] {label:<50}  EXC   {elapsed:5.1f}s  {exc}")
        results[label] = {"status": 0, "elapsed": round(elapsed, 1), "ok": False, "error": str(exc)}
        return None


def main() -> dict | None:
    with httpx.Client(follow_redirects=True, cookies={}) as client:
        print(f"\n=== Auth: login as {DEMO_EMAIL} ===")
        r = client.post(
            f"{BASE}/api/v1/auth/token",
            data={"username": DEMO_EMAIL, "password": DEMO_PASS},
        )
        if r.status_code != 200:
            print(f"  LOGIN FAILED {r.status_code}: {r.text[:300]}")
            return None
        print(f"  Login OK ({r.elapsed.total_seconds():.1f}s), cookie set: {COOKIE_NAME in r.cookies}")
        # httpx carries the cookie automatically in subsequent requests

        # Get portfolio list
        body = _call(client, "GET", f"{BASE}/api/v1/portfolios/", "GET /portfolios/")
        portfolios = body if isinstance(body, list) else []
        if not portfolios:
            print("  No portfolios. Run seed_demo_portfolio.py first.")
            return None
        pid = str(portfolios[0].get("id", ""))
        pname = portfolios[0].get("name", "?")
        print(f"  Portfolio: {pname} (id={pid})")

        print("\n=== New Endpoints ===")

        # 1. Regime history
        regime = _call(client, "GET",
                       f"{BASE}/api/v1/risk/regime/history?days=60",
                       "GET /risk/regime/history?days=60")
        if isinstance(regime, list) and len(regime) > 0:
            r0 = regime[0]
            print(f"     Sample: {r0}")

        # 2. Stress test
        stress = _call(client, "GET",
                       f"{BASE}/api/v1/risk/{pid}/stress",
                       "GET /risk/{pid}/stress")
        if isinstance(stress, dict):
            scenarios = stress.get("historical_scenarios") or []
            print(f"     Scenarios returned: {[s.get('scenario_name') for s in scenarios]}")
            for sc in scenarios:
                ret_pct = sc.get('portfolio_return_pct', 0)
                impact = sc.get('portfolio_inr_impact', 0)
                print(f"     {sc.get('scenario_label')}: {ret_pct:.1f}% ({impact:,.0f} INR)")

        # 3. Custom stress
        custom = _call(client, "POST",
                       f"{BASE}/api/v1/risk/{pid}/stress/custom",
                       "POST /risk/{pid}/stress/custom",
                       json={"equities_pct": -20.0, "crypto_pct": -40.0,
                             "gold_pct": 10.0, "bonds_pct": -5.0, "inr_move_pct": -5.0})
        if isinstance(custom, dict):
            ret = custom.get("portfolio_return_pct")
            impact = custom.get("portfolio_inr_impact")
            # portfolio_return_pct is in percentage points (e.g. -12.5 means -12.5%)
            print(f"     Custom shock result: {ret:.1f}% ({impact:,.0f} INR)" if isinstance(ret, float) else f"     Keys: {list(custom.keys())}")

        # 4. Optimize with diagnostics
        opt = _call(client, "POST",
                    f"{BASE}/api/v1/optimize/",
                    "POST /optimize/ (diagnostics)",
                    json={"portfolio_id": pid, "risk_tolerance": 0.5,
                          "use_regime_scaling": True, "use_lstm_forecasts": False})
        diagnostics_ok = False
        if isinstance(opt, dict):
            diag = opt.get("diagnostics")
            print(f"     Regime: {opt.get('regime','?')}  Sharpe: {opt.get('sharpe_ratio','?'):.2f}")
            if diag:
                print(f"     Diagnostics: model_kind={diag.get('model_kind','?')}, per_asset={len(diag.get('per_asset',[]))}")
                diagnostics_ok = True
            else:
                print("     WARNING: diagnostics field is None - not being populated")

        # 5. Backtest (the main event - 2Y monthly to keep it under 30s)
        print("\n  [Backtest - first run, may take 15-30s...]")
        bt = _call(client, "POST",
                   f"{BASE}/api/v1/backtest/",
                   "POST /backtest/ (2Y monthly)",
                   json={"portfolio_id": pid, "lookback_years": 2, "rebalance": "monthly",
                         "risk_tolerance": 0.5, "cost_bps": 10,
                         "use_ml": False, "use_regime": True})

        backtest_data = {}
        if isinstance(bt, dict):
            headline = bt.get("headline", "")
            strats = bt.get("strategies", [])
            print(f"\n     Headline: {headline}")
            print(f"     {'Strategy':<22} {'Profit INR':>12}  {'CAGR':>7}  {'Sharpe':>7}  {'MaxDD':>7}  {'Sortino':>7}")
            print(f"     {'-'*22} {'-'*12}  {'-'*7}  {'-'*7}  {'-'*7}  {'-'*7}")
            for s in strats:
                name    = s.get("name", "?")
                profit  = s.get("total_profit_inr", 0)
                cagr    = s.get("cagr", 0)
                sharpe  = s.get("sharpe", 0)
                dd      = s.get("max_drawdown", 0)
                sortino = s.get("sortino", 0)
                print(f"     {name:<22} {profit:>12,.0f}  {cagr:>7.1%}  {sharpe:>7.2f}  {dd:>7.1%}  {sortino:>7.2f}")
                backtest_data[name] = s

        # 6. Second backtest run to verify caching
        print("\n  [Backtest - second run, should use cache < 2s...]")
        _call(client, "POST",
              f"{BASE}/api/v1/backtest/",
              "POST /backtest/ (cached run)",
              json={"portfolio_id": pid, "lookback_years": 2, "rebalance": "monthly",
                    "risk_tolerance": 0.5, "cost_bps": 10,
                    "use_ml": False, "use_regime": True})

        print("\n=== Summary ===")
        failures = [(k, v) for k, v in results.items() if not v["ok"]]
        slow     = [(k, v) for k, v in results.items() if v.get("elapsed", 0) > 30]
        print(f"  Total calls: {len(results)}")
        print(f"  Failures:    {len(failures)}")
        print(f"  Slow (>30s): {len(slow)}")
        if failures:
            print("  FAILED:")
            for k, v in failures:
                print(f"    {k}: status={v['status']}")
        if slow:
            print("  SLOW:")
            for k, v in slow:
                print(f"    {k}: {v['elapsed']}s")

        return backtest_data


if __name__ == "__main__":
    bt = main()
