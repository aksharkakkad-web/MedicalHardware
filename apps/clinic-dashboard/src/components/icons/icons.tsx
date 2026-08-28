import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function Icon({ children, ...props }: IconProps & { children: React.ReactNode }) {
  return (
    <svg aria-hidden="true" fill="none" viewBox="0 0 24 24" {...props}>
      <g stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8">
        {children}
      </g>
    </svg>
  );
}

export function OverviewIcon(props: IconProps) {
  return <Icon {...props}><path d="M4 13h6V4H4v9Zm10 7h6v-9h-6v9ZM4 20h6v-3H4v3Zm10-13h6V4h-6v3Z" /></Icon>;
}

export function EventIcon(props: IconProps) {
  return <Icon {...props}><path d="M12 3.5 3.8 18a1.7 1.7 0 0 0 1.5 2.5h13.4a1.7 1.7 0 0 0 1.5-2.5L12 3.5Z" /><path d="M12 9v4.5M12 17h.01" /></Icon>;
}

export function ResidentsIcon(props: IconProps) {
  return <Icon {...props}><path d="M16 20v-1.5a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4V20M9.5 10.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM16 4a3.4 3.4 0 0 1 0 6.6M21 20v-1.5a4 4 0 0 0-3-3.8" /></Icon>;
}

export function ArrowIcon(props: IconProps) {
  return <Icon {...props}><path d="m9 18 6-6-6-6" /></Icon>;
}

export function SearchIcon(props: IconProps) {
  return <Icon {...props}><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></Icon>;
}

export function CareMark(props: IconProps) {
  return <Icon {...props}><path d="M20.8 5.8a5 5 0 0 0-7.1 0L12 7.5l-1.7-1.7a5 5 0 0 0-7.1 7.1L12 21l8.8-8.1a5 5 0 0 0 0-7.1Z" /><path d="M7.5 12h2l1.2-2.5 2.1 5 1.2-2.5h2.5" /></Icon>;
}
