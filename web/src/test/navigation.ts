import { vi } from "vitest";

// Stand-ins for the App Router hooks, which need a mounted Next.js router.
// The setup file mocks next/navigation with these; tests import them to steer
// the pathname and inspect navigation.
export const router = {
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
  back: vi.fn(),
  forward: vi.fn(),
  prefetch: vi.fn(),
};

let pathname = "/";

export function setPathname(value: string): void {
  pathname = value;
}

export const navigation = {
  useRouter: () => router,
  usePathname: () => pathname,
  // The query of jsdom's current location, which tests set with history.pushState.
  useSearchParams: () => new URLSearchParams(location.search),
  resetPathname: () => setPathname("/"),
};
