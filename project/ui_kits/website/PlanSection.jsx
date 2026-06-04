/* afc.wallet UI Kit — PlanSection Component */

function PlanSection({ onSelect }) {
  const sectionStyle = {
    background: '#000', padding: '88px 32px',
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
    color: '#fff',
  };

  const subStyle = {
    fontFamily: kitStyles.fontBody, fontSize: 18, fontWeight: 400,
    lineHeight: 1.56, color: 'rgba(255,255,255,0.72)',
    marginTop: 12,
  };

  const gridStyle = {
    display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
    gap: 16,
  };

  const plans = [
    { name: 'Standard', price: 'Free', featured: false, features: ['Up to 5 currency accounts', 'Instant spending notifications', 'Free card delivery'] },
    { name: 'Plus', price: '$3.99/mo', featured: false, features: ['Up to 15 currency accounts', 'Priority customer support', 'Purchase protection'] },
    { name: 'Premium', price: '$9.99/mo', featured: true, badge: 'Most popular', features: ['Unlimited currency accounts', 'Airport lounge access', 'Travel medical insurance'] },
    { name: 'Metal', price: '$16.99/mo', featured: false, features: ['Exclusive metal card', 'Up to 1% cashback', 'Concierge service'] },
  ];

  return React.createElement('section', { style: sectionStyle },
    React.createElement('div', { style: innerStyle },
      React.createElement('div', { style: headerStyle },
        React.createElement('h2', { style: h2Style }, 'Choose your plan'),
        React.createElement('p', { style: subStyle }, 'Find the perfect fit for the way you manage money.'),
      ),
      React.createElement('div', { style: gridStyle },
        plans.map((plan, i) =>
          React.createElement(KitCard, {
            key: i,
            variant: plan.featured ? 'featured' : 'dark',
            style: { gap: 16, position: 'relative' },
          },
            plan.badge && React.createElement(KitBadge, {
              variant: plan.featured ? 'tag' : 'feature',
            }, plan.badge),

            React.createElement('h3', {
              style: {
                fontFamily: kitStyles.fontDisplay, fontSize: 32, fontWeight: 500,
                lineHeight: 1.19, letterSpacing: '-0.32px',
                color: plan.featured ? '#fff' : '#fff',
              },
            }, plan.name),

            React.createElement('div', {
              style: {
                fontFamily: kitStyles.fontDisplay, fontSize: 24, fontWeight: 500,
                lineHeight: 1.33,
                color: plan.featured ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.72)',
              },
            }, plan.price),

            React.createElement('div', {
              style: {
                height: 1,
                background: plan.featured ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.12)',
                margin: '8px 0',
              },
            }),

            React.createElement('ul', {
              style: {
                listStyle: 'none', padding: 0, margin: 0,
                display: 'flex', flexDirection: 'column', gap: 10,
              },
            },
              plan.features.map((f, j) =>
                React.createElement('li', {
                  key: j,
                  style: {
                    fontFamily: kitStyles.fontBody, fontSize: 14, fontWeight: 400,
                    lineHeight: 1.43,
                    color: plan.featured ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.72)',
                    display: 'flex', alignItems: 'center', gap: 8,
                  },
                },
                  React.createElement('span', {
                    style: {
                      width: 16, height: 16, borderRadius: 8, flexShrink: 0,
                      background: plan.featured ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.08)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 10, color: '#fff',
                    },
                  }, '✓'),
                  f,
                )
              )
            ),

            React.createElement('div', { style: { marginTop: 'auto', paddingTop: 8 } },
              React.createElement(KitButton, {
                variant: plan.featured ? 'primary' : 'outlineDark',
                onClick: () => onSelect && onSelect(plan.name),
                style: { width: '100%', justifyContent: 'center' },
              }, 'Choose ' + plan.name)
            ),
          )
        )
      ),
    ),
  );
}

Object.assign(window, { PlanSection });
