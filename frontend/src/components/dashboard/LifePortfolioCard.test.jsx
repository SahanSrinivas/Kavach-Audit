import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import LifePortfolioCard from "./LifePortfolioCard";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

jest.mock("framer-motion", () => ({
  motion: {
    section: ({ children, ...props }) => <section {...props}>{children}</section>,
  },
}));

describe("LifePortfolioCard", () => {
  let container;
  let root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  test("renders schedule list and handles open click", () => {
    const onOpenSchedule = jest.fn();
    act(() => {
      root.render(
        <LifePortfolioCard
          schedules={[
            {
              id: "abc",
              createdAt: "2026-05-05T10:00:00Z",
              overallConfidence: 0.78,
              meta: { cisFilename: "cis.pdf", bondFilename: "bond.pdf" },
            },
          ]}
          overlap={null}
          onOpenSchedule={onOpenSchedule}
        />,
      );
    });
    const btn = Array.from(container.querySelectorAll("button")).find((b) =>
      (b.textContent || "").includes("cis.pdf + bond.pdf"),
    );
    expect(container.textContent).toContain("1 saved schedule");
    expect(container.textContent).toContain("cis.pdf + bond.pdf");
    expect(btn).toBeTruthy();
    act(() => btn.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    expect(onOpenSchedule).toHaveBeenCalledWith("abc");
  });

  test("renders overlap riders and last refreshed", () => {
    act(() => {
      root.render(
        <LifePortfolioCard
          schedules={[]}
          overlap={{
            lastRefreshedAt: "2026-05-05T10:00:00Z",
            lifeDetectedRiders: ["critical_illness"],
            hints: [{ code: "ci_overlap", title: "CI overlap", detail: "check clauses" }],
          }}
        />,
      );
    });
    expect(container.textContent).toContain("Health overlap hints");
    expect(container.textContent).toContain("Last refreshed:");
    expect(container.textContent).toContain("Critical illness");
    expect(container.textContent).toContain("CI overlap");
  });

  test("renders overlap retry path when overlap request fails", () => {
    const onRetryOverlap = jest.fn();
    act(() => {
      root.render(
        <LifePortfolioCard
          schedules={[]}
          overlap={null}
          overlapError={new Error("boom")}
          onRetryOverlap={onRetryOverlap}
        />,
      );
    });
    expect(container.textContent).toContain("Couldn't load health overlap hints.");
    const retryButton = Array.from(container.querySelectorAll("button")).find((b) =>
      (b.textContent || "").toLowerCase().includes("retry"),
    );
    expect(retryButton).toBeTruthy();
    act(() => retryButton.dispatchEvent(new MouseEvent("click", { bubbles: true })));
    expect(onRetryOverlap).toHaveBeenCalled();
  });
});

