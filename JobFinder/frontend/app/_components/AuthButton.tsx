"use client";

import { useEffect, useRef, useState } from "react";
import { useIsAuthenticated, useMsal } from "@azure/msal-react";
import { LogOut, UserRound } from "lucide-react";
import Link from "next/link";

import { loginRequest } from "@/lib/auth/msalConfig";

export default function AuthButton() {
  const { instance, accounts } = useMsal();
  const isAuthenticated         = useIsAuthenticated();
  const [open, setOpen]         = useState(false);
  const menuRef                 = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [open]);

  const account  = accounts[0];
  const initials = account?.name
    ?.split(" ")
    .map((n) => n[0])
    .slice(0, 2)
    .join("")
    .toUpperCase() ?? "?";

  if (!isAuthenticated) {
    return (
      <button
        type="button"
        onClick={() => void instance.loginRedirect(loginRequest)}
        className="rounded-full border border-white/25 px-4 py-1 text-xs text-white/65 transition-colors hover:border-white/40 hover:text-white/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30"
      >
        Se connecter
      </button>
    );
  }

  return (
    <div ref={menuRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-full border border-white/[0.18] bg-white/[0.05] py-1 pl-3 pr-1 text-xs text-white/70 transition-colors hover:border-white/30 hover:text-white/85 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30"
      >
        <span>{account?.name?.split(" ")[0] ?? "Mon compte"}</span>
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white/[0.12] text-[10px] font-semibold text-white/80">
          {initials}
        </span>
      </button>

      {open && (
        <div className="absolute right-0 top-9 z-50 w-44 rounded-xl border border-white/[0.12] bg-[#1a1a22] p-1.5 shadow-2xl">
          <Link
            href="/profile"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-white/70 transition-colors hover:bg-white/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30"
          >
            <UserRound className="h-3.5 w-3.5" />
            Mon profil
          </Link>
          <div className="mx-2 my-1 h-px bg-white/[0.08]" />
          <button
            type="button"
            onClick={() => void instance.logoutRedirect()}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-red-400/75 transition-colors hover:bg-white/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30"
          >
            <LogOut className="h-3.5 w-3.5" />
            Se déconnecter
          </button>
        </div>
      )}
    </div>
  );
}
