import { useEffect, useMemo, useRef, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";

import { useCurrentUser } from "../../hooks/useAuth";
import { usePortfolios } from "../../hooks/usePortfolio";
import { usePortfolioStore } from "../../store/portfolioStore";
import Badge from "../ui-qp/Badge";

const links = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/optimize", label: "Optimize" },
  { to: "/risk", label: "Risk" },
  { to: "/analytics", label: "Analytics" },
  { to: "/holdings", label: "Holdings" },
];

function ChevronDown({ className = "" }) {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={className}>
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

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
  const regime = usePortfolioStore((s) => s.regime);
  const portfolioId = usePortfolioStore((s) => s.portfolioId);
  const portfolioName = usePortfolioStore((s) => s.portfolioName);
  const setPortfolio = usePortfolioStore((s) => s.setPortfolio);
  const logout = usePortfolioStore((s) => s.logout);

  const { data: portfolios = [], loading: portfoliosLoading } = usePortfolios();
  const { data: currentUser } = useCurrentUser();

  const [portfolioOpen, setPortfolioOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const portfolioRef = useRef(null);
  const accountRef = useRef(null);

  const initials = useMemo(() => getInitials(currentUser), [currentUser]);
  const activePortfolioName = portfolioName || (portfoliosLoading ? "Loading..." : "Select Portfolio");

  useEffect(() => {
    const onDown = (event) => {
      if (portfolioRef.current && !portfolioRef.current.contains(event.target)) setPortfolioOpen(false);
      if (accountRef.current && !accountRef.current.contains(event.target)) setAccountOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  const handleLogout = () => {
    logout();
    setAccountOpen(false);
    setPortfolioOpen(false);
    navigate("/login");
  };

  return (
    <nav className="sticky top-0 z-40 h-14 bg-white/90 backdrop-blur-sm border-b border-black/[0.06] flex items-center px-6 gap-6">
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
