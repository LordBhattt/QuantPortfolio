import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { Navigate, useNavigate } from "react-router-dom";

import { addHoldingsBulk, getPortfolios } from "../api/portfolios";
import { getPortfolioRecommendation, submitInvestorProfile, type InvestorProfilePayload, type PortfolioRecommendation } from "../api/onboarding";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { usePortfolioStore } from "../store/portfolioStore";

type Step = 1 | 2 | 3 | 4 | 5;

const AGE_GROUPS: Array<{ value: InvestorProfilePayload["age_group"]; label: string; description: string }> = [
  { value: "18-25", label: "18-25", description: "Early career, long runway" },
  { value: "26-35", label: "26-35", description: "Income growth phase" },
  { value: "36-50", label: "36-50", description: "Family + wealth building" },
  { value: "50+", label: "50+", description: "Capital protection focus" },
];

const HORIZONS: Array<{ value: InvestorProfilePayload["investment_horizon"]; label: string; description: string }> = [
  { value: "short_term", label: "Short term", description: "Less than 1 year" },
  { value: "medium_term", label: "Medium term", description: "1-3 years" },
  { value: "long_term", label: "Long term", description: "More than 3 years" },
];

const INCOME_OPTIONS: Array<{ value: InvestorProfilePayload["income_stability"]; label: string; description: string }> = [
  { value: "stable", label: "Stable", description: "Predictable salary or cash flow" },
  { value: "variable", label: "Variable", description: "Commission, business, or irregular income" },
];

const RISK_OPTIONS: Array<{ value: InvestorProfilePayload["risk_appetite"]; label: string; description: string }> = [
  { value: "conservative", label: "Conservative", description: "Prioritize capital protection and lower drawdowns." },
  { value: "moderate", label: "Moderate", description: "Balance growth with manageable volatility." },
  { value: "aggressive", label: "Aggressive", description: "Accept higher volatility for stronger growth potential." },
];

const ONBOARDING_PORTFOLIO_NAME = "My Recommended Portfolio";

