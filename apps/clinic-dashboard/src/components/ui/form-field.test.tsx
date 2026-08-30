import { render, screen } from "@testing-library/react";
import { createRef } from "react";
import { describe, expect, it } from "vitest";

import { FormField, FormFieldset } from "./form-field";

describe("FormField", () => {
  it("connects an explicit visible label to the native control", () => {
    render(<FormField id="resident-search" label="Search residents" type="search" />);

    const input = screen.getByRole("searchbox", { name: "Search residents" });
    expect(input).toHaveAttribute("id", "resident-search");
    expect(screen.getByText("Search residents")).toHaveAttribute("for", "resident-search");
  });

  it("creates unique control, hint, and error IDs when no id is supplied", () => {
    render(
      <>
        <FormField label="First name" hint="Use the resident's preferred name." />
        <FormField label="Last name" hint="Use the resident's family name." />
      </>,
    );

    const controls = screen.getAllByRole("textbox");
    expect(new Set(controls.map((control) => control.id)).size).toBe(2);
    controls.forEach((control) => {
      const describedBy = control.getAttribute("aria-describedby")?.split(" ") ?? [];
      expect(describedBy).toHaveLength(1);
      expect(document.getElementById(describedBy[0])).toHaveTextContent(/Use the resident/);
    });
  });

  it("connects hint and appearing error text and marks the control invalid", () => {
    render(
      <FormField
        id="care-note"
        label="Care note"
        hint="Record what staff observed."
        error="Add what staff observed before saving."
        as="textarea"
        required
      />,
    );

    const control = screen.getByRole("textbox", { name: /Care note/ });
    expect(control).toHaveAttribute("aria-invalid", "true");
    expect(control).toHaveAttribute("required");
    const describedBy = control.getAttribute("aria-describedby")?.split(" ") ?? [];
    expect(describedBy).toHaveLength(2);
    expect(new Set(describedBy).size).toBe(2);
    expect(describedBy).not.toContain("care-note-hint");
    expect(describedBy).not.toContain("care-note-error");
    expect(describedBy.every((id) => /-(hint|error)$/.test(id))).toBe(true);
    describedBy.forEach((id) => expect(document.getElementById(id)).toBeInTheDocument());
    expect(screen.getByText("Record what staff observed.")).toHaveAttribute("id", describedBy[0]);
    expect(screen.getByText("Add what staff observed before saving.")).toHaveAttribute("id", describedBy[1]);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(control).not.toHaveAttribute("readonly");
  });

  it("keeps generated hint and error IDs opaque when explicit control IDs could collide", () => {
    render(
      <>
        <FormField id="foo" label="Foo" hint="Foo hint" error="Foo error" />
        <FormField id="foo-hint" label="Foo hint control" hint="Second hint" />
      </>,
    );

    const foo = screen.getByRole("textbox", { name: "Foo" });
    const fooHintControl = screen.getByRole("textbox", { name: "Foo hint control" });
    const fooDescriptions = foo.getAttribute("aria-describedby")?.split(" ") ?? [];
    const secondDescriptions = fooHintControl.getAttribute("aria-describedby")?.split(" ") ?? [];

    expect(fooDescriptions).toHaveLength(2);
    expect(secondDescriptions).toHaveLength(1);
    expect(fooDescriptions).not.toContain(fooHintControl.id);
    expect(fooDescriptions).not.toContain("foo-hint");
    expect(new Set([...fooDescriptions, ...secondDescriptions]).size).toBe(3);
    [...fooDescriptions, ...secondDescriptions].forEach((id) => {
      expect(document.getElementById(id)).toBeInTheDocument();
      expect(id).not.toBe(foo.id);
      expect(id).not.toBe(fooHintControl.id);
    });
  });

  it("forwards a typed ref to each native control kind", () => {
    const inputRef = createRef<HTMLInputElement>();
    const textareaRef = createRef<HTMLTextAreaElement>();
    const selectRef = createRef<HTMLSelectElement>();

    render(
      <>
        <FormField label="Input" ref={inputRef} />
        <FormField as="textarea" label="Textarea" ref={textareaRef} />
        <FormField as="select" label="Select" ref={selectRef} options={[{ value: "one", label: "One" }]} />
      </>,
    );

    expect(inputRef.current).toBe(screen.getByRole("textbox", { name: "Input" }));
    expect(textareaRef.current).toBe(screen.getByRole("textbox", { name: "Textarea" }));
    expect(selectRef.current).toBe(screen.getByRole("combobox", { name: "Select" }));
  });

  it("renders native select options and preserves disabled/read-only semantics", () => {
    render(
      <>
        <FormField
          id="workflow-state"
          label="Workflow state"
          as="select"
          defaultValue="acknowledged"
          options={[
            { value: "new", label: "New" },
            { value: "acknowledged", label: "Acknowledged" },
          ]}
        />
        <FormField id="room" label="Room" defaultValue="Room 214" disabled />
        <FormField id="resident" label="Resident" defaultValue="Avery Chen" readOnly />
      </>,
    );

    const select = screen.getByRole("combobox", { name: "Workflow state" });
    expect(select).toHaveValue("acknowledged");
    expect(screen.getByRole("option", { name: "New" })).toHaveValue("new");
    expect(screen.getByRole("option", { name: "Acknowledged" })).toHaveValue("acknowledged");
    expect(screen.getByRole("textbox", { name: "Room" })).toBeDisabled();
    expect(screen.getByRole("textbox", { name: "Resident" })).toHaveAttribute("readonly");
  });

  it("keeps grouped native controls under a fieldset and legend", () => {
    render(
      <FormFieldset legend="Follow-up timing">
        <label><input type="radio" name="timing" value="now" /> This round</label>
        <label><input type="radio" name="timing" value="later" /> Next round</label>
      </FormFieldset>,
    );

    expect(screen.getByRole("group", { name: "Follow-up timing" })).toBeInTheDocument();
    expect(screen.getAllByRole("radio")).toHaveLength(2);
  });
});
