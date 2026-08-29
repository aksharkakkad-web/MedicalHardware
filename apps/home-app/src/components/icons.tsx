import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function IconBase({ children, ...props }: IconProps) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{children}</svg>;
}

export function HomeIcon(props: IconProps) {
  return <IconBase {...props}><path d="m3.5 10.5 8.5-7 8.5 7"/><path d="M5.5 9.5v10h13v-10M9.5 19.5v-6h5v6"/></IconBase>;
}

export function UpdateIcon(props: IconProps) {
  return <IconBase {...props}><path d="M12 3.5a7.5 7.5 0 1 0 7.5 7.5"/><path d="M12 7v5l3 2M16 3.5h4.5V8"/></IconBase>;
}

export function RoutineIcon(props: IconProps) {
  return <IconBase {...props}><path d="M8 6h12M8 12h12M8 18h12"/><path d="m3.5 6 .8.8L6 5m-2.5 7 .8.8L6 11m-2.5 7 .8.8L6 17"/></IconBase>;
}

export function ArrowIcon(props: IconProps) {
  return <IconBase {...props}><path d="M5 12h14m-5-5 5 5-5 5"/></IconBase>;
}

export function CheckIcon(props: IconProps) {
  return <IconBase {...props}><path d="m5 12 4 4L19 6"/></IconBase>;
}

export function InfoIcon(props: IconProps) {
  return <IconBase {...props}><circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8h.01"/></IconBase>;
}
