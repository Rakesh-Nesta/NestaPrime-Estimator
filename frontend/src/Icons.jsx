// Amendment 36 follow-up (Section 42): small line-icon set for the sidebar
// nav items, KPI tiles, and top bar -- matching the CRM reference's use of
// an icon per header/tile. Same stroke-based style as the chevron/hamburger
// icons already used elsewhere in this app (Sidebar.jsx, the old nav).
function Icon({ children, className = "w-4 h-4" }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      {children}
    </svg>
  );
}

export function GridIcon(props) {
  return (
    <Icon {...props}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z" />
    </Icon>
  );
}

export function UsersIcon(props) {
  return (
    <Icon {...props}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M17 20v-1a4 4 0 00-4-4H7a4 4 0 00-4 4v1M15 3.13a4 4 0 010 7.75M21 20v-1a4 4 0 00-3-3.87" />
      <circle cx="9" cy="7" r="4" strokeLinecap="round" strokeLinejoin="round" />
    </Icon>
  );
}

export function FunnelIcon(props) {
  return (
    <Icon {...props}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 4h16l-6 8v6l-4 2v-8z" />
    </Icon>
  );
}

export function DocumentIcon(props) {
  return (
    <Icon {...props}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 4h6l4 4v12H5V4z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M14 4v4h4M8 13h8M8 17h5" />
    </Icon>
  );
}

export function FolderIcon(props) {
  return (
    <Icon {...props}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
    </Icon>
  );
}

export function CalendarIcon(props) {
  return (
    <Icon {...props}>
      <rect x="3" y="5" width="18" height="16" rx="2" strokeLinecap="round" strokeLinejoin="round" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h18M8 3v4M16 3v4" />
    </Icon>
  );
}

export function ClockIcon(props) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="9" strokeLinecap="round" strokeLinejoin="round" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 7v5l3 3" />
    </Icon>
  );
}

export function BellIcon(props) {
  return (
    <Icon {...props}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 8a6 6 0 1112 0c0 4 1.5 5.5 1.5 5.5H4.5S6 12 6 8z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M10 19a2 2 0 004 0" />
    </Icon>
  );
}

export function ShieldIcon(props) {
  return (
    <Icon {...props}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4" />
    </Icon>
  );
}

export function SearchIcon(props) {
  return (
    <Icon {...props}>
      <circle cx="11" cy="11" r="7" strokeLinecap="round" strokeLinejoin="round" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35" />
    </Icon>
  );
}

// Admin Overview redesign (2026-09-27): one small icon per role in the
// "Active people by role" grid, same stroke style as the rest of this file.
export function CrownIcon(props) {
  return (
    <Icon {...props}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 17h18l-1.5-8-4 3-3.5-5-3.5 5-4-3z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 20h15" />
    </Icon>
  );
}

export function BriefcaseIcon(props) {
  return (
    <Icon {...props}>
      <rect x="3" y="8" width="18" height="12" rx="2" strokeLinecap="round" strokeLinejoin="round" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 8V6a2 2 0 012-2h4a2 2 0 012 2v2M3 13h18" />
    </Icon>
  );
}

export function TruckIcon(props) {
  return (
    <Icon {...props}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 7h11v9H3zM14 10h4l3 3v3h-7z" />
      <circle cx="7.5" cy="18" r="1.75" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="17.5" cy="18" r="1.75" strokeLinecap="round" strokeLinejoin="round" />
    </Icon>
  );
}

export function WrenchIcon(props) {
  return (
    <Icon {...props}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M14.5 6.5a4 4 0 00-5.4 4.6L4 16.2V20h3.8l5.1-5.1a4 4 0 004.6-5.4l-2.8 2.8-2-2z" />
    </Icon>
  );
}

export function ReceiptIcon(props) {
  return (
    <Icon {...props}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 3h14v18l-2.5-1.5L14 21l-2.5-1.5L9 21l-2.5-1.5L4 21V3z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 8h8M8 12h8M8 16h5" />
    </Icon>
  );
}

export function LockIcon(props) {
  return (
    <Icon {...props}>
      <rect x="5" y="11" width="14" height="9" rx="2" strokeLinecap="round" strokeLinejoin="round" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 11V7a4 4 0 018 0v4" />
    </Icon>
  );
}
