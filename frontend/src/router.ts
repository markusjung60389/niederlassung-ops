/**
 * Hash routing.
 *
 * The active view used to be React state only: no deep link, no browser back,
 * and F5 dropped you back into the cockpit. A hash keeps the URL honest
 * without pulling in a router or requiring server-side rewrites.
 */

import React from "react";

export function currentRoute(fallback: string): string {
  const raw = window.location.hash.replace(/^#\/?/, "").split("?")[0];
  return raw || fallback;
}

export function useHashRoute(fallback: string): [string, (next: string) => void] {
  const [route, setRoute] = React.useState(() => currentRoute(fallback));

  React.useEffect(() => {
    const onChange = () => setRoute(currentRoute(fallback));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, [fallback]);

  const navigate = React.useCallback((next: string) => {
    // Assigning the hash pushes a history entry, so browser back works.
    if (currentRoute("") !== next) window.location.hash = `/${next}`;
  }, []);

  return [route, navigate];
}
