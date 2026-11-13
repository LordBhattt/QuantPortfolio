import PageWrapper from "../components/layout/PageWrapper";
import Card from "../components/ui-qp/Card";
import { useCurrentUser } from "../hooks/useAuth";

function getInitials(user) {
  const source = user?.full_name?.trim() || user?.email?.trim() || "QuantPortfolio";
  return source
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

export default function Profile() {
  const { data: currentUser, loading } = useCurrentUser();

  return (
    <PageWrapper title="Profile" subtitle="Your QuantPortfolio account">
      <Card className="max-w-2xl p-6">
        <div className="flex items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary-dark">
            <span className="font-mono text-lg font-semibold text-primary-foreground">
              {getInitials(currentUser)}
            </span>
          </div>
          <div className="min-w-0">
            <h2 className="truncate text-lg font-semibold text-gray-900">
              {loading ? "Loading profile..." : currentUser?.full_name || "QuantPortfolio User"}
            </h2>
            <p className="truncate text-sm font-mono text-gray-500">
              {loading ? "Loading..." : currentUser?.email || "No email available"}
            </p>
          </div>
        </div>

        <div className="mt-6 grid gap-4 border-t border-black/[0.06] pt-5 sm:grid-cols-2">
          <div>
            <p className="text-[11px] font-mono uppercase tracking-wider text-gray-400">Account status</p>
            <p className="mt-1 text-sm font-medium text-gray-900">{currentUser?.is_active === false ? "Inactive" : "Active"}</p>
          </div>
          <div>
            <p className="text-[11px] font-mono uppercase tracking-wider text-gray-400">Account ID</p>
            <p className="mt-1 truncate text-sm font-mono text-gray-700">{currentUser?.id || "Unavailable"}</p>
          </div>
        </div>
      </Card>
    </PageWrapper>
  );
}
