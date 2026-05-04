import { useCallback, useEffect, useState } from "react";
import api from "../lib/api";

// One hook for the three independent dashboard fetches.
//
// Old code used Promise.all, which fails the entire dashboard if ANY
// of the three rejects — a /policies 500 left audit/alerts as null and
// the user saw "you haven't run your audit yet" (wrong: audit DID
// succeed, policies just failed). Promise.allSettled-style here:
// each fetch lives or dies on its own, and per-section retry callbacks
// let the user re-pull just the section that broke.
//
// Shape:
//   {
//     audit:    { data, error, loading },
//     policies: { data, error, loading },
//     alerts:   { data, error, loading },
//     retry:    { audit(), policies(), alerts() },
//   }
//
// data is null/[] (not undefined) so the consumer can spread without
// optional-chaining everywhere.

const FETCHERS = {
  audit: () =>
    api.get("/audit/latest").then((r) => r.data?.data?.audit ?? null),
  policies: () =>
    api.get("/policies").then((r) => r.data?.data?.policies ?? []),
  alerts: () =>
    api.get("/alerts").then((r) => r.data?.data?.alerts ?? []),
};

const EMPTY = { audit: null, policies: [], alerts: [] };

export default function useDashboardData(enabled) {
  const [data, setData] = useState(EMPTY);
  const [errors, setErrors] = useState({
    audit: null,
    policies: null,
    alerts: null,
  });
  // Initial loading state derived from `enabled` so a logged-out / no-audit
  // user doesn't get a one-frame flash of the skeleton.
  const [loading, setLoading] = useState(() =>
    enabled
      ? { audit: true, policies: true, alerts: true }
      : { audit: false, policies: false, alerts: false },
  );

  const fetchOne = useCallback(async (key) => {
    setLoading((l) => ({ ...l, [key]: true }));
    setErrors((e) => ({ ...e, [key]: null }));
    try {
      const result = await FETCHERS[key]();
      setData((d) => ({ ...d, [key]: result }));
    } catch (err) {
      setErrors((e) => ({ ...e, [key]: err }));
    } finally {
      setLoading((l) => ({ ...l, [key]: false }));
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      setLoading({ audit: false, policies: false, alerts: false });
      return;
    }
    // Independent — no Promise.all. Each fires its own try/catch path.
    fetchOne("audit");
    fetchOne("policies");
    fetchOne("alerts");
  }, [enabled, fetchOne]);

  return {
    audit: { data: data.audit, error: errors.audit, loading: loading.audit },
    policies: {
      data: data.policies,
      error: errors.policies,
      loading: loading.policies,
    },
    alerts: { data: data.alerts, error: errors.alerts, loading: loading.alerts },
    retry: {
      audit: () => fetchOne("audit"),
      policies: () => fetchOne("policies"),
      alerts: () => fetchOne("alerts"),
    },
  };
}
