/**
 * Hash routing.
 *
 * The active view used to be React state only: no deep link, no browser back,
 * and F5 dropped you back into the cockpit. A hash keeps the URL honest
 * without pulling in a router or requiring server-side rewrites.
 *
 * With several branches the URL carries both: `#/mitarbeiter/rs` is the staff
 * list of Remscheid. The view comes first so a branch key can never be
 * mistaken for a view name, and a link sent to a colleague opens the branch
 * that was meant - not whichever one their own switcher last stood on.
 */

import React from "react";

export type Route = { view: string; branch: string | null };

function parse(fallback: string): Route {
  const raw = window.location.hash.replace(/^#\/?/, "").split("?")[0];
  const [view, branch] = raw.split("/");
  return { view: view || fallback, branch: branch ? decodeURIComponent(branch) : null };
}

function serialise(route: Route): string {
  return route.branch ? `/${route.view}/${encodeURIComponent(route.branch)}` : `/${route.view}`;
}

export function useHashRoute(fallback: string): [Route, (next: Partial<Route>) => void] {
  const [route, setRoute] = React.useState<Route>(() => parse(fallback));

  React.useEffect(() => {
    const onChange = () => setRoute(parse(fallback));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, [fallback]);

  const navigate = React.useCallback((next: Partial<Route>) => {
    const current = parse("");
    const target: Route = {
      view: next.view ?? current.view,
      branch: next.branch === undefined ? current.branch : next.branch,
    };
    const hash = serialise(target);
    // Assigning the hash pushes a history entry, so browser back works.
    if (serialise(current) !== hash) window.location.hash = hash;
  }, []);

  return [route, navigate];
}
