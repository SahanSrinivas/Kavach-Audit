import React from "react";
import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="min-h-[100dvh] flex flex-col items-center justify-center px-6 text-center">
      <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#13A8A8]">404</p>
      <h1 className="mt-3 font-heading text-4xl font-bold text-[#0B2545]">Nothing here.</h1>
      <p className="mt-3 text-[#475569]">This link has moved or never existed.</p>
      <Link
        to="/"
        data-testid="notfound-home-link"
        className="mt-8 inline-flex h-12 px-6 items-center rounded-xl bg-[#0B2545] text-white font-semibold"
      >
        Back to Kavach
      </Link>
    </div>
  );
}
