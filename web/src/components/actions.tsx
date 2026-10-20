"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useI18n } from "#i18n";
import { Icon } from "./icon";
import { Toasts, type ToastMessage } from "./toast";

export function CopySearch() {
  const [toast, setToast] = useState<ToastMessage | null>(null);
  const { t } = useI18n();
  return (
    <span className="copy-action">
      <button
        type="button"
        className="secondary"
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(location.href);
            setToast({
              tone: "success",
              title: t.copy.copied,
              message: t.copy.pinned,
            });
          } catch {
            setToast({
              tone: "warning",
              title: t.copy.failed,
              message: t.copy.manual,
            });
          }
        }}
      >
        <Icon name="copy" size={14} />
        {t.copy.button}
      </button>
      <Toasts toast={toast} onDismiss={() => setToast(null)} />
    </span>
  );
}

export function Retry() {
  const router = useRouter();
  const { t } = useI18n();
  return (
    <button type="button" onClick={() => router.refresh()}>
      <Icon name="rotate-cw" size={14} />
      {t.common.retry}
    </button>
  );
}
