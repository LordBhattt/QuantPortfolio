import { lazy, Suspense, useEffect } from "react";
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";

import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";

import Navbar from "./components/layout/Navbar.jsx";
import RequireAuth from "./components/layout/RequireAuth.jsx";
import OnboardingModal from "./components/onboarding/OnboardingModal.jsx";
import NotFound from "./pages/NotFound.tsx";
import { usePortfolioStore } from "./store/portfolioStore";
import { useCurrentUser } from "./hooks/useAuth";
import { usePortfolios } from "./hooks/usePortfolio";

const Backtest = lazy(() => import("./pages/Backtest.jsx"));
const Dashboard = lazy(() => import("./pages/Dashboard.jsx"));
const Optimize = lazy(() => import("./pages/Optimize.jsx"));
const Risk = lazy(() => import("./pages/Risk.jsx"));
const Analytics = lazy(() => import("./pages/Analytics.jsx"));
const Holdings = lazy(() => import("./pages/Holdings.jsx"));
const Profile = lazy(() => import("./pages/Profile.jsx"));
const Settings = lazy(() => import("./pages/Settings.jsx"));
const Login = lazy(() => import("./pages/Login.jsx"));
const Register = lazy(() => import("./pages/Register.jsx"));
const Onboarding = lazy(() => import("./pages/Onboarding.tsx"));

const queryClient = new QueryClient();

const LoadingFallback = () => (
  <div className="max-w-[1400px] mx-auto px-6 py-8 space-y-4">
    <div className="h-40 w-full bg-gray-50 rounded-xl animate-pulse" />
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="h-28 bg-gray-50 rounded-xl animate-pulse" />
      <div className="h-28 bg-gray-50 rounded-xl animate-pulse" />
      <div className="h-28 bg-gray-50 rounded-xl animate-pulse" />
    </div>
  </div>
);

function ProtectedShell() {
  return (
    <>
      <Navbar />
      <OnboardingModal />
      <Suspense fallback={<LoadingFallback />}>
        <Outlet />
      </Suspense>
    </>
  );
}

function SessionSync() {
  const { data: currentUser } = useCurrentUser();
  const setAuthenticatedUser = usePortfolioStore((state) => state.setAuthenticatedUser);

  useEffect(() => {
    if (currentUser?.id) setAuthenticatedUser(currentUser.id);
  }, [currentUser?.id, setAuthenticatedUser]);

  return null;
}

function PublicPage({ children }) {
  return <Suspense fallback={<LoadingFallback />}>{children}</Suspense>;
}

function RequireOnboarding({ children }: { children: ReactNode }) {
  const { loading: authLoading } = useCurrentUser();
  const { data: portfolios = [], loading: portfoliosLoading, error } = usePortfolios();

  if (authLoading || portfoliosLoading) return <LoadingFallback />;
  if (error) return <div className="p-6 text-sm text-red-700">Unable to load your portfolios. Please try again.</div>;
  if (portfolios.length === 0) {
    return <Navigate to="/onboarding" replace />;
  }
  return children;
}

function HomeRedirect() {
  const { data: portfolios = [], loading } = usePortfolios();
  if (loading) return <LoadingFallback />;
  return <Navigate to={portfolios.length > 0 ? "/dashboard" : "/onboarding"} replace />;
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <SessionSync />
        <Routes>
          <Route
            path="/login"
            element={
              <PublicPage>
                <Login />
              </PublicPage>
            }
          />
          <Route
            path="/register"
            element={
              <PublicPage>
                <Register />
              </PublicPage>
            }
          />
          <Route
            path="/onboarding"
            element={
              <RequireAuth>
                <PublicPage>
                  <Onboarding />
                </PublicPage>
              </RequireAuth>
            }
          />

          <Route
            path="/"
            element={
              <RequireAuth>
                <RequireOnboarding>
                  <ProtectedShell />
                </RequireOnboarding>
              </RequireAuth>
            }
          >
            <Route index element={<HomeRedirect />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="backtest" element={<Backtest />} />
            <Route path="optimize" element={<Optimize />} />
            <Route path="risk" element={<Risk />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="holdings" element={<Holdings />} />
            <Route path="profile" element={<Profile />} />
            <Route path="settings" element={<Settings />} />
          </Route>

          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
