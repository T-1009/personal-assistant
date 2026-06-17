import { useAuthCardStore } from "@/stores/auth-card-store";
import { ShieldCheckIcon, XIcon } from "lucide-react";
import type { FC } from "react";

export const AuthCard: FC = () => {
  const authUrl = useAuthCardStore((s) => s.authUrl);
  const message = useAuthCardStore((s) => s.message);
  const clearAuth = useAuthCardStore((s) => s.clearAuth);

  if (!authUrl) return null;

  return (
    <div className="mx-auto w-full max-w-(--thread-max-width) px-4 pt-2">
      <div className="flex items-start gap-3 rounded-xl border border-blue-200 bg-blue-50 p-4 dark:border-blue-800 dark:bg-blue-950">
        <ShieldCheckIcon className="mt-0.5 size-5 shrink-0 text-blue-600 dark:text-blue-400" />
        <p className="flex-1 text-sm leading-relaxed text-blue-800 dark:text-blue-200">
          {message}
        </p>
        <div className="flex shrink-0 items-center gap-2">
          <a
            href={authUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex h-8 items-center rounded-md bg-blue-600 px-3 text-sm font-medium text-white transition-colors hover:bg-blue-700"
          >
            点击授权
          </a>
          <button
            type="button"
            onClick={clearAuth}
            className="inline-flex size-8 items-center justify-center rounded-md text-blue-500 transition-colors hover:bg-blue-100 dark:hover:bg-blue-900"
            aria-label="关闭"
          >
            <XIcon className="size-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
