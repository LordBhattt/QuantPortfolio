import { create } from "zustand";

const onboardingKey = (userId) => `qp_onboarded:${userId}`;

const readOnboarded = (userId) => {
  if (!userId) return false;
  try {
    return localStorage.getItem(onboardingKey(userId)) === "true";
  } catch {
    return false;
  }
};

export const usePortfolioStore = create((set) => ({
  userId: null,
  portfolioId: null,
  portfolioName: null,
  regime: null,
  onboarded: false,
  setAuthenticatedUser: (userId) =>
    set({
      userId,
      portfolioId: null,
      portfolioName: null,
      regime: null,
      onboarded: typeof window !== "undefined" ? readOnboarded(userId) : false,
    }),
  setPortfolio: (id, name) => set({ portfolioId: id, portfolioName: name }),
  setRegime: (regime) => set({ regime }),
  completeOnboarding: () => {
    const userId = usePortfolioStore.getState().userId;
    try {
      if (userId) localStorage.setItem(onboardingKey(userId), "true");
    } catch {}
    set({ onboarded: true });
  },
  logout: () => {
    try {
      const userId = usePortfolioStore.getState().userId;
      if (userId) localStorage.removeItem(onboardingKey(userId));
    } catch {}
    set({
      userId: null,
      portfolioId: null,
      portfolioName: null,
      regime: null,
      onboarded: false,
    });
  },
}));
