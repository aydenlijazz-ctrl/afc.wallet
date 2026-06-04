/* afc.wallet UI Kit — FeatureGrid Component */

function FeatureGrid({ title, subtitle, features }) {
  const sectionStyle = {
    background: '#fff', padding: '88px 32px',
  };

  const innerStyle = {
    maxWidth: 1200, margin: '0 auto',
  };

  const headerStyle = {
    textAlign: 'center', marginBottom: 48,
  };

  const h2Style = {
    fontFamily: kitStyles.fontDisplay, fontSize: 48, fontWeight: 500,
    lineHeight: 1.21, letterSpacing: '-0.48px',
    color: '#191c1f',
  };

  const subStyle = {
    fontFamily: kitStyles.fontBody, fontSize: 18, fontWeight: 400,
    lineHeight: 1.56, letterSpacing: '-0.09px',
    color: '#505a63', marginTop: 12, maxWidth: 560, margin: '12px auto 0',
  };

  const gridStyle = {
    display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)',
    gap: 20,
  };

  const iconColors = ['#00a87e', '#007bc2', '#e61e49', '#494fdf', '#ec7e00', '#428619'];

  const defaultFeatures = [
    { title: 'Global transfers', desc: 'Send money to 150+ countries with the real exchange rate.' },
    { title: 'Multi-currency', desc: 'Hold and exchange 30+ currencies in your account instantly.' },
    { title: 'Smart budgeting', desc: 'Track spending with automatic categorisation and insights.' },
    { title: 'Instant notifications', desc: 'Real-time alerts for every transaction across all your cards.' },
    { title: 'Virtual cards', desc: 'Create disposable virtual cards for safer online shopping.' },
    { title: 'Crypto & stocks', desc: 'Invest from as little as $1 in crypto and fractional shares.' },
  ];

  const items = features || defaultFeatures;

  return React.createElement('section', { style: sectionStyle },
    React.createElement('div', { style: innerStyle },
      React.createElement('div', { style: headerStyle },
        React.createElement('h2', { style: h2Style }, title || 'Everything you need'),
        subtitle && React.createElement('p', { style: subStyle }, subtitle),
      ),
      React.createElement('div', { style: gridStyle },
        items.map((f, i) =>
          React.createElement(KitCard, { key: i, variant: 'light', style: { gap: 12 } },
            React.createElement('div', {
              style: {
                width: 40, height: 40, borderRadius: 10,
                background: iconColors[i % iconColors.length] + '14',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                marginBottom: 4,
              },
            },
              React.createElement('div', {
                style: {
                  width: 20, height: 20, borderRadius: 6,
                  background: iconColors[i % iconColors.length],
                },
              })
            ),
            React.createElement('h3', {
              style: {
                fontFamily: kitStyles.fontDisplay, fontSize: 20, fontWeight: 500,
                lineHeight: 1.4, color: '#191c1f',
              },
            }, f.title),
            React.createElement('p', {
              style: {
                fontFamily: kitStyles.fontBody, fontSize: 16, fontWeight: 400,
                lineHeight: 1.5, letterSpacing: '0.24px', color: '#505a63',
              },
            }, f.desc),
          )
        )
      ),
    ),
  );
}

Object.assign(window, { FeatureGrid });
