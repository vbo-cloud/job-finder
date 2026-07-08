/**
 * Minimal pub-sub so a manual analysis request (deep in the CV detail tree)
 * can tell CreditsBadge (pinned in the root layout, no shared parent state
 * between the two) to refetch the balance right after a credit is consumed.
 *
 * "use client" modules run in the browser only, one instance per page load,
 * so a module-level EventTarget is safe here — same trade-off already used
 * for the logo badge cache in MatchItem.tsx.
 */
const bus = new EventTarget();
const CREDITS_CONSUMED_EVENT = "credits-consumed";

export function notifyCreditsConsumed(): void {
  bus.dispatchEvent(new Event(CREDITS_CONSUMED_EVENT));
}

export function onCreditsConsumed(handler: () => void): () => void {
  bus.addEventListener(CREDITS_CONSUMED_EVENT, handler);
  return () => bus.removeEventListener(CREDITS_CONSUMED_EVENT, handler);
}
