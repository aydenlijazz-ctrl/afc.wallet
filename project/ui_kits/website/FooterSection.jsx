/* afc.wallet UI Kit — DownloadBand & FooterSection Components */

function DownloadBand() {
  const sectionStyle = {
    background: '#fff', padding: '88px 32px',
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    textAlign: 'center',
  };

  const h2Style = {
    fontFamily: kitStyles.fontDisplay, fontSize: 48, fontWeight: 500,
    lineHeight: 1.21, letterSpacing: '-0.48px',
    color: '#191c1f',
  };

  const pStyle = {
    fontFamily: kitStyles.fontBody, fontSize: 18, fontWeight: 400,
    lineHeight: 1.56, color: '#505a63', marginTop: 12, maxWidth: 480,
  };

  const tilesStyle = {
    display: 'flex', gap: 12, marginTop: 32,
  };

  const tileStyle = {
    display: 'flex', alignItems: 'center', gap: 10,
    background: '#f4f4f4', borderRadius: 12,
    padding: '12px 20px', height: 56, cursor: 'pointer',
    transition: 'background 0.2s ease',
  };

  const tileTextStyle = {
    display: 'flex', flexDirection: 'column',
  };

  const tileSmall = {
    fontFamily: kitStyles.fontBody, fontSize: 11, fontWeight: 400, color: '#505a63', lineHeight: 1.2,
  };

  const tileLarge = {
    fontFamily: kitStyles.fontBody, fontSize: 16, fontWeight: 600, color: '#191c1f', lineHeight: 1.3, letterSpacing: '0.16px',
  };

  return React.createElement('section', { style: sectionStyle },
    React.createElement('h2', { style: h2Style }, 'Start today'),
    React.createElement('p', { style: pStyle }, 'Download the app and open your account in minutes. Available on iOS and Android.'),
    React.createElement('div', { style: tilesStyle },
      React.createElement('div', { style: tileStyle },
        React.createElement('div', { style: { width: 28, height: 28, borderRadius: 6, background: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center' } },
          React.createElement('span', { style: { color: '#fff', fontSize: 16 } }, '⬡')
        ),
        React.createElement('div', { style: tileTextStyle },
          React.createElement('span', { style: tileSmall }, 'Download on the'),
          React.createElement('span', { style: tileLarge }, 'App Store'),
        ),
      ),
      React.createElement('div', { style: tileStyle },
        React.createElement('div', { style: { width: 28, height: 28, borderRadius: 6, background: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center' } },
          React.createElement('span', { style: { color: '#fff', fontSize: 14 } }, '▶')
        ),
        React.createElement('div', { style: tileTextStyle },
          React.createElement('span', { style: tileSmall }, 'Get it on'),
          React.createElement('span', { style: tileLarge }, 'Google Play'),
        ),
      ),
    ),
  );
}

function FooterSection() {
  const footerStyle = {
    background: '#000', padding: '80px 32px 32px',
  };

  const innerStyle = {
    maxWidth: 1200, margin: '0 auto',
  };

  const topStyle = {
    display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
    marginBottom: 48,
  };

  const logoStyle = {
    fontFamily: kitStyles.fontDisplay, fontSize: 24, fontWeight: 500,
    color: '#fff', letterSpacing: '-0.48px',
  };

  const gridStyle = {
    display: 'grid', gridTemplateColumns: 'repeat(4, auto)',
    gap: 48,
  };

  const colHeadStyle = {
    fontFamily: kitStyles.fontBody, fontSize: 14, fontWeight: 600,
    color: '#fff', marginBottom: 16, lineHeight: 1.43,
  };

  const colLinkStyle = {
    display: 'block', fontFamily: kitStyles.fontBody, fontSize: 14, fontWeight: 400,
    color: 'rgba(255,255,255,0.72)', textDecoration: 'none',
    lineHeight: 1.43, marginBottom: 10, cursor: 'pointer',
    transition: 'color 0.15s ease',
  };

  const bottomStyle = {
    borderTop: '1px solid rgba(255,255,255,0.06)',
    paddingTop: 24, marginTop: 48,
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  };

  const disclosureStyle = {
    fontFamily: kitStyles.fontBody, fontSize: 13, fontWeight: 400,
    color: 'rgba(255,255,255,0.5)', lineHeight: 1.4,
  };

  const columns = [
    { title: 'Products', links: ['Accounts', 'Cards', 'Transfers', 'Crypto', 'Insurance'] },
    { title: 'Company', links: ['About', 'Careers', 'Press', 'Blog', 'Partners'] },
    { title: 'Support', links: ['Help centre', 'Community', 'Contact us', 'Security'] },
    { title: 'Legal', links: ['Privacy policy', 'Terms of service', 'Cookie policy', 'Licenses'] },
  ];

  return React.createElement('footer', { style: footerStyle },
    React.createElement('div', { style: innerStyle },
      React.createElement('div', { style: topStyle },
        React.createElement('span', { style: logoStyle }, 'afc.wallet'),
        React.createElement('div', { style: gridStyle },
          columns.map((col, i) =>
            React.createElement('div', { key: i },
              React.createElement('div', { style: colHeadStyle }, col.title),
              col.links.map((link, j) =>
                React.createElement('a', {
                  key: j, href: '#', style: colLinkStyle,
                  onMouseEnter: (e) => { e.currentTarget.style.color = '#fff'; },
                  onMouseLeave: (e) => { e.currentTarget.style.color = 'rgba(255,255,255,0.72)'; },
                }, link)
              )
            )
          )
        ),
      ),
      React.createElement('div', { style: bottomStyle },
        React.createElement('span', { style: disclosureStyle }, '© 2026 afc.wallet. All rights reserved.'),
        React.createElement('span', { style: disclosureStyle }, 'afc.wallet Ltd is authorised and regulated.'),
      ),
    ),
  );
}

Object.assign(window, { DownloadBand, FooterSection });
