/* afc.wallet UI Kit — Shared Styles & Utilities */

const kitStyles = {
  /* Reset helpers */
  reset: {
    margin: 0, padding: 0, boxSizing: 'border-box',
  },

  /* Color tokens */
  colors: {
    primary: '#494fdf',
    primaryBright: '#4f55f1',
    primaryDeep: '#3a40c4',
    onPrimary: '#ffffff',
    ink: '#191c1f',
    body: '#1f2226',
    charcoal: '#3a3d40',
    mute: '#505a63',
    ash: '#5c5e60',
    stone: '#8d969e',
    faint: '#c9c9cd',
    onDark: '#ffffff',
    onDarkMute: 'rgba(255,255,255,0.72)',
    canvasLight: '#ffffff',
    canvasDark: '#000000',
    surfaceSoft: '#f4f4f4',
    surfaceCard: '#ffffff',
    surfaceDeep: '#0a0a0a',
    surfaceElevated: '#16181a',
    hairlineLight: '#e2e2e7',
    hairlineDark: 'rgba(255,255,255,0.12)',
    dividerSoft: 'rgba(255,255,255,0.06)',
    accentTeal: '#00a87e',
    accentBlueLink: '#376cd5',
    accentPink: '#e61e49',
    accentWarning: '#ec7e00',
    accentDanger: '#e23b4a',
  },

  /* Font stacks */
  fontDisplay: "'Plus Jakarta Sans', 'Inter', system-ui, sans-serif",
  fontBody: "'Inter', system-ui, sans-serif",

  /* Radius tokens */
  rounded: { none: 0, sm: 8, md: 12, lg: 20, xl: 28, full: 9999 },

  /* Spacing tokens */
  space: { xxs: 4, xs: 6, sm: 8, md: 14, lg: 16, xl: 24, xxl: 32, xxxl: 48, block: 80, section: 88, band: 120 },
};

/* Button component */
function KitButton({ variant = 'primary', size = 'md', children, onClick, style: extra }) {
  const base = {
    border: 'none', cursor: 'pointer', display: 'inline-flex',
    alignItems: 'center', justifyContent: 'center',
    fontFamily: kitStyles.fontBody,
    fontSize: size === 'sm' ? 14 : size === 'lg' ? 20 : 16,
    fontWeight: size === 'lg' ? 500 : 600,
    letterSpacing: size === 'lg' ? 0 : '0.24px',
    lineHeight: size === 'sm' ? '1.43' : '1.5',
    height: size === 'sm' ? 36 : 48,
    padding: size === 'sm' ? '8px 16px' : '14px 28px',
    borderRadius: 9999,
    transition: 'background 0.2s ease, opacity 0.2s ease',
    ...(size === 'lg' && { fontFamily: kitStyles.fontDisplay }),
  };

  const variants = {
    primary: { background: '#fff', color: '#000' },
    dark: { background: '#000', color: '#fff' },
    soft: { background: '#f4f4f4', color: '#191c1f' },
    outlineLight: { background: '#fff', color: '#191c1f', border: '1px solid #191c1f', padding: '13px 27px' },
    outlineDark: { background: 'transparent', color: '#fff', border: '1px solid #fff', padding: '13px 27px' },
    accent: { background: '#494fdf', color: '#fff' },
  };

  return React.createElement('button', {
    style: { ...base, ...variants[variant], ...extra },
    onClick,
    onMouseEnter: (e) => { e.currentTarget.style.opacity = '0.85'; },
    onMouseLeave: (e) => { e.currentTarget.style.opacity = '1'; },
  }, children);
}

/* Badge component */
function KitBadge({ variant = 'tag', children }) {
  const base = {
    display: 'inline-flex', alignItems: 'center',
    fontFamily: kitStyles.fontBody, fontSize: 13, fontWeight: 400,
    lineHeight: '1.4', borderRadius: 9999, padding: '4px 12px',
  };
  const variants = {
    tag: { background: '#f4f4f4', color: '#191c1f' },
    feature: { background: '#494fdf', color: '#fff' },
  };
  return React.createElement('span', { style: { ...base, ...variants[variant] } }, children);
}

/* Card component */
function KitCard({ variant = 'light', children, style: extra }) {
  const base = {
    padding: 32, borderRadius: 20,
    display: 'flex', flexDirection: 'column',
  };
  const variants = {
    light: { background: '#fff', border: '1px solid #e2e2e7', color: '#191c1f' },
    dark: { background: '#16181a', color: '#fff' },
    featured: { background: '#494fdf', color: '#fff' },
  };
  return React.createElement('div', { style: { ...base, ...variants[variant], ...extra } }, children);
}

/* Export to window */
Object.assign(window, { kitStyles, KitButton, KitBadge, KitCard });
