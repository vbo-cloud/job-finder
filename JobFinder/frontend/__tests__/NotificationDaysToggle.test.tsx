import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import NotificationDaysToggle from "@/app/profile/_components/NotificationDaysToggle";

describe("NotificationDaysToggle", () => {
  it("renders all seven days", () => {
    render(<NotificationDaysToggle value={[]} onChange={jest.fn()} />);

    ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"].forEach((label) => {
      expect(screen.getByText(label)).toBeInTheDocument();
    });
  });

  it("marks the days present in value as pressed", () => {
    render(<NotificationDaysToggle value={[7]} onChange={jest.fn()} />);

    expect(screen.getByText("Dim").closest("button")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Lun").closest("button")).toHaveAttribute("aria-pressed", "false");
  });

  it("adds a day to the selection when an inactive day is clicked", () => {
    const onChange = jest.fn();
    render(<NotificationDaysToggle value={[7]} onChange={onChange} />);

    fireEvent.click(screen.getByText("Lun").closest("button")!);

    expect(onChange).toHaveBeenCalledWith([1, 7]);
  });

  it("removes a day from the selection when an active day is clicked", () => {
    const onChange = jest.fn();
    render(<NotificationDaysToggle value={[1, 7]} onChange={onChange} />);

    fireEvent.click(screen.getByText("Dim").closest("button")!);

    expect(onChange).toHaveBeenCalledWith([1]);
  });

  it("can clear the last selected day, leaving notifications disabled", () => {
    const onChange = jest.fn();
    render(<NotificationDaysToggle value={[7]} onChange={onChange} />);

    fireEvent.click(screen.getByText("Dim").closest("button")!);

    expect(onChange).toHaveBeenCalledWith([]);
  });
});
