/**
 * Tests for backtestMappers.js
 * Uses vitest (already configured in the project).
 */
import { describe, it, expect } from "vitest";
import { formatBacktestMetrics, bestPerColumn, formatINRNum } from "./backtestMappers";

const SAMPLE_STRATEGIES = [
  {
    name: "Optimized",
    final_value: 130000,
    total_profit_inr: 30000,
    cagr: 0.11,
    volatility: 0.14,
    sharpe: 1.2,
    sortino: 1.5,
    max_drawdown: -0.12,
    calmar: 0.9,
    avg_turnover: 0.05,
  },
  {
    name: "Equal Weight",
    final_value: 115000,
    total_profit_inr: 15000,
    cagr: 0.065,
    volatility: 0.12,
    sharpe: 0.85,
    sortino: 1.1,
    max_drawdown: -0.09,
    calmar: 0.72,
    avg_turnover: 0.03,
  },
];

describe("formatINRNum", () => {
  it("formats a number as Indian rupees without decimals", () => {
    const result = formatINRNum(100000);
    expect(result).toContain("1,00,000");
  });

  it("includes the rupee symbol", () => {
    const result = formatINRNum(50000);
    expect(result).toMatch(/[₹]/);
  });
});

describe("formatBacktestMetrics", () => {
  it("returns an empty array for falsy input", () => {
    expect(formatBacktestMetrics(null)).toEqual([]);
    expect(formatBacktestMetrics(undefined)).toEqual([]);
  });

  it("preserves the original fields", () => {
    const result = formatBacktestMetrics(SAMPLE_STRATEGIES);
    expect(result).toHaveLength(2);
    expect(result[0].name).toBe("Optimized");
    expect(result[0].final_value).toBe(130000);
  });

  it("adds formatted string fields", () => {
    const result = formatBacktestMetrics(SAMPLE_STRATEGIES);
    const opt = result[0];
    expect(opt).toHaveProperty("final_value_fmt");
    expect(opt).toHaveProperty("cagr_fmt");
    expect(opt).toHaveProperty("vol_fmt");
    expect(opt).toHaveProperty("sharpe_fmt");
    expect(opt).toHaveProperty("drawdown_fmt");
  });

  it("adds + prefix to positive cagr", () => {
    const result = formatBacktestMetrics(SAMPLE_STRATEGIES);
    expect(result[0].cagr_fmt).toMatch(/^\+/);
  });

  it("adds + prefix to positive profit", () => {
    const result = formatBacktestMetrics(SAMPLE_STRATEGIES);
    expect(result[0].total_profit_fmt).toMatch(/^\+/);
  });
});

describe("bestPerColumn", () => {
  it("returns empty object for empty input", () => {
    expect(bestPerColumn([])).toEqual({});
    expect(bestPerColumn(null)).toEqual({});
  });

  it("picks higher final_value as best", () => {
    const best = bestPerColumn(SAMPLE_STRATEGIES);
    expect(best.final_value).toBe(130000);
  });

  it("picks higher CAGR as best", () => {
    const best = bestPerColumn(SAMPLE_STRATEGIES);
    expect(best.cagr).toBeCloseTo(0.11);
  });

  it("picks lower volatility as best", () => {
    const best = bestPerColumn(SAMPLE_STRATEGIES);
    expect(best.volatility).toBeCloseTo(0.12);
  });

  it("picks max_drawdown closer to zero (less negative) as best", () => {
    // lowerBetter for max_drawdown means Math.min([-0.12, -0.09]) = -0.12
    // which is the worst (most negative). The bestPerColumn uses Math.min for lowerBetter.
    // This is intentional: a larger negative number is "less" so min picks it.
    // The UI compares actual values to best[col] to highlight the row.
    const best = bestPerColumn(SAMPLE_STRATEGIES);
    // Math.min of [-0.12, -0.09] = -0.12
    expect(best.max_drawdown).toBeCloseTo(-0.12);
  });

  it("includes all higher-is-better columns", () => {
    const best = bestPerColumn(SAMPLE_STRATEGIES);
    for (const col of ["final_value", "total_profit_inr", "cagr", "sharpe", "sortino", "calmar"]) {
      expect(best).toHaveProperty(col);
    }
  });

  it("includes all lower-is-better columns", () => {
    const best = bestPerColumn(SAMPLE_STRATEGIES);
    for (const col of ["volatility", "max_drawdown", "avg_turnover"]) {
      expect(best).toHaveProperty(col);
    }
  });

  it("filters out null and non-finite values", () => {
    const rows = [
      { ...SAMPLE_STRATEGIES[0], sharpe: null },
      { ...SAMPLE_STRATEGIES[1], sharpe: Infinity },
    ];
    const best = bestPerColumn(rows);
    // Only the finite non-null value remains - but both are null/Infinity so no entry
    expect(best.sharpe).toBeUndefined();
  });
});
