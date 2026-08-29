import {
  forwardRef,
  type ButtonHTMLAttributes,
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
  children: ReactNode;
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
      aria-label={pending && stableLabel !== undefined ? stableLabel : ariaLabel}
      aria-labelledby={ariaLabelledBy}
      aria-busy={pending || undefined}
    >
      {pending ? <span className={styles.spinner} aria-hidden="true" /> : null}
      <span className={styles.buttonContent}>
        {shouldReplaceChildren ? pendingLabel : children}
      </span>
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
