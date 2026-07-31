import { redirect } from "next/navigation";
import { auth, signIn } from "@/auth";

export default async function SignInPage({
  searchParams
}: {
  searchParams: Promise<{ callbackUrl?: string }>;
}) {
  const params = await searchParams;
  const callbackUrl = params?.callbackUrl || "/";
  const session = await auth();
  if (session?.user) {
    redirect(callbackUrl);
  }

  const demoEnabled =
    (process.env.DEMO_MODE || "").toLowerCase() === "true";
  const githubEnabled = Boolean(
    process.env.AUTH_GITHUB_ID && process.env.AUTH_GITHUB_SECRET
  );

  return (
    <div className="max-w-md mx-auto py-8">
      <h1 className="text-xl font-semibold tracking-tight mb-4">Sign in</h1>
      <p className="text-sm text-slate-500 mb-6">
        DEMO-TRADE — research + trading-signal platform. Sign in with a
        supported provider to view your watchlists, portfolios, and
        research chats. Not investment advice.
      </p>

      <div className="grid gap-3">
        {githubEnabled && (
          <form
            action={async () => {
              "use server";
              await signIn("github", { redirectTo: callbackUrl });
            }}
          >
            <button
              type="submit"
              className="w-full text-sm px-4 py-2 rounded border border-slate-300 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800"
            >
              Continue with GitHub
            </button>
          </form>
        )}

        {demoEnabled && (
          <form
            action={async () => {
              "use server";
              await signIn("demo", { redirectTo: callbackUrl });
            }}
          >
            <button
              type="submit"
              className="w-full text-sm px-4 py-2 rounded border border-blue-500 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950"
            >
              Continue as demo user
            </button>
            <p className="text-[10px] text-slate-500 mt-1">
              Demo login is only available when the API is running with
              DEMO_MODE=true.
            </p>
          </form>
        )}

        {!githubEnabled && !demoEnabled && (
          <p className="text-sm text-amber-600 dark:text-amber-400">
            No auth providers are configured. Set{" "}
            <code className="mono">AUTH_GITHUB_ID</code> +{" "}
            <code className="mono">AUTH_GITHUB_SECRET</code> for GitHub OAuth,
            or set <code className="mono">DEMO_MODE=true</code> for demo login.
          </p>
        )}
      </div>
    </div>
  );
}
