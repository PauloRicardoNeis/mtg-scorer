import { vi } from "vitest";

// Stand-ins for the App Router hooks, which need a mounted Next.js router.
// The setup file mocks next/navigation with these; tests import them to steer
// the pathname and inspect navigation.
type Navigate = (href: string, options?: { scroll?: boolean }) => void;

export const router = {
  push: vi.fn<Navigate>(),
  replace: vi.fn<Navigate>(),
  refresh: vi.fn<() => void>(),
  back: vi.fn<() => void>(),
  forward: vi.fn<() => void>(),
  prefetch: vi.fn<(href: string) => void>(),
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
