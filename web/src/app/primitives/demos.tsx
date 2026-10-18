"use client";

import { useState } from "react";
import { Toasts, type ToastMessage } from "@/components/toast";

const samples: Record<string, ToastMessage> = {
  success: {
    tone: "success",
    title: "Search URL copied.",
    message: "It stays pinned to this dataset.",
  },
  warning: {
    tone: "warning",
    title: "Couldn't copy the URL.",
    message: "Copy it from your browser address bar.",
  },
};

export function ToastDemo() {
  const [toast, setToast] = useState<ToastMessage | null>(null);
  return (
    <div className="gallery-row">
      <button
        type="button"
        className="secondary sm"
        onClick={() => setToast(samples.success)}
      >
        Show success toast
      </button>
      <button
        type="button"
        className="secondary sm"
        onClick={() => setToast(samples.warning)}
      >
        Show warning toast
      </button>
      <button
        type="button"
        className="secondary sm"
        onClick={() =>
          setToast({
            title: "Filters cleared.",
            message: "Showing every card in this dataset.",
            action: { label: "Undo", onClick: () => setToast(null) },
          })
        }
      >
        Show toast with action
      </button>
      <Toasts toast={toast} onDismiss={() => setToast(null)} />
    </div>
  );
}
