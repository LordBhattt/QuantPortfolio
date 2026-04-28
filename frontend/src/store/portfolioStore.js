import { create } from "zustand";

const readOnboarded = () => {
  try {
    return localStorage.getItem("qp_onboarded") === "true";
  } catch {
    return false;
  }
};

const readToken = () => {
  try {
    return localStorage.getItem("qp_token");
  } catch {
    return null;
  }
};

export const usePortfolioStore = create((set) => ({
  token: typeof window !== "undefined" ? readToken() : null,
  portfolioId: null,
  portfolioName: null,
  regime: null,
  onboarded: typeof window !== "undefined" ? readOnboarded() : false,

  setToken: (token) => {
    try {
      if (token) localStorage.setItem("qp_token", token);
      else localStorage.removeItem("qp_token");
    } catch {}
    set({ token });
  },
  setPortfolio: (id, name) => set({ portfolioId: id, portfolioName: name }),
  setRegime: (regime) => set({ regime }),
  completeOnboarding: () => {
    try {
      localStorage.setItem("qp_onboarded", "true");
    } catch {}
    set({ onboarded: true });
  },
  logout: () => {
    try {
      localStorage.removeItem("qp_token");
      localStorage.removeItem("qp_onboarded");
    } catch {}
    set({
      token: null,
      portfolioId: null,
      portfolioName: null,
      regime: null,
      onboarded: false,
    });
  },
}));
