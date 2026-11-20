/**
 * Minimal pub-sub so a manual analysis request (deep in the CV detail tree)
 * can tell CreditsBadge (pinned in the root layout, no shared parent state
 * between the two) about credit balance changes without a shared parent state.
 *
 * "use client" modules run in the browser only, one instance per page load,
 * so a module-level EventTarget is safe here — same trade-off already used
 * for the logo badge cache in MatchItem.tsx.
 */
const bus = new EventTarget();
const CREDITS_CONSUMED_EVENT = "credits-consumed";
const CREDITS_RESERVED_EVENT = "credits-reserved";
const CREDITS_RELEASED_EVENT = "credits-released";

/** Analysis request succeeded — refetch the real balance from the server. */
export function notifyCreditsConsumed(): void {
  bus.dispatchEvent(new Event(CREDITS_CONSUMED_EVENT));
}

/** Analysis request just fired optimistically — decrement the badge by 1 right away, before the server responds. */
export function notifyCreditsReserved(): void {
  bus.dispatchEvent(new Event(CREDITS_RESERVED_EVENT));
}

/** Analysis request failed — undo the optimistic decrement (no credit was actually consumed). */
export function notifyCreditsReleased(): void {
  bus.dispatchEvent(new Event(CREDITS_RELEASED_EVENT));
}

export function onCreditsConsumed(handler: () => void): () => void {
  bus.addEventListener(CREDITS_CONSUMED_EVENT, handler);
  return () => bus.removeEventListener(CREDITS_CONSUMED_EVENT, handler);
}

export function onCreditsReserved(handler: () => void): () => void {
  bus.addEventListener(CREDITS_RESERVED_EVENT, handler);
  return () => bus.removeEventListener(CREDITS_RESERVED_EVENT, handler);
}

export function onCreditsReleased(handler: () => void): () => void {
  bus.addEventListener(CREDITS_RELEASED_EVENT, handler);
  return () => bus.removeEventListener(CREDITS_RELEASED_EVENT, handler);
}
