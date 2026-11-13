import { beforeEach, describe, expect, it } from "vitest";

import { usePortfolioStore } from "./portfolioStore";

describe("portfolio session state", () => {
  beforeEach(() => {
    localStorage.clear();
    usePortfolioStore.setState({
      userId: null,
      portfolioId: null,
      portfolioName: null,
      regime: null,
      onboarded: false,
    });
  });

  it("keeps onboarding completion scoped to the authenticated user", () => {
    usePortfolioStore.getState().setAuthenticatedUser("user-a");
    usePortfolioStore.getState().completeOnboarding();
    expect(usePortfolioStore.getState().onboarded).toBe(true);

    usePortfolioStore.getState().setAuthenticatedUser("user-b");
    expect(usePortfolioStore.getState().onboarded).toBe(false);
    expect(usePortfolioStore.getState().portfolioId).toBeNull();

    usePortfolioStore.getState().setAuthenticatedUser("user-a");
    expect(usePortfolioStore.getState().onboarded).toBe(true);
  });
});
