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
//     lifeSchedules: { data, error, loading },
//     overlapHints: { data, error, loading },
//     retry:    { audit(), policies(), alerts(), lifeSchedules(), overlapHints() },
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
  lifeSchedules: () =>
    api.get("/life/schedules").then((r) => r.data?.data?.schedules ?? []),
  overlapHints: () =>
    api.get("/life/overlap-hints").then((r) => r.data?.data ?? null),
};

const EMPTY = { audit: null, policies: [], alerts: [], lifeSchedules: [], overlapHints: null };

export default function useDashboardData(enabled) {
  const [data, setData] = useState(EMPTY);
  const [errors, setErrors] = useState({
    audit: null,
    policies: null,
    alerts: null,
    lifeSchedules: null,
    overlapHints: null,
  });
  // Initial loading state derived from `enabled` so a logged-out / no-audit
  // user doesn't get a one-frame flash of the skeleton.
  const [loading, setLoading] = useState(() =>
    enabled
      ? { audit: true, policies: true, alerts: true, lifeSchedules: true, overlapHints: true }
      : {
          audit: false,
          policies: false,
          alerts: false,
          lifeSchedules: false,
          overlapHints: false,
        },
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
      setLoading({
        audit: false,
        policies: false,
        alerts: false,
        lifeSchedules: false,
        overlapHints: false,
      });
      return;
    }
    // Independent — no Promise.all. Each fires its own try/catch path.
    fetchOne("audit");
    fetchOne("policies");
    fetchOne("alerts");
    fetchOne("lifeSchedules");
    fetchOne("overlapHints");
  }, [enabled, fetchOne]);

  return {
    audit: { data: data.audit, error: errors.audit, loading: loading.audit },
    policies: {
      data: data.policies,
      error: errors.policies,
      loading: loading.policies,
    },
    alerts: { data: data.alerts, error: errors.alerts, loading: loading.alerts },
    lifeSchedules: {
      data: data.lifeSchedules,
      error: errors.lifeSchedules,
      loading: loading.lifeSchedules,
    },
    overlapHints: {
      data: data.overlapHints,
      error: errors.overlapHints,
      loading: loading.overlapHints,
    },
    retry: {
      audit: () => fetchOne("audit"),
      policies: () => fetchOne("policies"),
      alerts: () => fetchOne("alerts"),
      lifeSchedules: () => fetchOne("lifeSchedules"),
      overlapHints: () => fetchOne("overlapHints"),
    },
  };
}
