import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";

jest.mock("@/lib/api/client", () => ({
  __esModule: true,
  default: {
    get: jest.fn().mockResolvedValue({ data: new Blob() }),
    delete: jest.fn().mockResolvedValue({}),
  },
}));

import apiClient from "@/lib/api/client";
import CVCard from "@/app/_components/CVCard";
import type { CVData } from "@/lib/api/types";

const baseCV: CVData = {
  id: "cv-uuid-1",
  name: "Mon CV.pdf",
  status: "matched",
  uploaded_at: "2024-06-01T10:00:00.000Z",
  match_count: 5,
  unseen_count: 2,
  has_thumbnail: false,
};

describe("CVCard", () => {
  describe("status rendering", () => {
    it("shows spinner and pending label when status is pending", () => {
      render(
        <CVCard
          cv={{ ...baseCV, status: "pending" }}
          onDeleted={jest.fn()}
        />
      );
      expect(screen.getByRole("status")).toBeInTheDocument();
      expect(screen.getByText("Analyse en cours…")).toBeInTheDocument();
    });

    it("shows spinner when status is processing", () => {
      render(
        <CVCard
          cv={{ ...baseCV, status: "processing" }}
          onDeleted={jest.fn()}
        />
      );
      expect(screen.getByRole("status")).toBeInTheDocument();
    });

    it("shows error text when status is error", () => {
      render(
        <CVCard
          cv={{ ...baseCV, status: "error" }}
          onDeleted={jest.fn()}
        />
      );
      expect(screen.getByText("Erreur")).toBeInTheDocument();
    });

    it("shows match count when status is matched", () => {
      render(<CVCard cv={baseCV} onDeleted={jest.fn()} />);
      expect(screen.getByText("5 matchs")).toBeInTheDocument();
    });

    it("shows searching label when status is done", () => {
      render(
        <CVCard cv={{ ...baseCV, status: "done" }} onDeleted={jest.fn()} />
      );
      expect(screen.getByText(/Recherche en cours/)).toBeInTheDocument();
    });

    it("uses singular match when count is 1", () => {
      render(
        <CVCard cv={{ ...baseCV, match_count: 1 }} onDeleted={jest.fn()} />
      );
      expect(screen.getByText("1 match")).toBeInTheDocument();
    });

    it("shows unseen count badge when unseen_count > 0", () => {
      render(<CVCard cv={baseCV} onDeleted={jest.fn()} />);
      expect(screen.getByText("+2")).toBeInTheDocument();
    });

    it("does not show unseen badge when unseen_count is 0", () => {
      render(
        <CVCard cv={{ ...baseCV, unseen_count: 0 }} onDeleted={jest.fn()} />
      );
      expect(screen.queryByText(/^\+/)).not.toBeInTheDocument();
    });

    it("falls back to 'CV sans nom' when name is null", () => {
      render(
        <CVCard cv={{ ...baseCV, name: null }} onDeleted={jest.fn()} />
      );
      expect(screen.getByText("CV sans nom")).toBeInTheDocument();
    });
  });

  describe("delete flow", () => {
    beforeEach(() => {
      jest.clearAllMocks();
    });

    it("shows delete button on hover (via mouse enter)", () => {
      const { container } = render(
        <CVCard cv={baseCV} onDeleted={jest.fn()} />
      );
      const wrapper = container.firstChild as HTMLElement;
      fireEvent.mouseEnter(wrapper);
      expect(
        screen.getByRole("button", { name: "Supprimer ce CV" })
      ).toBeInTheDocument();
    });

    it("clicking trash button shows confirm and cancel buttons", () => {
      const { container } = render(
        <CVCard cv={baseCV} onDeleted={jest.fn()} />
      );
      fireEvent.mouseEnter(container.firstChild as HTMLElement);
      fireEvent.click(screen.getByRole("button", { name: "Supprimer ce CV" }));
      expect(
        screen.getByRole("button", { name: "Confirmer la suppression" })
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Annuler la suppression" })
      ).toBeInTheDocument();
    });

    it("confirms delete: calls apiClient.delete and fires onDeleted callback", async () => {
      jest.useFakeTimers();
      const onDeleted = jest.fn();
      const { container } = render(<CVCard cv={baseCV} onDeleted={onDeleted} />);

      fireEvent.mouseEnter(container.firstChild as HTMLElement);
      fireEvent.click(screen.getByRole("button", { name: "Supprimer ce CV" }));
      fireEvent.click(screen.getByRole("button", { name: "Confirmer la suppression" }));

      // runAllTimersAsync fires the 400ms animation delay and flushes the
      // promise chain that follows (apiClient.delete → onDeleted).
      await act(async () => jest.runAllTimersAsync());

      expect((apiClient.delete as jest.Mock)).toHaveBeenCalledWith(`/cv/${baseCV.id}`);
      expect(onDeleted).toHaveBeenCalledWith(baseCV.id);

      jest.useRealTimers();
    });

    it("clicking cancel returns to idle state without calling delete", () => {
      const { container } = render(
        <CVCard cv={baseCV} onDeleted={jest.fn()} />
      );
      fireEvent.mouseEnter(container.firstChild as HTMLElement);
      fireEvent.click(screen.getByRole("button", { name: "Supprimer ce CV" }));
      fireEvent.click(
        screen.getByRole("button", { name: "Annuler la suppression" })
      );
      expect(
        screen.queryByRole("button", { name: "Confirmer la suppression" })
      ).not.toBeInTheDocument();
      expect((apiClient.delete as jest.Mock)).not.toHaveBeenCalled();
    });
  });

  describe("onSelect callback", () => {
    it("calls onSelect when the card body is clicked", () => {
      const onSelect = jest.fn();
      render(<CVCard cv={baseCV} onDeleted={jest.fn()} onSelect={onSelect} />);
      // Click the CV filename text — the click bubbles up to the card div with onSelect.
      fireEvent.click(screen.getByText("Mon CV.pdf"));
      expect(onSelect).toHaveBeenCalledTimes(1);
    });
  });
});
