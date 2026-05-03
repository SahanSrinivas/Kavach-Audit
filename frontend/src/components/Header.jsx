import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { useAuth } from "../lib/auth";

/**
 * Kavachly branded header.
 * - Wordmark "Kavachly" (Outfit, 700, navy) + thin divider + tagline "Insurance, audited." (Inter, 500, muted)
 * - Tagline + divider hidden on widths <480px (only wordmark shows)
 * - Sticky top, white surface, 1px border-bottom
 * - Right side is auth-aware: avatar circle (first letter of mobile) → /dashboard/settings when logged in;
 *   nothing when logged out.
 * - Logo click → "/" if logged out, "/dashboard" if logged in.
 *
 * Do NOT use on Stage 0 ("/"). The landing hero is friction-zero by design.
 */
export default function Header() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();

  const homeHref = user ? "/dashboard" : "/";
  const initial = user?.mobile ? user.mobile.charAt(0) : "";
  // Render the avatar slot only once auth state has resolved — prevents flicker
  // (especially on Stage 0 where most visitors will be logged out).
  const showAvatar = !loading && !!user;

  return (
    <header
      data-testid="kavachly-header"
      className="sticky top-0 z-50 bg-white border-b border-[#E1E5EB]"
    >
      <div className="h-14 flex items-center justify-between px-4 sm:px-6 max-w-6xl mx-auto">
        {/* Left — wordmark + tagline */}
        <Link
          to={homeHref}
          data-testid="header-brand"
          className="flex items-baseline gap-3 group"
        >
          <span className="inline-flex items-center gap-1.5">
            <ShieldCheck
              className="w-4 h-4 text-[#13A8A8] translate-y-[1px]"
              strokeWidth={2.5}
              aria-hidden="true"
            />
            <span
              data-testid="header-wordmark"
              className="font-heading font-bold text-[#0B2545] text-[20px] sm:text-[24px] leading-none tracking-[-0.02em] transition-opacity group-hover:opacity-80"
            >
              Kavachly
            </span>
          </span>

          {/* Divider + tagline — hidden on tiny phones */}
          <span
            data-testid="header-tagline-block"
            className="hidden min-[480px]:flex items-baseline gap-3"
          >
            <span
              aria-hidden="true"
              className="block w-px h-3 bg-[#E1E5EB] translate-y-[-1px]"
            />
            <span
              data-testid="header-tagline"
              className="font-medium text-[#5C6770] text-[11px] sm:text-[12px] leading-none tracking-tight"
            >
              Insurance, audited.
            </span>
          </span>
        </Link>

        {/* Right — auth-aware avatar */}
        {showAvatar ? (
          <button
            type="button"
            data-testid="header-avatar"
            aria-label="Open settings"
            onClick={() => navigate("/dashboard/settings")}
            className="w-9 h-9 rounded-full bg-[#0B2545] text-white font-heading font-semibold text-sm flex items-center justify-center hover:bg-[#0B2545]/90 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#13A8A8] focus-visible:ring-offset-2"
          >
            {initial || <ShieldCheck className="w-4 h-4" />}
          </button>
        ) : null}
      </div>
    </header>
  );
}
