/* afc.wallet UI Kit — NavBar Component */

function NavBar({ currentPage = 'home', onNavigate }) {
  const [menuOpen, setMenuOpen] = React.useState(false);

  const navStyle = {
    height: 64, background: '#000',
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '0 32px',
    borderBottom: '1px solid rgba(255,255,255,0.12)',
    position: 'sticky', top: 0, zIndex: 100,
  };

  const logoStyle = {
    fontFamily: kitStyles.fontDisplay, fontSize: 20, fontWeight: 500,
    color: '#fff', letterSpacing: '-0.4px', cursor: 'pointer',
  };

  const linksStyle = {
    display: 'flex', gap: 28, alignItems: 'center',
  };

  const linkStyle = (active) => ({
    fontFamily: kitStyles.fontBody, fontSize: 16, fontWeight: 600,
    color: active ? '#fff' : 'rgba(255,255,255,0.72)',
    textDecoration: 'none', letterSpacing: '0.24px',
    cursor: 'pointer', transition: 'color 0.2s ease',
    background: 'none', border: 'none', padding: 0,
  });

  const rightStyle = {
    display: 'flex', gap: 12, alignItems: 'center',
  };

  const pages = [
    { id: 'home', label: 'Personal' },
    { id: 'business', label: 'Business' },
    { id: 'company', label: 'Company' },
  ];

  return React.createElement('nav', { style: navStyle },
    React.createElement('span', {
      style: logoStyle,
      onClick: () => onNavigate && onNavigate('home'),
    }, 'afc.wallet'),

    React.createElement('div', { style: linksStyle },
      pages.map(p =>
        React.createElement('button', {
          key: p.id,
          style: linkStyle(currentPage === p.id),
          onClick: () => onNavigate && onNavigate(p.id),
          onMouseEnter: (e) => { if (currentPage !== p.id) e.currentTarget.style.color = '#fff'; },
          onMouseLeave: (e) => { if (currentPage !== p.id) e.currentTarget.style.color = 'rgba(255,255,255,0.72)'; },
        }, p.label)
      )
    ),

    React.createElement('div', { style: rightStyle },
      React.createElement('button', {
        style: {
          ...linkStyle(false), fontSize: 14,
        },
        onClick: () => onNavigate && onNavigate('login'),
      }, 'Log in'),
      React.createElement(KitButton, {
        variant: 'primary', size: 'sm',
        onClick: () => onNavigate && onNavigate('signup'),
      }, 'Get started')
    )
  );
}

Object.assign(window, { NavBar });
