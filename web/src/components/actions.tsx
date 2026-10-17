"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "./icon";

export function CopySearch() {
  const [status, setStatus] = useState("");
  return (
    <span className="copy-action">
      <button
        type="button"
        className="secondary"
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(location.href);
            setStatus("Search URL copied.");
          } catch {
            setStatus("Copy the URL from your browser address bar.");
          }
        }}
      >
        <Icon name="copy" size={14} />
        Copy this search URL
      </button>
      <span role="status">{status}</span>
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
