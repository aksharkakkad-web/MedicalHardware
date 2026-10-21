import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FacilityTimeField } from "./facility-time-field";
function Controlled({
  initial = ""
}: {
  initial?: string;
}) {
  const [value, setValue] = useState(initial);
  return <>
      <FacilityTimeField label="Check time" value={value} onChange={setValue} timeZone="America/Chicago" />
      <output data-testid="saved-time">{value}</output>
    </>;
}
describe("facility time field", () => {
  it("uses a normal local date/time control and emits a uniquely valid ISO instant", () => {
    const onChange = vi.fn();
    render(<FacilityTimeField label="Check time" value="2026-10-21T15:00:00Z" onChange={onChange} timeZone="America/Chicago" hint="Optional check time." />);
    const control = screen.getByLabelText("Check time");
    expect(control).toHaveAttribute("type", "datetime-local");
    expect(control).toHaveValue("2026-10-21T10:00");
    fireEvent.change(control, {
      target: {
        value: "2026-10-21T09:00"
      }
    });
    expect(onChange).toHaveBeenCalledWith("2026-10-21T14:00:00.000Z");
  });
  it("keeps a spring-gap value unconfirmed and explains it in plain language", () => {
    render(<Controlled />);
    fireEvent.change(screen.getByLabelText("Check time"), {
      target: {
        value: "2026-03-08T02:30"
      }
    });
    expect(screen.getByTestId("saved-time")).toHaveTextContent("2026-03-08T02:30");
    expect(screen.getByRole("alert")).toHaveTextContent(/does not exist/i);
    expect(screen.getByLabelText("Check time")).toHaveAttribute("aria-invalid", "true");
  });
  it("requires a deliberate first or second repeated-hour choice", async () => {
    render(<Controlled />);
    fireEvent.change(screen.getByLabelText("Check time"), {
      target: {
        value: "2026-11-01T01:30"
      }
    });
    expect(screen.getByTestId("saved-time")).toHaveTextContent("2026-11-01T01:30");
    expect(screen.getByRole("alert")).toHaveTextContent(/occurs twice/i);
    expect(screen.getByRole("radio", {
      name: /First occurrence.*CDT/i
    })).not.toBeChecked();
    await userEvent.click(screen.getByRole("radio", {
      name: /Second occurrence.*CST/i
    }));
    expect(screen.getByTestId("saved-time")).toHaveTextContent("2026-11-01T07:30:00.000Z");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
  it("keeps an existing repeated-hour instant selected and respects required/disabled", () => {
    render(<FacilityTimeField label="Check time" value="2026-11-01T07:30:25Z" onChange={() => undefined} timeZone="America/Chicago" required disabled />);
    expect(screen.getByRole("radio", {
      name: /Second occurrence.*CST/i
    })).toBeChecked();
    expect(screen.getByLabelText(/^Check time/)).toBeRequired();
    expect(screen.getByLabelText(/^Check time/)).toBeDisabled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
