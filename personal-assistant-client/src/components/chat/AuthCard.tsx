import { useAuthCardStore } from "@/stores/auth-card-store";
import { ShieldCheckIcon, XIcon, CheckCircleIcon } from "lucide-react";
import type { FC } from "react";

export interface AuthCardProps {
  messageId?: string;
}

export const AuthCard: FC<AuthCardProps> = ({ messageId }) => {
  const storeMessageId = useAuthCardStore((s) => s.messageId);
  const authUrl = useAuthCardStore((s) => s.authUrl);
  const message = useAuthCardStore((s) => s.message);
  const authComplete = useAuthCardStore((s) => s.authComplete);
  const clearAuth = useAuthCardStore((s) => s.clearAuth);

  if (!authUrl) return null;
  // If messageId is provided, we are rendering inside a specific message bubble.
  // Only render if the store's messageId matches this component's prop.
  if (messageId && messageId !== storeMessageId) return null;

  const isComplete = authComplete;

  return (
    <div className="mb-4 mt-4 w-full">
      <div
        className={
          isComplete
            ? "flex items-start gap-3 rounded-xl border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-950"
            : "flex items-start gap-3 rounded-xl border border-blue-200 bg-blue-50 p-4 dark:border-blue-800 dark:bg-blue-950"
        }
      >
        {isComplete ? (
          <CheckCircleIcon className="mt-0.5 size-5 shrink-0 text-green-600 dark:text-green-400" />
        ) : (
          <ShieldCheckIcon className="mt-0.5 size-5 shrink-0 text-blue-600 dark:text-blue-400" />
        )}
        <p
          className={
            isComplete
              ? "flex-1 text-sm leading-relaxed text-green-800 dark:text-green-200"
              : "flex-1 text-sm leading-relaxed text-blue-800 dark:text-blue-200"
          }
        >
          {message}
        </p>
        <div className="flex shrink-0 items-center gap-2">
          {isComplete ? (
            <span className="inline-flex h-8 items-center rounded-md bg-green-600 px-3 text-sm font-medium text-white">
              授权完成
            </span>
          ) : (
            <a
              href={authUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-8 items-center rounded-md bg-blue-600 px-3 text-sm font-medium text-white transition-colors hover:bg-blue-700"
            >
              点击授权
            </a>
          )}
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
