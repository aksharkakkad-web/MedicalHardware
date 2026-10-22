"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";

import { Button } from "./button";
import styles from "./modal.module.css";

export type ModalProps = Readonly<{
  open: boolean;
  title: string;
  description?: string;
  children: ReactNode;
  onRequestClose: () => void;
  dismissDisabled?: boolean;
  closeLabel?: string;
}>;

function restoreFocus(previousFocus: HTMLElement | null) {
  const target = previousFocus?.isConnected && previousFocus !== document.body
    ? previousFocus
    : document.querySelector<HTMLElement>("main#care-workspace, main");
  if (!target) return;

  const needsTemporaryTabIndex = !target.hasAttribute("tabindex") && target.tabIndex < 0;
  if (needsTemporaryTabIndex) target.setAttribute("tabindex", "-1");
  target.focus({ preventScroll: true });
  if (needsTemporaryTabIndex) target.removeAttribute("tabindex");
}

export function Modal({
  open,
  title,
  description,
  children,
  onRequestClose,
  dismissDisabled = false,
  closeLabel = "Close",
}: ModalProps) {
  const id = useId();
  const titleId = `${id}-title`;
  const descriptionId = `${id}-description`;
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!open || !dialog) return;

    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const bodyStyle = document.body.style;
    const overflowProperties = ["overflow", "overflow-x", "overflow-y"] as const;
    const previousOverflow = overflowProperties.map((property) => ({
      property,
      value: bodyStyle.getPropertyValue(property),
      priority: bodyStyle.getPropertyPriority(property),
    }));

    if (!dialog.open) dialog.showModal();
    overflowProperties.forEach((property) => bodyStyle.removeProperty(property));
    bodyStyle.setProperty("overflow", "hidden");
    titleRef.current?.focus({ preventScroll: true });

    return () => {
      if (dialog.open) dialog.close();
      overflowProperties.forEach((property) => bodyStyle.removeProperty(property));
      previousOverflow.forEach(({ property, value, priority }) => {
        if (value) bodyStyle.setProperty(property, value, priority);
      });
      restoreFocus(previousFocus);
    };
  }, [open]);

  function requestClose() {
    if (!dismissDisabled) onRequestClose();
  }

  return (
    <dialog
      ref={dialogRef}
      className={styles.dialog}
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      onCancel={(event) => {
        // Keep dismissal controlled so callers can preserve unsaved work.
        event.preventDefault();
        requestClose();
      }}
    >
      <header className={styles.header}>
        <div className={styles.heading}>
          <h2 id={titleId} ref={titleRef} className={styles.title} tabIndex={-1}>{title}</h2>
          {description ? <p id={descriptionId} className={styles.description}>{description}</p> : null}
        </div>
        <Button
          className={styles.close}
          variant="secondary"
          type="button"
          aria-label={closeLabel}
          disabled={dismissDisabled}
          onClick={requestClose}
        >
          Close
        </Button>
      </header>
      <div className={styles.content}>{children}</div>
    </dialog>
  );
}
