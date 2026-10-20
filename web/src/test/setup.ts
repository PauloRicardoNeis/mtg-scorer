import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { navigation } from "./navigation";

vi.mock("next/navigation", async () => {
  const { navigation } = await import("./navigation");
  return {
    useRouter: navigation.useRouter,
    usePathname: navigation.usePathname,
    useSearchParams: navigation.useSearchParams,
  };
});

afterEach(() => {
  cleanup();
  navigation.resetPathname();
  // Node-environment suites (server-only modules) have no window.
  if (typeof window !== "undefined") window.history.replaceState(null, "", "/");
});
