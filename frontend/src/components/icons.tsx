import type { ReactNode, SVGProps } from 'react'

/* A small hand-drawn icon set (1.5px strokes) so the interface does not look like a stock kit. */

type IconProps = SVGProps<SVGSVGElement> & { size?: number }

function Icon({ size = 16, children, ...props }: IconProps & { children: ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}
         strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      {children}
    </svg>
  )
}

export const IconSearch = (p: IconProps) => <Icon {...p}><circle cx="11" cy="11" r="6.5" /><path d="m20 20-4.2-4.2" /></Icon>
export const IconSun = (p: IconProps) => (
  <Icon {...p}><circle cx="12" cy="12" r="4" /><path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4" /></Icon>
)
export const IconMoon = (p: IconProps) => <Icon {...p}><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z" /></Icon>
export const IconSpark = (p: IconProps) => (
  <Icon {...p}><path d="M12 3c.6 4.3 2.7 6.4 7 7-4.3.6-6.4 2.7-7 7-.6-4.3-2.7-6.4-7-7 4.3-.6 6.4-2.7 7-7Z" /><path d="M19 17c.2 1.3.7 1.8 2 2-1.3.2-1.8.7-2 2-.2-1.3-.7-1.8-2-2 1.3-.2 1.8-.7 2-2Z" /></Icon>
)
export const IconArrowRight = (p: IconProps) => <Icon {...p}><path d="M5 12h14M13 6l6 6-6 6" /></Icon>
export const IconArrowUpRight = (p: IconProps) => <Icon {...p}><path d="M7 17 17 7M8 7h9v9" /></Icon>
export const IconDownload = (p: IconProps) => <Icon {...p}><path d="M12 4v11M7 10l5 5 5-5M5 20h14" /></Icon>
export const IconLink = (p: IconProps) => <Icon {...p}><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" /><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" /></Icon>
export const IconReset = (p: IconProps) => <Icon {...p}><path d="M4 12a8 8 0 1 0 2.4-5.7L4 8.5" /><path d="M4 4v4.5h4.5" /></Icon>
export const IconInfo = (p: IconProps) => <Icon {...p}><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></Icon>
export const IconAlert = (p: IconProps) => <Icon {...p}><path d="M12 3 2.5 20h19L12 3Z" /><path d="M12 10v4M12 17h.01" /></Icon>
export const IconCheck = (p: IconProps) => <Icon {...p}><path d="m5 12.5 4.5 4.5L19 7.5" /></Icon>
export const IconClose = (p: IconProps) => <Icon {...p}><path d="M6 6l12 12M18 6 6 18" /></Icon>
export const IconCommand = (p: IconProps) => (
  <Icon {...p}><path d="M9 9V6.5A2.5 2.5 0 1 0 6.5 9H9Zm0 0h6m-6 0v6m6-6V6.5A2.5 2.5 0 1 1 17.5 9H15Zm0 0v6m0 0h-6m6 0v2.5a2.5 2.5 0 1 0 2.5-2.5H15ZM9 15v2.5A2.5 2.5 0 1 1 6.5 15H9Z" /></Icon>
)
export const IconChevron = (p: IconProps) => <Icon {...p}><path d="m9 6 6 6-6 6" /></Icon>
export const IconSend = (p: IconProps) => <Icon {...p}><path d="M4 12 20 4l-6 16-3-7-7-1Z" /></Icon>
export const IconGlobe = (p: IconProps) => (
  <Icon {...p}><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3Z" /></Icon>
)
export const IconLayers = (p: IconProps) => <Icon {...p}><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m3 13 9 5 9-5" /></Icon>
export const IconCube = (p: IconProps) => <Icon {...p}><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z" /><path d="m4 7.5 8 4.5 8-4.5M12 12v9" /></Icon>
export const IconPlane = (p: IconProps) => <Icon {...p}><path d="M3 17 12 7l9 10" /><path d="M3 17h18" /></Icon>
export const IconPlay = (p: IconProps) => <Icon {...p}><path d="M8 5v14l11-7L8 5Z" /></Icon>
export const IconStop = (p: IconProps) => <Icon {...p}><rect x="6" y="6" width="12" height="12" rx="2" /></Icon>
export const IconDoc = (p: IconProps) => <Icon {...p}><path d="M7 3h7l5 5v13H7V3Z" /><path d="M14 3v5h5M10 13h6M10 17h6" /></Icon>

export const NavIcons = {
  overview: (p: IconProps) => <Icon {...p}><circle cx="12" cy="12" r="8" /><path d="M12 4v4M12 16v4M4 12h4M16 12h4" /><circle cx="12" cy="12" r="1.5" /></Icon>,
  valuation: (p: IconProps) => <Icon {...p}><path d="M4 19V9M10 19V5M16 19v-7M22 19H2" /></Icon>,
  expectations: (p: IconProps) => <Icon {...p}><path d="M3 17c3-6 6-9 9-9s6 3 9 9" /><path d="M3 12h18" strokeDasharray="2 3" /></Icon>,
  comps: (p: IconProps) => <Icon {...p}><circle cx="6" cy="12" r="2.5" /><circle cx="18" cy="6" r="2.5" /><circle cx="18" cy="18" r="2.5" /><path d="m8.2 11 7.6-4M8.2 13l7.6 4" /></Icon>,
  mna: (p: IconProps) => <Icon {...p}><circle cx="9" cy="12" r="5" /><circle cx="15" cy="12" r="5" /></Icon>,
  lbo: (p: IconProps) => <Icon {...p}><path d="M4 20h16M6 20V10l6-5 6 5v10" /><path d="M10 20v-5h4v5" /></Icon>,
  risk: (p: IconProps) => <Icon {...p}><path d="M3 12h3l2-6 4 12 3-9 2 3h4" /></Icon>,
  data: (p: IconProps) => <Icon {...p}><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3" /></Icon>,
  report: (p: IconProps) => <Icon {...p}><path d="M7 3h7l5 5v13H7V3Z" /><path d="M14 3v5h5M10 13h6M10 17h4" /></Icon>,
}
