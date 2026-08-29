import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button, IconButton } from "./button";

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
    expect(button.querySelector("[aria-hidden='true']")).toBeInTheDocument();
    expect(button).not.toHaveAttribute("aria-live");
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
});