function formatAmount(value: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatWeight(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function formatPrice(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) {
    return "-";
  }
  return formatAmount(value);
}

function defaultQuantityForRecommendation(item: PortfolioRecommendation) {
  const unitPrice = item.current_price_inr;
  if (!unitPrice || !Number.isFinite(unitPrice) || unitPrice <= 0) {
    // Price unavailable — use a safe fractional quantity that approximates
    // the recommended INR amount assuming a high unit price (~₹1L).
    // This prevents the old bug where 0.01 × ₹91L BTC = ₹91K overshoot.
    const safeEstimatePrice = 100_000;
    const quantity = item.recommended_amount_inr / safeEstimatePrice;
    return Number(Math.max(quantity, 0.000001).toFixed(6));
  }
  const quantity = item.recommended_amount_inr / unitPrice;
  return Number(Math.max(quantity, 0.000001).toFixed(6));
}

function formatLabel(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function getErrorMessage(error: unknown, fallback: string) {
  if (error && typeof error === "object" && "response" in error) {
    const maybeAxios = error as { response?: { data?: { detail?: string } }; message?: string };
    return maybeAxios.response?.data?.detail || maybeAxios.message || fallback;
  }
  if (error instanceof Error) {
    return error.message || fallback;
  }
  return fallback;
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-xl border border-black/[0.06] bg-white px-4 py-3">
      <div>
        <div className="text-[10px] font-mono uppercase tracking-[0.16em] text-gray-400">{label}</div>
        <div className="mt-1 text-sm font-medium text-gray-900">{value}</div>
      </div>
    </div>
  );
}

export default function Onboarding() {
  const navigate = useNavigate();
  const onboarded = usePortfolioStore((state) => state.onboarded);
  const setPortfolio = usePortfolioStore((state) => state.setPortfolio);
  const completeOnboarding = usePortfolioStore((state) => state.completeOnboarding);

  const [step, setStep] = useState<Step>(1);
  const [submissionVersion, setSubmissionVersion] = useState(0);
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [portfolioId, setPortfolioId] = useState<string | null>(null);
  const [recommendations, setRecommendations] = useState<PortfolioRecommendation[]>([]);
  const [selectedAssets, setSelectedAssets] = useState<Record<string, boolean>>({});
  const [quantityDrafts, setQuantityDrafts] = useState<Record<string, string>>({});
  const [confirmOpen, setConfirmOpen] = useState(false);

  const [investmentAmount, setInvestmentAmount] = useState("100000");
  const [ageGroup, setAgeGroup] = useState<InvestorProfilePayload["age_group"] | "">("");
  const [riskAppetite, setRiskAppetite] = useState<InvestorProfilePayload["risk_appetite"] | "">("");
  const [investmentHorizon, setInvestmentHorizon] = useState<InvestorProfilePayload["investment_horizon"] | "">("");
  const [incomeStability, setIncomeStability] = useState<InvestorProfilePayload["income_stability"] | "">("");
  const [existingInvestments, setExistingInvestments] = useState(false);

  useEffect(() => {
    if (onboarded) {
      navigate("/dashboard", { replace: true });
    }
  }, [navigate, onboarded]);

  useEffect(() => {
    if (step !== 4) {
      return;
    }

    let active = true;

    const runOnboarding = async () => {
      setLoading(true);
      setError(null);

      try {
        const payload: InvestorProfilePayload = {
          investment_amount: Number(investmentAmount),
          investment_horizon: investmentHorizon as InvestorProfilePayload["investment_horizon"],
          risk_appetite: riskAppetite as InvestorProfilePayload["risk_appetite"],
          income_stability: incomeStability as InvestorProfilePayload["income_stability"],
          existing_investments: existingInvestments,
          age_group: ageGroup as InvestorProfilePayload["age_group"],
        };

        await submitInvestorProfile(payload);
        const allocation = await getPortfolioRecommendation();
        const portfolios = await getPortfolios();
        const recommendedPortfolio = portfolios.find((portfolio) => portfolio.name === ONBOARDING_PORTFOLIO_NAME) ?? portfolios[0] ?? null;

        if (!recommendedPortfolio) {
          throw new Error("Recommended portfolio was not created.");
        }

        if (!active) {
          return;
        }

        setPortfolio(recommendedPortfolio.id, recommendedPortfolio.name);
        setPortfolioId(recommendedPortfolio.id);
        setRecommendations(allocation);
        setSelectedAssets(Object.fromEntries(allocation.map((item) => [item.ticker, false])));
        setQuantityDrafts(Object.fromEntries(allocation.map((item) => [item.ticker, String(defaultQuantityForRecommendation(item))])));
        setStep(5);
      } catch (submissionError) {
        if (!active) {
          return;
        }

        setError(getErrorMessage(submissionError, "Unable to build a recommendation right now."));
        setStep(3);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    void runOnboarding();

    return () => {
      active = false;
    };
  }, [ageGroup, existingInvestments, incomeStability, investmentAmount, investmentHorizon, riskAppetite, step, submissionVersion]);

  const progress = useMemo(() => Math.min(100, (step / 5) * 100), [step]);
  const selectedRows = useMemo(
    () => recommendations.filter((item) => selectedAssets[item.ticker]),
    [recommendations, selectedAssets],
  );

  const totalSelectedAmount = selectedRows.reduce((sum, item) => sum + item.recommended_amount_inr, 0);
  const canContinueStep1 = Number(investmentAmount) > 0 && ageGroup !== "";
  const canContinueStep2 = riskAppetite !== "" && investmentHorizon !== "";
  const canContinueStep3 = incomeStability !== "";

  const advanceToStep4 = () => {
    if (!canContinueStep1 || !canContinueStep2 || !canContinueStep3) {
      return;
    }

    setError(null);
    setStep(4);
    setSubmissionVersion((current) => current + 1);
  };

  const openConfirmDialog = () => {
    if (selectedRows.length === 0) {
      setError("Select at least one asset before confirming investments.");
      return;
    }

    setError(null);
    setQuantityDrafts((current) => {
      const next: Record<string, string> = {};
      for (const row of selectedRows) {
        next[row.ticker] = current[row.ticker] || "1";
      }
      return next;
    });
    setConfirmOpen(true);
  };

  const confirmInvestments = async () => {
    if (!portfolioId) {
      setError("Recommended portfolio is unavailable.");
      return;
    }

    setConfirming(true);
    setError(null);
    let savedSuccessfully = false;

    try {
      const holdingsPayload = selectedRows.map((row) => {
        const quantity = Number(quantityDrafts[row.ticker]);
        if (!Number.isFinite(quantity) || quantity <= 0) {
          throw new Error(`Enter a valid quantity for ${row.ticker}.`);
        }

        const buyPrice = row.current_price_inr && Number.isFinite(row.current_price_inr) && row.current_price_inr > 0
          ? row.current_price_inr
          : row.recommended_amount_inr / quantity;

        return {
          ticker: row.ticker,
          quantity,
          avg_buy_price: buyPrice,
          buy_currency: "INR",
        };
      });

      await addHoldingsBulk(portfolioId, holdingsPayload);

      completeOnboarding();
      navigate("/dashboard", { replace: true });
      savedSuccessfully = true;
    } catch (confirmationError) {
      setError(getErrorMessage(confirmationError, "Unable to save your confirmed investments."));
    } finally {
      setConfirming(false);
      if (savedSuccessfully) {
        setConfirmOpen(false);
      }
    }
  };

  if (onboarded) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div
      className="min-h-screen bg-slate-50 text-gray-900"
      style={{
        backgroundImage:
          "radial-gradient(circle at top left, rgba(15, 23, 42, 0.08), transparent 36%), radial-gradient(circle at top right, rgba(180, 83, 9, 0.08), transparent 28%), linear-gradient(180deg, rgba(255,255,255,0.92), rgba(248,250,252,1))",
      }}
    >
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-8 md:px-6 md:py-12">
        <div className="max-w-3xl space-y-3">
          <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-gray-500">Investor profiling</p>
          <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">Build your recommended portfolio in a few steps.</h1>
          <p className="max-w-2xl text-sm text-gray-600 md:text-base">
            Tell us about your capital, risk appetite, and timeline. We&apos;ll generate a portfolio and let you confirm the assets you actually buy.
          </p>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between text-[11px] font-mono uppercase tracking-[0.18em] text-gray-500">
            <span>Step {step} of 5</span>
            <span>{Math.round(progress)}%</span>
          </div>
          <Progress value={progress} className="h-2.5" />
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(300px,0.9fr)]">
          <Card className="border-black/[0.06] shadow-sm">
            <CardHeader className="space-y-1 border-b border-black/[0.06] bg-white/60">
              <CardTitle className="text-lg md:text-xl">
                {step === 1 && "Step 1: Tell us your starting point"}
                {step === 2 && "Step 2: Choose your risk posture"}
                {step === 3 && "Step 3: Add income context"}
                {step === 4 && "Step 4: Generating your portfolio"}
                {step === 5 && "Step 5: Review and confirm"}
              </CardTitle>
              <CardDescription>
                {step === 1 && "Investment amount and age help us calibrate the allocation baseline."}
                {step === 2 && "Risk appetite and horizon determine the overall mix across bonds, stocks, gold, and crypto."}
                {step === 3 && "Income stability helps us fine-tune the score before recommendations are built."}
                {step === 4 && "We are saving your profile and fetching the recommended allocation now."}
                {step === 5 && "Check the assets you actually bought, then we will create the holdings for you."}
              </CardDescription>
            </CardHeader>

            <CardContent className="p-6 md:p-8">
              {step === 1 && (
                <div className="space-y-8">
                  <div className="space-y-3">
                    <Label htmlFor="investment_amount" className="text-[11px] font-mono uppercase tracking-[0.16em] text-gray-500">
                      Investment amount (INR)
                    </Label>
                    <Input
                      id="investment_amount"
                      type="number"
                      min="1"
                      step="1000"
                      value={investmentAmount}
                      onChange={(event) => setInvestmentAmount(event.target.value)}
                      className="max-w-sm"
                    />
                  </div>

                  <div className="space-y-3">
                    <div className="text-[11px] font-mono uppercase tracking-[0.16em] text-gray-500">Age group</div>
                    <RadioGroup value={ageGroup} onValueChange={(value) => setAgeGroup(value as InvestorProfilePayload["age_group"])} className="grid gap-3 md:grid-cols-2">
                      {AGE_GROUPS.map((option) => (
                        <Label
                          key={option.value}
                          className={`flex cursor-pointer items-start gap-3 rounded-2xl border p-4 transition-colors ${
                            ageGroup === option.value ? "border-gray-900 bg-gray-900/5" : "border-black/[0.08] bg-white hover:border-black/[0.16]"
                          }`}
                        >
                          <RadioGroupItem value={option.value} className="mt-1" />
                          <span className="space-y-0.5">
                            <span className="block text-sm font-semibold text-gray-900">{option.label}</span>
                            <span className="block text-xs text-gray-500">{option.description}</span>
                          </span>
                        </Label>
                      ))}
                    </RadioGroup>
                  </div>

                  <div className="flex justify-end">
                    <Button onClick={() => setStep(2)} disabled={!canContinueStep1}>
                      Continue
                    </Button>
                  </div>
                </div>
              )}

              {step === 2 && (
                <div className="space-y-8">
                  <div className="grid gap-3 md:grid-cols-3">
                    {RISK_OPTIONS.map((option) => {
                      const selected = riskAppetite === option.value;

                      return (
                        <button key={option.value} type="button" onClick={() => setRiskAppetite(option.value)} className="text-left">
                          <Card className={`h-full transition-all ${selected ? "border-gray-900 shadow-md shadow-black/5" : "border-black/[0.08] hover:border-black/[0.16]"}`}>
                            <CardContent className="space-y-2 p-5">
                              <div className="flex items-center justify-between gap-3">
                                <h3 className="text-base font-semibold text-gray-900">{option.label}</h3>
                                <span className={`text-[10px] font-mono uppercase tracking-[0.14em] ${selected ? "text-gray-900" : "text-gray-400"}`}>
                                  {selected ? "Selected" : "Choose"}
                                </span>
                              </div>
                              <p className="text-sm leading-6 text-gray-600">{option.description}</p>
                            </CardContent>
                          </Card>
                        </button>
                      );
                    })}
                  </div>

                  <div className="space-y-3">
                    <div className="text-[11px] font-mono uppercase tracking-[0.16em] text-gray-500">Investment horizon</div>
                    <RadioGroup
                      value={investmentHorizon}
                      onValueChange={(value) => setInvestmentHorizon(value as InvestorProfilePayload["investment_horizon"])}
                      className="grid gap-3 md:grid-cols-3"
                    >
                      {HORIZONS.map((option) => (
                        <Label
                          key={option.value}
                          className={`flex cursor-pointer flex-col gap-1 rounded-2xl border p-4 transition-colors ${
                            investmentHorizon === option.value ? "border-gray-900 bg-gray-900/5" : "border-black/[0.08] bg-white hover:border-black/[0.16]"
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <RadioGroupItem value={option.value} />
                            <span className="text-sm font-semibold text-gray-900">{option.label}</span>
                          </div>
                          <span className="ml-7 text-xs text-gray-500">{option.description}</span>
                        </Label>
                      ))}
                    </RadioGroup>
                  </div>

                  <div className="flex items-center justify-between gap-3">
                    <Button variant="outline" onClick={() => setStep(1)}>
                      Back
                    </Button>
                    <Button onClick={() => setStep(3)} disabled={!canContinueStep2}>
                      Continue
                    </Button>
                  </div>
                </div>
              )}

              {step === 3 && (
                <div className="space-y-8">
                  <div className="space-y-3">
                    <div className="text-[11px] font-mono uppercase tracking-[0.16em] text-gray-500">Income stability</div>
                    <RadioGroup
                      value={incomeStability}
                      onValueChange={(value) => setIncomeStability(value as InvestorProfilePayload["income_stability"])}
                      className="grid gap-3 md:grid-cols-2"
                    >
                      {INCOME_OPTIONS.map((option) => (
                        <Label
                          key={option.value}
                          className={`flex cursor-pointer flex-col gap-1 rounded-2xl border p-4 transition-colors ${
                            incomeStability === option.value ? "border-gray-900 bg-gray-900/5" : "border-black/[0.08] bg-white hover:border-black/[0.16]"
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <RadioGroupItem value={option.value} />
                            <span className="text-sm font-semibold text-gray-900">{option.label}</span>
                          </div>
                          <span className="ml-7 text-xs text-gray-500">{option.description}</span>
                        </Label>
                      ))}
                    </RadioGroup>
                  </div>

                  <div className="flex items-center justify-between rounded-2xl border border-black/[0.08] bg-white px-4 py-4">
                    <div>
                      <div className="text-sm font-semibold text-gray-900">Existing investments</div>
                      <div className="text-xs text-gray-500">Do you already have investments elsewhere?</div>
                    </div>
                    <Switch checked={existingInvestments} onCheckedChange={(checked) => setExistingInvestments(checked)} />
                  </div>

                  {error && <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}

                  <div className="flex items-center justify-between gap-3">
                    <Button variant="outline" onClick={() => setStep(2)}>
                      Back
                    </Button>
                    <Button onClick={advanceToStep4} disabled={!canContinueStep3}>
                      Build recommendation
                    </Button>
                  </div>
                </div>
              )}

              {step === 4 && (
                <div className="flex min-h-[320px] flex-col items-center justify-center gap-4 text-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-full border border-black/[0.08] bg-white shadow-sm">
                    <Loader2 className="h-7 w-7 animate-spin text-gray-900" />
                  </div>
                  <div className="space-y-1">
                    <p className="text-base font-semibold text-gray-900">Creating your profile and portfolio mix</p>
                    <p className="text-sm text-gray-500">We are saving your investor profile and building a tailored allocation now.</p>
                  </div>
                  {error && <p className="max-w-xl rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
                </div>
              )}

              {step === 5 && (
                <div className="space-y-6">
                  <div className="rounded-2xl border border-black/[0.08] bg-gray-50 px-4 py-4">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <p className="text-sm font-semibold text-gray-900">Recommended portfolio ready</p>
                        <p className="text-xs text-gray-500">Select the assets you actually invested in and confirm the quantities.</p>
                      </div>
                      <div className="text-xs font-mono uppercase tracking-[0.14em] text-gray-500">
                        {selectedRows.length} selected · {formatAmount(totalSelectedAmount)}
                      </div>
                    </div>
                  </div>

                  <div className="overflow-hidden rounded-2xl border border-black/[0.08] bg-white">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-[220px]">Asset</TableHead>
                          <TableHead>Class</TableHead>
                          <TableHead>Suggested Weight %</TableHead>
                          <TableHead>Suggested Amount (INR)</TableHead>
                          <TableHead>Current Price (INR)</TableHead>
                          <TableHead className="text-right">I actually invested in this</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {recommendations.map((row) => (
                          <TableRow key={row.ticker}>
                            <TableCell className="font-medium text-gray-900">{row.ticker}</TableCell>
                            <TableCell>{formatLabel(row.asset_class)}</TableCell>
                            <TableCell>{formatWeight(row.recommended_weight)}</TableCell>
                            <TableCell>{formatAmount(row.recommended_amount_inr)}</TableCell>
                            <TableCell>{formatPrice(row.current_price_inr)}</TableCell>
                            <TableCell className="text-right">
                              <Checkbox
                                checked={Boolean(selectedAssets[row.ticker])}
                                onCheckedChange={(checked) =>
                                  setSelectedAssets((current) => ({
                                    ...current,
                                    [row.ticker]: Boolean(checked),
                                  }))
                                }
                              />
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>

                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <Button variant="outline" onClick={() => setStep(3)}>
                      Back
                    </Button>
                    <Button onClick={openConfirmDialog} disabled={selectedRows.length === 0}>
                      Confirm My Investments
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <div className="space-y-6">
            <Card className="border-black/[0.06] shadow-sm">
              <CardHeader>
                <CardTitle className="text-base">Profile summary</CardTitle>
                <CardDescription>These inputs drive the recommendation and eventual holdings.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 pt-0">
                <SummaryItem label="Investment amount" value={investmentAmount ? formatAmount(Number(investmentAmount)) : "-"} />
                <SummaryItem label="Age group" value={ageGroup || "Not selected"} />
                <SummaryItem label="Risk appetite" value={riskAppetite ? formatLabel(riskAppetite) : "Not selected"} />
                <SummaryItem label="Horizon" value={investmentHorizon ? formatLabel(investmentHorizon) : "Not selected"} />
                <SummaryItem label="Income stability" value={incomeStability ? formatLabel(incomeStability) : "Not selected"} />
                <SummaryItem label="Existing investments" value={existingInvestments ? "Yes" : "No"} />
              </CardContent>
            </Card>

            <Card className="border-black/[0.06] shadow-sm">
              <CardHeader>
                <CardTitle className="text-base">Flow notes</CardTitle>
                <CardDescription>What happens after you continue.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 pt-0 text-sm text-gray-600">
                <p>1. We save your investor profile.</p>
                <p>2. The backend returns a recommended allocation.</p>
                <p>3. We create a starter portfolio if needed.</p>
                <p>4. You confirm what you actually bought.</p>
                <p>5. We post holdings for the confirmed assets only.</p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Confirm quantities</DialogTitle>
            <DialogDescription>
              Enter the quantity for each asset you checked. We will use the suggested allocation as the notional amount.
            </DialogDescription>
          </DialogHeader>

          <div className="max-h-[55vh] space-y-4 overflow-y-auto pr-1">
            {selectedRows.map((row) => (
              <div key={row.ticker} className="grid gap-2 rounded-xl border border-black/[0.08] bg-gray-50 p-4 md:grid-cols-[1fr_180px] md:items-center">
                <div>
                  <div className="text-sm font-semibold text-gray-900">{row.ticker}</div>
                  <div className="text-xs text-gray-500">
                    {formatLabel(row.asset_class)} · Suggested {formatAmount(row.recommended_amount_inr)} · Price {formatPrice(row.current_price_inr)}
                  </div>
                </div>
                <div className="space-y-1">
                  <Label className="text-[11px] font-mono uppercase tracking-[0.14em] text-gray-500">Quantity</Label>
                  <Input
                    type="number"
                    min="0"
                    step="any"
                    value={quantityDrafts[row.ticker] || ""}
                    onChange={(event) =>
                      setQuantityDrafts((current) => ({
                        ...current,
                        [row.ticker]: event.target.value,
                      }))
                    }
                  />
                </div>
              </div>
            ))}
          </div>

          <div className="rounded-xl border border-black/[0.08] bg-gray-50 px-4 py-3 flex items-center justify-between">
            <div className="text-xs font-mono uppercase tracking-[0.14em] text-gray-500">Estimated total investment</div>
            <div className="text-sm font-semibold text-gray-900">
              {formatAmount(
                selectedRows.reduce((sum, row) => {
                  const qty = Number(quantityDrafts[row.ticker]) || 0;
                  const price = row.current_price_inr && Number.isFinite(row.current_price_inr) && row.current_price_inr > 0
                    ? row.current_price_inr
                    : row.recommended_amount_inr / Math.max(qty, 0.000001);
                  return sum + qty * price;
                }, 0)
              )}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)} disabled={confirming}>
              Cancel
            </Button>
            <Button onClick={confirmInvestments} disabled={confirming || selectedRows.length === 0}>
              {confirming ? "Saving..." : "Confirm and create holdings"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}