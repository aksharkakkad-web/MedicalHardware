import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Modal } from "./modal";

afterEach(() => {
  document.body.style.removeProperty("overflow");
  document.body.style.removeProperty("overflow-x");
  document.body.style.removeProperty("overflow-y");
});

describe("Modal", () => {
  it("opens the native dialog with its title, description and initial title focus", () => {
    const { rerender, container } = render(
      <Modal open={false} title="Respond to concern" description="Room 214 · Avery Chen" onRequestClose={vi.fn()}>
        <p>Response controls</p>
      </Modal>,
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(container.querySelector("dialog")).not.toHaveAttribute("open");

    rerender(
      <Modal open title="Respond to concern" description="Room 214 · Avery Chen" onRequestClose={vi.fn()}>
        <p>Response controls</p>
      </Modal>,
    );

    const dialog = screen.getByRole("dialog", { name: "Respond to concern" });
    expect(dialog.tagName).toBe("DIALOG");
    expect(dialog).toHaveAttribute("open");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAccessibleDescription("Room 214 · Avery Chen");
    expect(screen.getByRole("heading", { name: "Respond to concern" })).toHaveFocus();
    expect(screen.getByText("Response controls")).toBeInTheDocument();
  });

  it("uses distinct title and description IDs for every instance", () => {
    const { container } = render(
      <>
        <Modal open={false} title="First response" description="First context" onRequestClose={vi.fn()}>First</Modal>
        <Modal open={false} title="Second response" description="Second context" onRequestClose={vi.fn()}>Second</Modal>
      </>,
    );

    const dialogs = [...container.querySelectorAll("dialog")];
    const ids = dialogs.flatMap((dialog) => [dialog.getAttribute("aria-labelledby"), dialog.getAttribute("aria-describedby")]);
    expect(new Set(ids).size).toBe(4);
    ids.forEach((id) => expect(document.getElementById(id!)).toBeInTheDocument());
  });

  it("omits the description relationship when no description is supplied", () => {
    render(<Modal open title="Response" onRequestClose={vi.fn()}>Content</Modal>);
    expect(screen.getByRole("dialog")).not.toHaveAttribute("aria-describedby");
  });

  it("requests Close without submitting or closing ahead of controlled state", async () => {
    const user = userEvent.setup();
    const onRequestClose = vi.fn();
    const onSubmit = vi.fn((event) => event.preventDefault());
    render(
      <form onSubmit={onSubmit}>
        <Modal open title="Response" closeLabel="Close response" onRequestClose={onRequestClose}>Content</Modal>
      </form>,
    );

    const close = screen.getByRole("button", { name: "Close response" });
    expect(close).toHaveAttribute("type", "button");
    await user.click(close);
    expect(onRequestClose).toHaveBeenCalledTimes(1);
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toHaveAttribute("open");
  });

  it("prevents native Escape dismissal and requests controlled dismissal", () => {
    const onRequestClose = vi.fn();
    render(<Modal open title="Response" onRequestClose={onRequestClose}>Content</Modal>);
    const cancel = new Event("cancel", { cancelable: true });
    fireEvent(screen.getByRole("dialog"), cancel);

    expect(cancel.defaultPrevented).toBe(true);
    expect(onRequestClose).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("dialog")).toHaveAttribute("open");
  });

  it("blocks Close and Escape while dismissal is disabled", async () => {
    const user = userEvent.setup();
    const onRequestClose = vi.fn();
    render(<Modal open title="Response" dismissDisabled onRequestClose={onRequestClose}>Saving response</Modal>);
    const close = screen.getByRole("button", { name: "Close" });
    expect(close).toBeDisabled();
    await user.click(close);
    const cancel = new Event("cancel", { cancelable: true });
    fireEvent(screen.getByRole("dialog"), cancel);

    expect(cancel.defaultPrevented).toBe(true);
    expect(onRequestClose).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toHaveAttribute("open");
  });

  it("restores focus to the original trigger when controlled state closes", () => {
    render(<button>Respond</button>);
    const trigger = screen.getByRole("button", { name: "Respond" });
    trigger.focus();
    const { rerender } = render(<Modal open title="Response" onRequestClose={vi.fn()}>Content</Modal>);
    rerender(<Modal open={false} title="Response" onRequestClose={vi.fn()}>Content</Modal>);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("focuses the workspace when the original trigger disappears", () => {
    const { rerender } = render(
      <>
        <main id="care-workspace">Care workspace</main>
        <button>Respond</button>
        <Modal open={false} title="Response" onRequestClose={vi.fn()}>Content</Modal>
      </>,
    );
    screen.getByRole("button", { name: "Respond" }).focus();
    rerender(
      <>
        <main id="care-workspace">Care workspace</main>
        <button>Respond</button>
        <Modal open title="Response" onRequestClose={vi.fn()}>Content</Modal>
      </>,
    );
    rerender(
      <>
        <main id="care-workspace">Care workspace</main>
        <Modal open={false} title="Response" onRequestClose={vi.fn()}>Content</Modal>
      </>,
    );

    expect(screen.getByRole("main")).toHaveFocus();
  });

  it("restores the original scroll properties and priorities on close", () => {
    document.body.style.setProperty("overflow-x", "clip", "important");
    document.body.style.setProperty("overflow-y", "scroll");
    const { rerender } = render(<Modal open title="Response" onRequestClose={vi.fn()}>Content</Modal>);
    expect(document.body.style.overflow).toBe("hidden");
    rerender(<Modal open={false} title="Response" onRequestClose={vi.fn()}>Content</Modal>);

    expect(document.body.style.getPropertyValue("overflow-x")).toBe("clip");
    expect(document.body.style.getPropertyPriority("overflow-x")).toBe("important");
    expect(document.body.style.getPropertyValue("overflow-y")).toBe("scroll");
    expect(document.body.style.getPropertyValue("overflow")).toBe("");
  });

  it("cleans up body locking and focus when unmounted", () => {
    render(<button>Respond</button>);
    const trigger = screen.getByRole("button", { name: "Respond" });
    trigger.focus();
    document.body.style.setProperty("overflow", "auto", "important");
    const { unmount } = render(<Modal open title="Response" onRequestClose={vi.fn()}>Content</Modal>);
    unmount();

    expect(document.body.style.overflow).toBe("auto");
    expect(document.body.style.getPropertyPriority("overflow")).toBe("important");
    expect(trigger).toHaveFocus();
  });

  it("keeps open lifecycle cleanup safe under Strict Mode", () => {
    render(<button>Respond</button>);
    const trigger = screen.getByRole("button", { name: "Respond" });
    trigger.focus();
    const { unmount } = render(
      <StrictMode><Modal open title="Response" onRequestClose={vi.fn()}>Content</Modal></StrictMode>,
    );

    expect(screen.getByRole("dialog")).toHaveAttribute("open");
    expect(screen.getByRole("heading", { name: "Response" })).toHaveFocus();
    expect(document.body.style.overflow).toBe("hidden");
    unmount();
    expect(document.body.style.overflow).toBe("");
    expect(trigger).toHaveFocus();
  });
});
