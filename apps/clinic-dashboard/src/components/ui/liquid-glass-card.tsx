"use client";

import {
  forwardRef,
  useId,
  type CSSProperties,
  type HTMLAttributes,
  type ReactNode,
} from "react";

import styles from "./liquid-glass-card.module.css";

export type LiquidGlassCardSize = "small" | "default";

export type LiquidGlassCardProps = Readonly<
  Omit<HTMLAttributes<HTMLDivElement>, "children"> & {
    children: ReactNode;
    glassEffect?: boolean;
    size?: LiquidGlassCardSize;
  }
>;

type GlassFilterStyle = CSSProperties & {
  WebkitBackdropFilter?: string;
};

function classNames(...names: Array<string | undefined | false>) {
  return names.filter(Boolean).join(" ");
}

/**
 * An opt-in display treatment for non-operational marketing, empty-state, or
 * future showcase content. Do not use it for resident data, status, forms,
 * navigation, or caregiver work queues; Clear Signal operational surfaces
 * must remain flat and unambiguous.
 * Adapted from Kokonut UI's MIT-licensed Liquid Glass Card.
 */
export const LiquidGlassCard = forwardRef<HTMLDivElement, LiquidGlassCardProps>(
  function LiquidGlassCard(
    {
      children,
      className,
      glassEffect = false,
      size = "default",
      ...props
    },
    ref,
  ) {
    const reactId = useId();
    const filterId = `ac-liquid-glass-${reactId.replace(/[^a-zA-Z0-9_-]/g, "")}`;
    const filterReference = `url("#${filterId}")`;
    const filterStyle: GlassFilterStyle = {
      backdropFilter: filterReference,
      WebkitBackdropFilter: filterReference,
    };

    return (
      <div
        {...props}
        ref={ref}
        className={classNames(styles.card, className)}
        data-glass-effect={glassEffect ? "on" : "off"}
        data-size={size}
      >
        {glassEffect ? (
          <>
            <svg
              aria-hidden="true"
              className={styles.filterDefinition}
              focusable="false"
              width="0"
              height="0"
            >
              <defs>
                <filter
                  id={filterId}
                  colorInterpolationFilters="sRGB"
                  height="200%"
                  width="200%"
                  x="-50%"
                  y="-50%"
                >
                  <feTurbulence
                    baseFrequency="0.05 0.05"
                    numOctaves="1"
                    result="noise"
                    seed="1"
                    type="fractalNoise"
                  />
                  <feGaussianBlur in="noise" result="softNoise" stdDeviation="2" />
                  <feDisplacementMap
                    in="SourceGraphic"
                    in2="softNoise"
                    scale="24"
                    xChannelSelector="R"
                    yChannelSelector="B"
                  />
                </filter>
              </defs>
            </svg>
            <span
              aria-hidden="true"
              className={styles.refraction}
              data-liquid-glass-refraction
              style={filterStyle}
            />
            <span aria-hidden="true" className={styles.highlight} />
          </>
        ) : null}
        <div className={styles.content}>{children}</div>
      </div>
    );
  },
);

LiquidGlassCard.displayName = "LiquidGlassCard";
