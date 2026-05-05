import { create } from "zustand";

const readOnboarded = () => {
  try {
    return localStorage.getItem("qp_onboarded") === "true";
  } catch {
    return false;
  }
};

export const usePortfolioStore = create((set) => ({
  portfolioId: null,
  portfolioName: null,
  regime: null,
  onboarded: typeof window !== "undefined" ? readOnboarded() : false,
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
      localStorage.removeItem("qp_onboarded");
    } catch {}
    set({
      portfolioId: null,
      portfolioName: null,
      regime: null,
      onboarded: false,
    });
  },
}));
