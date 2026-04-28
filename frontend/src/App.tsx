import { lazy, Suspense } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";

import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";

import Navbar from "./components/layout/Navbar.jsx";
import RequireAuth from "./components/layout/RequireAuth.jsx";
import OnboardingModal from "./components/onboarding/OnboardingModal.jsx";
import NotFound from "./pages/NotFound.tsx";

const Dashboard = lazy(() => import("./pages/Dashboard.jsx"));
const Optimize = lazy(() => import("./pages/Optimize.jsx"));
const Risk = lazy(() => import("./pages/Risk.jsx"));
const Analytics = lazy(() => import("./pages/Analytics.jsx"));
const Holdings = lazy(() => import("./pages/Holdings.jsx"));
const Login = lazy(() => import("./pages/Login.jsx"));
const Register = lazy(() => import("./pages/Register.jsx"));

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

function PublicPage({ children }) {
  return <Suspense fallback={<LoadingFallback />}>{children}</Suspense>;
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
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
            path="/"
            element={
              <RequireAuth>
                <ProtectedShell />
              </RequireAuth>
            }
          >
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="optimize" element={<Optimize />} />
            <Route path="risk" element={<Risk />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="holdings" element={<Holdings />} />
          </Route>

          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
