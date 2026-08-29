import {
  forwardRef,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";

import styles from "./button.module.css";

export type ButtonVariant = "primary" | "secondary" | "quiet" | "ghost" | "danger";

export type ButtonProps = Readonly<
  Omit<ButtonHTMLAttributes<HTMLButtonElement>, "type"> & {
    variant?: ButtonVariant;
    pending?: boolean;
    pendingLabel?: string;
    children: ReactNode;
    type?: ButtonHTMLAttributes<HTMLButtonElement>["type"];
  }
>;

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
    ...props
  },
  ref,
) {
  const isDisabled = disabled || pending;
  const stableLabel = ariaLabel ?? (typeof children === "string" ? children : undefined);

  return (
    <button
      {...props}
      ref={ref}
      className={classNames(styles.button, styles[variant], className)}
      type={type}
      disabled={isDisabled}
      aria-label={pending && stableLabel ? stableLabel : ariaLabel}
      aria-busy={pending || undefined}
    >
      {pending ? <span className={styles.spinner} aria-hidden="true" /> : null}
      <span className={styles.buttonContent}>{pending ? pendingLabel ?? children : children}</span>
    </button>
  );
});

export type IconButtonProps = Readonly<
  Omit<ButtonHTMLAttributes<HTMLButtonElement>, "type" | "aria-label"> & {
    "aria-label": string;
    type?: ButtonHTMLAttributes<HTMLButtonElement>["type"];
    pending?: boolean;
  }
>;

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { className, disabled = false, pending = false, type = "button", children, ...props },
  ref,
) {
  return (
    <button
      {...props}
      ref={ref}
      className={classNames(styles.button, styles.iconButton, className)}
      type={type}
      disabled={disabled || pending}
      aria-busy={pending || undefined}
    >
      {pending ? <span className={styles.spinner} aria-hidden="true" /> : children}
    </button>
  );
});

Button.displayName = "Button";
IconButton.displayName = "IconButton";
