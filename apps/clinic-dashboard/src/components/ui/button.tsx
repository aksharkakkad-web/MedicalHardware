import {
  forwardRef,
  isValidElement,
  type ButtonHTMLAttributes,
  type ReactElement,
  type ReactNode,
} from "react";

import styles from "./button.module.css";

export type ButtonVariant = "primary" | "secondary" | "quiet" | "ghost" | "danger";

type ButtonBaseProps = Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  "type" | "children" | "aria-label"
> & {
  variant?: ButtonVariant;
  pending?: boolean;
  type?: ButtonHTMLAttributes<HTMLButtonElement>["type"];
};

type ButtonTextProps = ButtonBaseProps & {
  children: string;
  "aria-label"?: string;
  "aria-labelledby"?: string;
  pendingLabel?: string;
};

type ButtonLabeledProps = ButtonBaseProps & {
  children: ReactNode;
  pendingLabel?: string;
} & (
    | { "aria-label": string; "aria-labelledby"?: string }
    | { "aria-label"?: string; "aria-labelledby": string }
  );

type ButtonUnlabeledProps = ButtonBaseProps & {
  children: string;
  "aria-label"?: never;
  "aria-labelledby"?: never;
  pendingLabel?: never;
};

export type ButtonProps = Readonly<ButtonTextProps | ButtonLabeledProps | ButtonUnlabeledProps>;

function classNames(...names: Array<string | undefined | false>) {
  return names.filter(Boolean).join(" ");
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    children,
    className,
    disabled = false,
    pending = false,
    pendingLabel,
    type = "button",
    variant = "primary",
    "aria-label": ariaLabel,
    "aria-labelledby": ariaLabelledBy,
    ...props
  },
  ref,
) {
  const isDisabled = disabled || pending;
  const stableLabel = ariaLabel ?? (typeof children === "string" ? children : undefined);
  const hasStableAccessibleName = stableLabel !== undefined || ariaLabelledBy !== undefined;
  const shouldReplaceChildren = pending && pendingLabel !== undefined && hasStableAccessibleName;

  return (
    <button
      {...props}
      ref={ref}
      className={classNames(styles.button, styles[variant], className)}
      type={type}
      disabled={isDisabled}
      aria-label={stableLabel}
      aria-labelledby={ariaLabelledBy}
      aria-busy={pending || undefined}
    >
      <span
        className={styles.progressSlot}
        data-button-progress={pending ? "visible" : "hidden"}
        aria-hidden="true"
      >
        <span className={styles.spinner} />
      </span>
      <span className={styles.buttonContent}>
        <span
          className={styles.buttonLabel}
          data-button-label
          aria-hidden={shouldReplaceChildren || undefined}
        >
          {children}
        </span>
        {shouldReplaceChildren ? (
          <span className={styles.pendingLabel} data-button-pending-label>
            {pendingLabel}
          </span>
        ) : null}
      </span>
    </button>
  );
});

export type IconButtonProps = Readonly<
  Omit<ButtonHTMLAttributes<HTMLButtonElement>, "type" | "aria-label" | "children"> & {
    "aria-label": string;
    children: ReactElement;
    type?: ButtonHTMLAttributes<HTMLButtonElement>["type"];
    pending?: boolean;
  }
>;

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { className, disabled = false, pending = false, type = "button", children, ...props },
  ref,
) {
  const accessibleLabel = props["aria-label"];
  if (!isValidElement(children) || typeof accessibleLabel !== "string" || accessibleLabel.trim().length === 0) {
    return null;
  }

  return (
    <button
      {...props}
      ref={ref}
      className={classNames(styles.button, styles.iconButton, className)}
      type={type}
      disabled={disabled || pending}
      aria-busy={pending || undefined}
    >
      <span className={styles.iconContent}>
        <span className={styles.iconLabel} aria-hidden={pending || undefined} data-icon-label>
          {children}
        </span>
        {pending ? (
          <span className={styles.iconPending} data-icon-pending aria-hidden="true">
            <span className={styles.spinner} />
          </span>
        ) : null}
      </span>
    </button>
  );
});

Button.displayName = "Button";
IconButton.displayName = "IconButton";
