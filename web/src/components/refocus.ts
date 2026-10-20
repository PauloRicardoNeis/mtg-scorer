import { useEffect, type RefObject } from "react";

// The control a filter change came from. A navigation can remount the toolbar,
// which drops focus; module state outlives the remount, so the new toolbar can
// hand focus back.
let pending: { name: string; value: string } | null = null;

/** Note the control behind a change, before the change navigates. */
export function rememberFocus(target: EventTarget | null): void {
  if (!(
    target instanceof HTMLInputElement || target instanceof HTMLSelectElement
  ))
    return;
  pending = {
    name: target.name,
    value: target.type === "checkbox" ? target.value : "",
  };
}

/**
 * After each new address, focus the noted control again unless focus already sits
 * in the form, then forget it so a later visit does not steal focus.
 */
export function useRefocus(
  form: RefObject<HTMLFormElement | null>,
  address: string,
): void {
  useEffect(() => {
    const noted = pending;
    pending = null;
    const root = form.current;
    if (!noted || !root || root.contains(document.activeElement)) return;
    const selector = noted.value
      ? `[name="${noted.name}"][value="${noted.value}"]`
      : `[name="${noted.name}"]`;
    root.querySelector<HTMLElement>(selector)?.focus();
  }, [form, address]);
}
