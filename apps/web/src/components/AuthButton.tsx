import Link from "next/link";
import { auth, signOut } from "@/auth";

export async function AuthButton() {
  const session = await auth();

  if (!session?.user) {
    return (
      <Link
        href="/signin"
        className="text-sm px-3 py-1 rounded border border-blue-500 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950"
      >
        Sign in
      </Link>
    );
  }

  const label = session.user.name || session.user.email || "You";

  return (
    <form
      action={async () => {
        "use server";
        await signOut({ redirectTo: "/signin" });
      }}
      className="flex items-center gap-2"
    >
      <span className="text-xs text-slate-500 hidden sm:inline">
        {label}
      </span>
      <button
        type="submit"
        className="text-xs px-2 py-1 rounded border border-slate-300 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800"
      >
        Sign out
      </button>
    </form>
  );
}
