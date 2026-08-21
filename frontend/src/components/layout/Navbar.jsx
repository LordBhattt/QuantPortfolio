import { useEffect, useMemo, useRef, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCheck, ChevronDown, ExternalLink, Loader2, Sparkles } from "lucide-react";

import { markAlertRead, markAllAlertsRead } from "../../api/alerts";
import { logout as logoutApi } from "../../api/auth";
import { useCurrentUser } from "../../hooks/useAuth";
import { useAlerts } from "../../hooks/useAlerts";
import { usePortfolios } from "../../hooks/usePortfolio";
import { usePortfolioStore } from "../../store/portfolioStore";
import Badge from "../ui-qp/Badge";

const links = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/optimize", label: "Optimize" },
  { to: "/risk", label: "Risk" },
  { to: "/analytics", label: "Analytics" },
  { to: "/backtest", label: "Backtest" },
  { to: "/holdings", label: "Holdings" },
];

function getInitials(user) {
  const source = user?.full_name?.trim() || user?.email?.trim() || "QuantPortfolio";
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return parts
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

export default function Navbar() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const regime = usePortfolioStore((s) => s.regime);
  const portfolioId = usePortfolioStore((s) => s.portfolioId);
  const portfolioName = usePortfolioStore((s) => s.portfolioName);
  const setPortfolio = usePortfolioStore((s) => s.setPortfolio);
  const logout = usePortfolioStore((s) => s.logout);

  const { data: portfolios = [], loading: portfoliosLoading } = usePortfolios();
  const { data: currentUser } = useCurrentUser();
  const { data: alerts = [], loading: alertsLoading, refetch: refetchAlerts } = useAlerts();

  const [portfolioOpen, setPortfolioOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [alertsOpen, setAlertsOpen] = useState(false);
  const [locallyReadIds, setLocallyReadIds] = useState(new Set());
  const portfolioRef = useRef(null);
  const accountRef = useRef(null);
  const alertsRef = useRef(null);

  const initials = useMemo(() => getInitials(currentUser), [currentUser]);
  const activePortfolioName = portfolioName || (portfoliosLoading ? "Loading..." : "Select Portfolio");
  const unreadCount = alerts.filter((alert) => !locallyReadIds.has(alert.id)).length;
  const visibleAlerts = alerts.slice(0, 5);

  useEffect(() => {
    const onDown = (event) => {
      if (portfolioRef.current && !portfolioRef.current.contains(event.target)) setPortfolioOpen(false);
      if (accountRef.current && !accountRef.current.contains(event.target)) setAccountOpen(false);
      if (alertsRef.current && !alertsRef.current.contains(event.target)) setAlertsOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  const handleViewPortfolio = (portfolioId, portfolioName) => {
    setPortfolio(portfolioId, portfolioName);
    setAlertsOpen(false);
    navigate("/dashboard");
  };

  const handleOptimizeNow = async (portfolioId, portfolioName, alertId) => {
    setPortfolio(portfolioId, portfolioName);
    setLocallyReadIds((current) => new Set([...current, alertId]));
    await markAlertRead(alertId);
    await refetchAlerts();
    setAlertsOpen(false);
    navigate("/optimize");
  };

  const handleMarkAllRead = async () => {
    await markAllAlertsRead();
    setLocallyReadIds(new Set());
    await refetchAlerts();
  };

  const handleLogout = async () => {
    try {
      await logoutApi();
    } finally {
      await queryClient.removeQueries({ queryKey: ["current-user"] });
      logout();
      setAccountOpen(false);
      setPortfolioOpen(false);
      navigate("/login");
    }
  };

  return (
    <nav className="sticky top-0 z-40 h-14 bg-white/80 backdrop-blur-xl backdrop-saturate-150 border-b border-black/[0.06] shadow-[0_1px_0_0_rgba(0,0,0,0.02)] flex items-center px-6 gap-6">
      <div className="flex items-center gap-2">
        <div className="w-7 h-7 rounded-md bg-gray-900 flex items-center justify-center">
          <span className="text-white font-mono text-xs font-semibold">Q</span>
        </div>
        <span className="font-sans font-semibold text-sm tracking-tight text-gray-900">QuantPortfolio</span>
      </div>

      <div ref={portfolioRef} className="relative">
        <button
          onClick={() => setPortfolioOpen((value) => !value)}
          className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-black/[0.08] bg-white hover:bg-black/[0.03] transition-colors"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-primary" />
          <span className="font-sans text-xs font-medium text-gray-900">{activePortfolioName}</span>
          <ChevronDown className="text-gray-400" />
        </button>
        {portfolioOpen && (
          <div className="absolute left-0 top-11 w-56 bg-white border border-black/[0.08] rounded-xl shadow-card-hover z-50 py-1.5 animate-fadeUp">
            {portfoliosLoading && <div className="px-4 py-2 text-sm font-sans text-gray-500">Loading portfolios...</div>}
            {!portfoliosLoading &&
              portfolios.map((portfolio) => (
                <button
                  key={portfolio.id}
                  onClick={() => {
                    setPortfolio(portfolio.id, portfolio.name);
                    setPortfolioOpen(false);
                  }}
                  className={`w-full text-left px-4 py-2 text-sm font-sans hover:bg-black/[0.04] transition-colors flex items-center justify-between ${
                    portfolio.id === portfolioId ? "text-gray-900 font-medium" : "text-gray-600"
                  }`}
                >
                  <span className="truncate">{portfolio.name}</span>
                  {portfolio.id === portfolioId && <span className="text-[10px] font-mono text-primary">ACTIVE</span>}
                </button>
              ))}
            {!portfoliosLoading && portfolios.length === 0 && (
              <div className="px-4 py-2 text-sm font-sans text-gray-500">Create your first portfolio to get started.</div>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center gap-1">
        {links.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `px-3 py-1.5 text-sm font-sans font-medium rounded-lg transition-colors duration-150 ${
                isActive ? "text-gray-900 bg-black/[0.04]" : "text-gray-500 hover:text-gray-900 hover:bg-black/[0.03]"
              }`
            }
          >
            {label}
          </NavLink>
        ))}
      </div>

      <div className="ml-auto flex items-center gap-4">
        {regime && <Badge regime={regime} />}

        <div ref={alertsRef} className="relative">
          <button
            onClick={() => setAlertsOpen((value) => !value)}
            className="relative flex h-9 w-9 items-center justify-center rounded-full border border-black/[0.08] bg-white text-gray-700 hover:bg-black/[0.03] transition-colors"
            aria-label="Notifications"
          >
            <Bell className="h-4 w-4" />
            {unreadCount > 0 && (
              <span className="absolute -right-1 -top-1 inline-flex min-w-5 items-center justify-center rounded-full bg-red-600 px-1.5 py-0.5 text-[10px] font-semibold leading-none text-white">
                {unreadCount > 9 ? "9+" : unreadCount}
              </span>
            )}
          </button>

          {alertsOpen && (
            <div className="absolute right-0 top-11 z-50 w-[360px] overflow-hidden rounded-2xl border border-black/[0.08] bg-white shadow-card-hover animate-fadeUp">
              <div className="flex items-center justify-between border-b border-black/[0.06] px-4 py-3">
                <div>
                  <div className="text-sm font-semibold text-gray-900">Alerts</div>
                  <div className="text-[11px] font-mono text-gray-500">Unread portfolio drift and drawdown notices</div>
                </div>
                <button
                  onClick={handleMarkAllRead}
                  className="inline-flex items-center gap-1 rounded-full border border-black/[0.08] px-2.5 py-1 text-[11px] font-medium text-gray-600 hover:bg-black/[0.03]"
                >
                  <CheckCheck className="h-3.5 w-3.5" />
                  Mark all read
                </button>
              </div>

              <div className="max-h-[420px] overflow-y-auto p-2">
                {alertsLoading && <div className="px-4 py-6 text-sm text-gray-500">Loading alerts...</div>}
                {!alertsLoading && visibleAlerts.length === 0 && (
                  <div className="flex flex-col items-center gap-2 px-4 py-8 text-center text-gray-500">
                    <Sparkles className="h-5 w-5 text-gray-300" />
                    <div className="text-sm font-medium text-gray-700">No unread alerts</div>
                    <div className="text-xs text-gray-500">Your portfolios are currently within range.</div>
                  </div>
                )}

                {visibleAlerts.map((alert) => {
                  const isRead = locallyReadIds.has(alert.id) || Boolean(alert.is_read);
                  const portfolio = alert.portfolio;
                  const createdAt = alert.created_at ? new Date(alert.created_at) : null;

                  return (
                    <div
                      key={alert.id}
                      className={`mb-2 rounded-xl border p-3 transition-colors ${
                        isRead ? "border-black/[0.06] bg-gray-50 opacity-75" : "border-red-200 bg-red-50/70"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-[11px] font-mono uppercase tracking-[0.14em] text-gray-400">{portfolio?.name || "Portfolio"}</div>
                          <p className="mt-1 text-sm font-medium text-gray-900">{alert.message}</p>
                          <div className="mt-2 text-[11px] font-mono text-gray-500">
                            {createdAt ? createdAt.toLocaleString("en-IN") : "Just now"}
                          </div>
                        </div>
                        <div className={`mt-0.5 h-2 w-2 rounded-full ${isRead ? "bg-gray-300" : "bg-red-500"}`} />
                      </div>

                      <div className="mt-3 flex flex-wrap gap-2">
                        <button
                          onClick={() => handleViewPortfolio(alert.portfolio_id, portfolio?.name || "Portfolio")}
                          className="inline-flex items-center gap-1 rounded-full border border-black/[0.08] px-3 py-1.5 text-[11px] font-medium text-gray-700 hover:bg-black/[0.03]"
                        >
                          <ExternalLink className="h-3.5 w-3.5" />
                          View Portfolio
                        </button>
                        <button
                          onClick={() => handleOptimizeNow(alert.portfolio_id, portfolio?.name || "Portfolio", alert.id)}
                          className="inline-flex items-center gap-1 rounded-full bg-gray-900 px-3 py-1.5 text-[11px] font-medium text-white hover:bg-gray-800"
                        >
                          <Loader2 className="h-3.5 w-3.5" />
                          Optimize Now
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        <div ref={accountRef} className="relative">
          <button
            onClick={() => setAccountOpen((value) => !value)}
            className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-primary-dark flex items-center justify-center hover:opacity-90 transition-opacity"
          >
            <span className="text-primary-foreground font-mono text-xs font-semibold">{initials}</span>
          </button>
          {accountOpen && (
            <div className="absolute right-0 top-12 w-56 bg-white border border-black/[0.08] rounded-xl shadow-card-hover z-50 py-2 animate-fadeUp">
              <div className="px-4 py-2 flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-primary-dark flex items-center justify-center">
                  <span className="text-white font-mono text-xs font-semibold">{initials}</span>
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-sans font-semibold text-gray-900 truncate">
                    {currentUser?.full_name || "QuantPortfolio User"}
                  </div>
                  <div className="text-xs font-mono text-gray-400 truncate">{currentUser?.email || "Loading..."}</div>
                </div>
              </div>
              <div className="border-t border-black/[0.06] my-1" />
              <button className="w-full text-left px-4 py-2 text-sm font-sans text-gray-700 hover:bg-black/[0.04] transition-colors">
                Profile
              </button>
              <button className="w-full text-left px-4 py-2 text-sm font-sans text-gray-700 hover:bg-black/[0.04] transition-colors">
                Settings
              </button>
              <div className="border-t border-black/[0.06] my-1" />
              <button
                onClick={handleLogout}
                className="w-full text-left px-4 py-2 text-sm font-sans font-medium text-gray-900 hover:bg-black/[0.04] transition-colors"
              >
                Sign Out
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}
