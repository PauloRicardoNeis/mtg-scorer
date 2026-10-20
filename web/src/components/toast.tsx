"use client";

import { useEffect, useEffectEvent, useState } from "react";
import { useI18n } from "#i18n";
import { IconButton } from "./primitives";

export type ToastMessage = {
  title: string;
  message?: string;
  tone?: "accent" | "success" | "warning" | "danger" | "neutral";
  action?: { label: string; onClick: () => void };
};

function ToastCard({
  toast,
  onDismiss,
}: {
  toast: ToastMessage;
  onDismiss: () => void;
}) {
  const { t } = useI18n();
  // Pointer or keyboard focus on the toast holds it open.
  const [held, setHeld] = useState(false);
  const dismiss = useEffectEvent(onDismiss);
  useEffect(() => {
    if (held) return;
    const timer = setTimeout(dismiss, 4000);
    return () => clearTimeout(timer);
  }, [toast, held]);
  return (
    <div
      className={`toast ${toast.tone ?? "accent"}`}
      onPointerEnter={() => setHeld(true)}
      onPointerLeave={() => setHeld(false)}
      onFocus={() => setHeld(true)}
      onBlur={() => setHeld(false)}
    >
      <span className="toast-dot" aria-hidden="true" />
      <div className="toast-body">
        <p className="toast-title">{toast.title}</p>
        {toast.message && <p className="toast-message">{toast.message}</p>}
      </div>
      {toast.action && (
        <button
          type="button"
          className="toast-action"
          onClick={toast.action.onClick}
        >
          {toast.action.label}
        </button>
      )}
      <IconButton
        icon="x"
        label={t.common.dismiss}
        size="sm"
        onClick={onDismiss}
      />
    </div>
  );
}

/**
 * A bottom-right status region showing one toast at a time. The region stays
 * mounted so screen readers announce each new toast; a toast closes after
 * about four seconds.
 */
export function Toasts({
  toast,
  onDismiss,
}: {
  toast: ToastMessage | null;
  onDismiss: () => void;
}) {
  return (
    <div className="toast-region" role="status">
      {toast && <ToastCard toast={toast} onDismiss={onDismiss} />}
    </div>
  );
}
