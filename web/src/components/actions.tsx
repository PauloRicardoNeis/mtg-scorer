"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "./icon";
import { Toasts, type ToastMessage } from "./toast";

export function CopySearch() {
  const [toast, setToast] = useState<ToastMessage | null>(null);
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
              title: "Search URL copied.",
              message: "It stays pinned to this dataset.",
            });
          } catch {
            setToast({
              tone: "warning",
              title: "Couldn't copy the URL.",
              message: "Copy it from your browser address bar.",
            });
          }
        }}
      >
        <Icon name="copy" size={14} />
        Copy this search URL
      </button>
      <Toasts toast={toast} onDismiss={() => setToast(null)} />
    </span>
  );
}

export function Retry() {
  const router = useRouter();
  return (
    <button type="button" onClick={() => router.refresh()}>
      <Icon name="rotate-cw" size={14} />
      Retry
    </button>
  );
}
