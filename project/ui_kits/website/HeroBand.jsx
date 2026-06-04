/* afc.wallet UI Kit — HeroBand Component */

function HeroBand({ headline, subline, primaryCta, secondaryCta, onPrimary, onSecondary }) {
  const bandStyle = {
    background: '#000', padding: '120px 32px 100px',
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    textAlign: 'center', position: 'relative', overflow: 'hidden',
  };

  const h1Style = {
    fontFamily: kitStyles.fontDisplay, fontSize: 80, fontWeight: 500,
    lineHeight: 1.0, letterSpacing: '-0.8px',
    color: '#fff', maxWidth: 900, margin: '0 auto',
    textWrap: 'balance',
  };

  const pStyle = {
    fontFamily: kitStyles.fontBody, fontSize: 18, fontWeight: 400,
    lineHeight: 1.56, letterSpacing: '-0.09px',
    color: 'rgba(255,255,255,0.72)', maxWidth: 520,
    margin: '24px auto 0',
  };

  const actionsStyle = {
    display: 'flex', gap: 12, justifyContent: 'center',
    marginTop: 36,
  };

  /* Decorative gradient glow */
  const glowStyle = {
    position: 'absolute', bottom: -120, left: '50%', transform: 'translateX(-50%)',
    width: 600, height: 300,
    background: 'radial-gradient(ellipse, rgba(73,79,223,0.15) 0%, transparent 70%)',
    pointerEvents: 'none',
  };

  return React.createElement('section', { style: bandStyle },
    React.createElement('div', { style: glowStyle }),
    React.createElement('h1', { style: h1Style }, headline || 'Your money, simplified'),
    React.createElement('p', { style: pStyle }, subline || 'One account for spending, saving, investing, and managing your finances across borders.'),
    React.createElement('div', { style: actionsStyle },
      React.createElement(KitButton, { variant: 'primary', size: 'lg', onClick: onPrimary }, primaryCta || 'Get started'),
      secondaryCta && React.createElement(KitButton, { variant: 'outlineDark', onClick: onSecondary }, secondaryCta),
    ),
  );
}

Object.assign(window, { HeroBand });
