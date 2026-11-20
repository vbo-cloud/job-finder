"use client";

import { useState } from "react";

import apiClient from "@/lib/api/client";
import type { CreditsRefillResponse } from "@/lib/api/types";
import { notifyCreditsConsumed } from "@/lib/creditsBus";

interface Props {
  /** Called with the new balance returned by the backend after a refill. */
  onRefilled: (newBalance: number) => void;
}

/**
 * Admin-only escape hatch while there is no purchase flow: adds 10 analysis
 * credits to the admin's own account. Rendered only when GET /profile says
 * is_admin — the backend enforces the restriction anyway (403 otherwise).
 */
export default function AdminRefillButton({ onRefilled }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  async function handleRefill() {
    setBusy(true);
    setError(false);
    try {
      const res = await apiClient.post<CreditsRefillResponse>("/profile/credits/refill");
      onRefilled(res.data.analysis_credits_remaining);
      // Despite the name, this tells CreditsBadge to refetch the balance —
      // same bus as a consumption, the badge only needs "balance changed".
      notifyCreditsConsumed();
    } catch (err) {
      console.error("[profile] credits refill failed:", err);
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="flex items-center gap-2">
      {error && <span className="text-[11px] text-destructive">Erreur, réessayez</span>}
      <button
        type="button"
        onClick={() => void handleRefill()}
        disabled={busy}
        title="Fonction admin — recharge 10 crédits d'analyse"
        className="rounded-full border border-soft px-3 py-1.5 text-xs font-semibold text-body transition-colors hover:border-default hover:text-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50"
      >
        {busy ? "Recharge…" : "+10 crédits"}
      </button>
    </span>
  );
}
