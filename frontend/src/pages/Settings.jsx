import { useNavigate } from "react-router-dom";

import PageWrapper from "../components/layout/PageWrapper";
import Card from "../components/ui-qp/Card";

export default function Settings() {
  const navigate = useNavigate();

  return (
    <PageWrapper title="Settings" subtitle="Portfolio preferences and application guidance">
      <div className="grid max-w-3xl gap-4">
        <Card className="p-6">
          <h2 className="text-[15px] font-semibold text-gray-900">Optimization preferences</h2>
          <p className="mt-1 text-sm text-gray-500">
            Review your allocation constraints and risk tolerance on the Optimize page before running a new allocation.
          </p>
          <button
            type="button"
            onClick={() => navigate("/optimize")}
            className="mt-4 rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-800"
          >
            Open Optimize
          </button>
        </Card>

        <Card className="p-6">
          <h2 className="text-[15px] font-semibold text-gray-900">Notifications</h2>
          <p className="mt-1 text-sm text-gray-500">
            Portfolio drift and drawdown alerts are available from the notification bell in the navigation bar.
          </p>
          <button
            type="button"
            onClick={() => navigate("/risk")}
            className="mt-4 rounded-lg border border-black/[0.1] px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-black/[0.04]"
          >
            Review Risk
          </button>
        </Card>
      </div>
    </PageWrapper>
  );
}
