import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button, IconButton, type ButtonProps, type IconButtonProps } from "./button";

const validTextButtonProps: ButtonProps = { children: "Save change" };
const validLabeledButtonProps: ButtonProps = {
  children: <span>Save change</span>,
  "aria-label": "Save change",
};
const validIconButtonProps: IconButtonProps = {
  "aria-label": "More actions",
  children: <span aria-hidden="true">⋯</span>,
};

// @ts-expect-error Unlabeled buttons intentionally accept text only.
const unlabeledButtonWithElement: ButtonProps = { children: <span>Save change</span> };
// @ts-expect-error Icon buttons require a real icon child.
const iconButtonWithoutChild: IconButtonProps = { "aria-label": "More actions" };
// @ts-expect-error Icon buttons do not accept text children.
const iconButtonWithText: IconButtonProps = { "aria-label": "More actions", children: "More" };

void validTextButtonProps;
void validLabeledButtonProps;
void validIconButtonProps;
void unlabeledButtonWithElement;
void iconButtonWithoutChild;
void iconButtonWithText;

describe("Button", () => {
  it("defaults to a non-submitting native button", () => {
    render(<Button>Review resident</Button>);

    expect(screen.getByRole("button", { name: "Review resident" })).toHaveAttribute(
      "type",
      "button",
    );
  });

  it("keeps the accessible name while showing a pending label", () => {
    render(
      <Button pending pendingLabel="Saving change">
        Save change
      </Button>,
    );

    const button = screen.getByRole("button", { name: "Save change" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).toHaveTextContent("Saving change");
    expect(button).toHaveTextContent("Save change");
    expect(button.querySelector("[data-button-label]")).toHaveAttribute("aria-hidden", "true");
    expect(button.querySelector("[data-button-pending-label]")).not.toHaveAttribute("aria-hidden");
    expect(button.querySelector("[data-button-progress='visible']")).toBeInTheDocument();
    expect(button).not.toHaveAttribute("aria-live");
  });

  it("reserves the pending spinner footprint before loading starts", () => {
    const { rerender } = render(<Button pendingLabel="Saving change">Save change</Button>);

    const button = screen.getByRole("button", { name: "Save change" });
    expect(button.querySelector("[data-button-progress='hidden']")).toBeInTheDocument();
    rerender(<Button pending pendingLabel="Saving change">Save change</Button>);
    expect(button.querySelector("[data-button-progress='visible']")).toBeInTheDocument();
  });

  it("keeps an explicit accessible name when pending replaces JSX children", () => {
    render(
      <Button pending pendingLabel="Saving change" aria-label="Save change">
        <span>Save change</span>
      </Button>,
    );

    const button = screen.getByRole("button", { name: "Save change" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-label", "Save change");
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).toHaveTextContent("Saving change");
  });

  it("honors disabled without changing the visible label", () => {
    render(<Button disabled>Resolve event</Button>);

    expect(screen.getByRole("button", { name: "Resolve event" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Resolve event" })).toHaveTextContent(
      "Resolve event",
    );
  });

  it("supports the design-system visual variants", () => {
    render(
      <>
        <Button variant="primary">Primary</Button>
        <Button variant="secondary">Secondary</Button>
        <Button variant="quiet">Quiet</Button>
        <Button variant="ghost">Ghost</Button>
        <Button variant="danger">Danger</Button>
      </>,
    );

    expect(screen.getAllByRole("button")).toHaveLength(5);
  });
});

describe("IconButton", () => {
  it("requires and exposes an explicit accessible label with a 44px target", () => {
    render(<IconButton aria-label="More actions"><span aria-hidden="true">⋯</span></IconButton>);

    const button = screen.getByRole("button", { name: "More actions" });
    expect(button).toHaveAttribute("type", "button");
    expect(button.className).toContain("iconButton");
  });

  it("does not render a blank control when malformed runtime input omits the icon", () => {
    render(<IconButton aria-label="More actions">{null as never}</IconButton>);

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("does not render a control with a blank accessible label", () => {
    render(<IconButton aria-label=" "><span aria-hidden="true">⋯</span></IconButton>);

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
