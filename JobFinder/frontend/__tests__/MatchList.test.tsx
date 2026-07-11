import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import MatchList, { SKELETON_COUNT, type MatchItemData } from "@/app/_components/MatchList";
import type { MatchOut } from "@/lib/api/types";

function makeMatch(id: string, score = 0.8): MatchOut {
  return {
    score,
    is_new: false,
    analysis: null,
    offer: {
      id,
      ft_id: `FT-${id}`,
      title: `Offre ${id}`,
      company: "ACME",
      location: "Paris",
      contract_type: "CDI",
      description: "",
      salary: null,
      rome_code: null,
      skills: [],
      expires_at: null,
    },
  };
}

function makeItem(id: string, score = 0.8): MatchItemData {
  return {
    match: makeMatch(id, score),
    isNew: true,
    isSaved: false,
    isExpanded: false,
    analysisPending: false,
    onSelect: jest.fn(),
    onSave: jest.fn(),
    onReject: jest.fn(),
    onAnalyze: jest.fn(),
  };
}

describe("MatchList", () => {
  it("renders skeleton placeholders when loading", () => {
    const { container } = render(
      <MatchList items={[]} loading={true} rejectedCount={0} onRestoreAll={jest.fn()} />,
    );
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons).toHaveLength(SKELETON_COUNT);
  });

  it("shows empty state message when no items and not loading", () => {
    render(
      <MatchList items={[]} loading={false} rejectedCount={0} onRestoreAll={jest.fn()} />,
    );
    expect(screen.getByText("Aucune offre ne correspond")).toBeInTheDocument();
  });

  it("renders a MatchItem for each item", () => {
    const items = [makeItem("1"), makeItem("2"), makeItem("3")];
    render(
      <MatchList items={items} loading={false} rejectedCount={0} onRestoreAll={jest.fn()} />,
    );
    expect(screen.getByText("Offre 1")).toBeInTheDocument();
    expect(screen.getByText("Offre 2")).toBeInTheDocument();
    expect(screen.getByText("Offre 3")).toBeInTheDocument();
  });

  it("does not show empty state when items are present", () => {
    render(
      <MatchList items={[makeItem("1")]} loading={false} rejectedCount={0} onRestoreAll={jest.fn()} />,
    );
    expect(screen.queryByText("Aucune offre ne correspond")).not.toBeInTheDocument();
  });

  it("does not show empty state when still loading", () => {
    render(
      <MatchList items={[]} loading={true} rejectedCount={0} onRestoreAll={jest.fn()} />,
    );
    expect(screen.queryByText("Aucune offre ne correspond")).not.toBeInTheDocument();
  });

  it("shows rejected banner when rejectedCount > 0", () => {
    render(
      <MatchList items={[]} loading={false} rejectedCount={2} onRestoreAll={jest.fn()} />,
    );
    expect(screen.getByText(/2 offres masquées/)).toBeInTheDocument();
    expect(screen.getByText("Réafficher")).toBeInTheDocument();
  });

  it("calls onRestoreAll when Réafficher is clicked", () => {
    const onRestoreAll = jest.fn();
    render(
      <MatchList items={[]} loading={false} rejectedCount={1} onRestoreAll={onRestoreAll} />,
    );
    fireEvent.click(screen.getByText("Réafficher"));
    expect(onRestoreAll).toHaveBeenCalledTimes(1);
  });
});
