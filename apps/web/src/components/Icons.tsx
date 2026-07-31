import type { SVGProps } from "react";

/**
 * Lightweight inline-SVG icon set. No external dep.
 * Every icon has stroke=currentColor + width/height 20 by default so the
 * nav can just toggle text color.
 */
type P = SVGProps<SVGSVGElement>;
const base = {
  width: 20,
  height: 20,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const
};

export const IconGrid = (p: P) => (
  <svg {...base} {...p}>
    <rect x="3" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="3" width="7" height="7" rx="1.5" />
    <rect x="3" y="14" width="7" height="7" rx="1.5" />
    <rect x="14" y="14" width="7" height="7" rx="1.5" />
  </svg>
);

export const IconWallet = (p: P) => (
  <svg {...base} {...p}>
    <path d="M3 7a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    <path d="M16 12h4" />
    <circle cx="16" cy="12" r="1" />
  </svg>
);

export const IconAward = (p: P) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="9" r="5" />
    <path d="M8.5 13.5 6.5 21l5.5-3 5.5 3-2-7.5" />
  </svg>
);

export const IconTrophy = (p: P) => (
  <svg {...base} {...p}>
    <path d="M6 4h12v4a6 6 0 0 1-12 0z" />
    <path d="M4 6H2v2a3 3 0 0 0 3 3" />
    <path d="M20 6h2v2a3 3 0 0 1-3 3" />
    <path d="M9 17h6l-.5 3h-5z" />
    <path d="M12 14v3" />
  </svg>
);

export const IconList = (p: P) => (
  <svg {...base} {...p}>
    <path d="M8 6h13" /><path d="M8 12h13" /><path d="M8 18h13" />
    <circle cx="4" cy="6" r="1" /><circle cx="4" cy="12" r="1" /><circle cx="4" cy="18" r="1" />
  </svg>
);

export const IconNews = (p: P) => (
  <svg {...base} {...p}>
    <path d="M4 5a2 2 0 0 1 2-2h11a2 2 0 0 1 2 2v14l-3-2-3 2-3-2-3 2-3-2z" />
    <path d="M8 8h7M8 12h7M8 16h4" />
  </svg>
);

export const IconCalendar = (p: P) => (
  <svg {...base} {...p}>
    <rect x="3" y="5" width="18" height="16" rx="2" />
    <path d="M8 3v4M16 3v4M3 10h18" />
  </svg>
);

export const IconLine = (p: P) => (
  <svg {...base} {...p}>
    <path d="M3 3v18h18" />
    <path d="M7 15l4-4 3 3 6-7" />
  </svg>
);

export const IconCalc = (p: P) => (
  <svg {...base} {...p}>
    <rect x="4" y="3" width="16" height="18" rx="2" />
    <path d="M8 7h8M8 12h.01M12 12h.01M16 12h.01M8 16h.01M12 16h.01M16 16h.01" />
  </svg>
);

export const IconPercent = (p: P) => (
  <svg {...base} {...p}>
    <path d="M5 19 19 5" />
    <circle cx="7" cy="7" r="2" />
    <circle cx="17" cy="17" r="2" />
  </svg>
);

export const IconSearch = (p: P) => (
  <svg {...base} {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </svg>
);

export const IconArrowUpRight = (p: P) => (
  <svg {...base} {...p}>
    <path d="M7 17 17 7" />
    <path d="M8 7h9v9" />
  </svg>
);

export const IconBell = (p: P) => (
  <svg {...base} {...p}>
    <path d="M18 8a6 6 0 1 0-12 0c0 7-3 8-3 8h18s-3-1-3-8" />
    <path d="M10 21h4" />
  </svg>
);

export const IconChevronRight = (p: P) => (
  <svg {...base} {...p}>
    <path d="m9 18 6-6-6-6" />
  </svg>
);

export const IconChevronDown = (p: P) => (
  <svg {...base} {...p}>
    <path d="m6 9 6 6 6-6" />
  </svg>
);

export const IconLogo = (p: P) => (
  <svg {...base} {...p} width={p.width ?? 22} height={p.height ?? 22}>
    <rect x="3" y="3" width="18" height="18" rx="5" stroke="#2563eb" />
    <path d="M7 15l3-3 3 3 4-6" stroke="#2563eb" strokeWidth="2" />
  </svg>
);

export const IconShare = (p: P) => (
  <svg {...base} {...p}>
    <circle cx="18" cy="5" r="3" />
    <circle cx="6" cy="12" r="3" />
    <circle cx="18" cy="19" r="3" />
    <path d="M8.6 10.5 15.4 6.5M8.6 13.5l6.8 4" />
  </svg>
);

export const IconPlus = (p: P) => (
  <svg {...base} {...p}>
    <path d="M12 5v14M5 12h14" />
  </svg>
);
