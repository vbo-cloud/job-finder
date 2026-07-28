"use client";

import { useEffect, useRef, useState } from "react";
import { useIsAuthenticated, useMsal } from "@azure/msal-react";
import { LogOut, MessageSquareWarning, Moon, Sun, UserRound } from "lucide-react";
import Link from "next/link";

import { loginRequest } from "@/lib/auth/msalConfig";
import { useTheme } from "@/lib/theme/useTheme";

export default function AuthButton() {
  const { instance, accounts } = useMsal();
  const isAuthenticated         = useIsAuthenticated();
  const [open, setOpen]         = useState(false);
  const menuRef                 = useRef<HTMLDivElement>(null);
  const { themeId, toggle }     = useTheme();

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

  const account  = instance.getActiveAccount() ?? accounts[0];
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
        className="flex h-8 items-center rounded-full border border-default px-4 text-xs text-body transition-colors hover:border-hover hover:text-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
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
        className="flex h-8 items-center gap-2 rounded-full border border-soft bg-card pl-3 pr-1 text-xs text-primary transition-colors hover:border-default hover:text-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
      >
        <span>{account?.name?.split(" ")[0] ?? "Mon compte"}</span>
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-badge text-[10px] font-semibold text-strong">
          {initials}
        </span>
      </button>

      {open && (
        <div className="absolute right-0 top-9 z-50 w-44 rounded-xl border border-soft bg-surface p-1.5 shadow-2xl">
          <Link
            href="/profile"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-primary transition-colors hover:bg-overlay focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
          >
            <UserRound className="h-3.5 w-3.5" />
            Mon profil
          </Link>

          <button
            type="button"
            onClick={toggle}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-primary transition-colors hover:bg-overlay focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
          >
            {themeId === "dark" ? (
              <Sun className="h-3.5 w-3.5" />
            ) : (
              <Moon className="h-3.5 w-3.5" />
            )}
            {themeId === "dark" ? "Thème clair" : "Thème sombre"}
          </button>

          <Link
            href="/feedback"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-primary transition-colors hover:bg-overlay focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
          >
            <MessageSquareWarning className="h-3.5 w-3.5" aria-hidden="true" />
            Donner un avis / Signaler un bug
          </Link>

          <div className="mx-2 my-1 h-px bg-card-hover" />

          <button
            type="button"
            onClick={() => void instance.logoutRedirect()}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-destructive transition-colors hover:bg-overlay focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-default"
          >
            <LogOut className="h-3.5 w-3.5" />
            Se déconnecter
          </button>
        </div>
      )}
    </div>
  );
}
