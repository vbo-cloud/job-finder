import React, { useEffect } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

import { UnsavedChangesProvider, useUnsavedChanges } from "@/lib/navigation/UnsavedChangesContext";

function Harness({
  onResult,
  saveHandler,
}: {
  onResult: (proceed: boolean) => void;
  saveHandler?: () => Promise<boolean>;
}) {
  const { setHasUnsavedChanges, registerSaveHandler, confirmNavigation } = useUnsavedChanges();

  useEffect(() => {
    if (!saveHandler) return;
    registerSaveHandler(saveHandler);
    return () => registerSaveHandler(null);
  }, [saveHandler, registerSaveHandler]);

  return (
    <div>
      <button onClick={() => setHasUnsavedChanges(true)}>mark dirty</button>
      <button onClick={() => setHasUnsavedChanges(false)}>mark clean</button>
      <button onClick={() => void confirmNavigation().then(onResult)}>navigate</button>
    </div>
  );
}

function renderHarness(props: Omit<React.ComponentProps<typeof Harness>, "onResult">) {
  const onResult = jest.fn();
  render(
    <UnsavedChangesProvider>
      <Harness onResult={onResult} {...props} />
    </UnsavedChangesProvider>,
  );
  return onResult;
}

describe("UnsavedChangesContext", () => {
  it("resolves confirmNavigation immediately, without a dialog, when there are no unsaved changes", async () => {
    const onResult = renderHarness({});

    fireEvent.click(screen.getByText("navigate"));

    await waitFor(() => expect(onResult).toHaveBeenCalledWith(true));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows the dialog when dirty, and resolves false on Annuler", async () => {
    const onResult = renderHarness({});
    fireEvent.click(screen.getByText("mark dirty"));

    fireEvent.click(screen.getByText("navigate"));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Annuler" }));

    await waitFor(() => expect(onResult).toHaveBeenCalledWith(false));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("resolves true on Quitter sans enregistrer, without invoking the save handler", async () => {
    const saveHandler = jest.fn().mockResolvedValue(true);
    const onResult = renderHarness({ saveHandler });
    fireEvent.click(screen.getByText("mark dirty"));

    fireEvent.click(screen.getByText("navigate"));
    await screen.findByRole("dialog");

    fireEvent.click(screen.getByRole("button", { name: "Quitter sans enregistrer" }));

    await waitFor(() => expect(onResult).toHaveBeenCalledWith(true));
    expect(saveHandler).not.toHaveBeenCalled();
  });

  it("Enregistrer et quitter calls the registered save handler and resolves true on success", async () => {
    const saveHandler = jest.fn().mockResolvedValue(true);
    const onResult = renderHarness({ saveHandler });
    fireEvent.click(screen.getByText("mark dirty"));

    fireEvent.click(screen.getByText("navigate"));
    await screen.findByRole("dialog");

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Enregistrer et quitter" }));
    });

    expect(saveHandler).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(onResult).toHaveBeenCalledWith(true));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("keeps the dialog open and shows an error when the save handler fails", async () => {
    const saveHandler = jest.fn().mockResolvedValue(false);
    const onResult = renderHarness({ saveHandler });
    fireEvent.click(screen.getByText("mark dirty"));

    fireEvent.click(screen.getByText("navigate"));
    await screen.findByRole("dialog");

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Enregistrer et quitter" }));
    });

    expect(await screen.findByText("Erreur lors de la sauvegarde.")).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(onResult).not.toHaveBeenCalled();
  });
});
