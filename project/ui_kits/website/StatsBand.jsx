/* afc.wallet UI Kit — StatsBand & SignupModal Components */

function StatsBand() {
  const bandStyle = {
    background: '#000', padding: '64px 32px',
    borderTop: '1px solid rgba(255,255,255,0.06)',
    borderBottom: '1px solid rgba(255,255,255,0.06)',
  };

  const innerStyle = {
    maxWidth: 1200, margin: '0 auto',
    display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 32,
    textAlign: 'center',
  };

  const numStyle = {
    fontFamily: kitStyles.fontDisplay, fontSize: 48, fontWeight: 500,
    lineHeight: 1.0, letterSpacing: '-0.48px', color: '#fff',
  };

  const labelStyle = {
    fontFamily: kitStyles.fontBody, fontSize: 14, fontWeight: 400,
    lineHeight: 1.43, color: 'rgba(255,255,255,0.72)', marginTop: 8,
  };

  const stats = [
    { num: '70M+', label: 'Customers worldwide' },
    { num: '150+', label: 'Countries supported' },
    { num: '30+', label: 'Currencies available' },
    { num: '$15B+', label: 'Transactions monthly' },
  ];

  return React.createElement('section', { style: bandStyle },
    React.createElement('div', { style: innerStyle },
      stats.map((s, i) =>
        React.createElement('div', { key: i },
          React.createElement('div', { style: numStyle }, s.num),
          React.createElement('div', { style: labelStyle }, s.label),
        )
      )
    ),
  );
}

function SignupModal({ open, onClose }) {
  if (!open) return null;

  const overlayStyle = {
    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
    background: 'rgba(0,0,0,0.7)', display: 'flex',
    alignItems: 'center', justifyContent: 'center', zIndex: 200,
    backdropFilter: 'blur(4px)',
  };

  const modalStyle = {
    background: '#fff', borderRadius: 20, padding: 40,
    width: 420, maxWidth: '90vw',
    display: 'flex', flexDirection: 'column', gap: 20,
  };

  const titleStyle = {
    fontFamily: kitStyles.fontDisplay, fontSize: 32, fontWeight: 500,
    lineHeight: 1.19, letterSpacing: '-0.32px', color: '#191c1f',
  };

  const descStyle = {
    fontFamily: kitStyles.fontBody, fontSize: 16, fontWeight: 400,
    lineHeight: 1.5, letterSpacing: '0.24px', color: '#505a63',
  };

  const inputStyle = {
    width: '100%', height: 56, background: '#fff', color: '#191c1f',
    border: '1px solid #e2e2e7', borderRadius: 12,
    padding: '14px 16px',
    fontFamily: kitStyles.fontBody, fontSize: 16, fontWeight: 400,
    letterSpacing: '0.24px', lineHeight: 1.5, outline: 'none',
    boxSizing: 'border-box',
  };

  const closeStyle = {
    position: 'absolute', top: 16, right: 16,
    background: 'none', border: 'none', cursor: 'pointer',
    fontFamily: kitStyles.fontBody, fontSize: 20, color: '#8d969e',
    width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center',
  };

  const [email, setEmail] = React.useState('');
  const [submitted, setSubmitted] = React.useState(false);

  return React.createElement('div', { style: overlayStyle, onClick: (e) => { if (e.target === e.currentTarget) onClose(); } },
    React.createElement('div', { style: { ...modalStyle, position: 'relative' } },
      React.createElement('button', { style: closeStyle, onClick: onClose }, '×'),
      !submitted ? React.createElement(React.Fragment, null,
        React.createElement('div', { style: titleStyle }, 'Create account'),
        React.createElement('div', { style: descStyle }, 'Enter your email to get started. It takes less than 2 minutes.'),
        React.createElement('input', {
          style: inputStyle, type: 'email', placeholder: 'Enter your email',
          value: email, onChange: (e) => setEmail(e.target.value),
          onFocus: (e) => { e.target.style.borderColor = '#494fdf'; },
          onBlur: (e) => { e.target.style.borderColor = '#e2e2e7'; },
        }),
        React.createElement('input', {
          style: inputStyle, type: 'tel', placeholder: 'Phone number',
        }),
        React.createElement(KitButton, {
          variant: 'dark',
          onClick: () => setSubmitted(true),
          style: { width: '100%', justifyContent: 'center' },
        }, 'Continue'),
        React.createElement('div', {
          style: { fontFamily: kitStyles.fontBody, fontSize: 13, color: '#8d969e', lineHeight: 1.4, textAlign: 'center' },
        }, 'By continuing, you agree to our Terms of Service and Privacy Policy.'),
      ) : React.createElement(React.Fragment, null,
        React.createElement('div', { style: { ...titleStyle, textAlign: 'center' } }, 'Check your email'),
        React.createElement('div', { style: { ...descStyle, textAlign: 'center' } },
          'We sent a verification link to ', React.createElement('strong', null, email || 'your inbox'), '. Click the link to continue setting up your account.'
        ),
        React.createElement(KitButton, {
          variant: 'soft',
          onClick: () => { setSubmitted(false); setEmail(''); onClose(); },
          style: { width: '100%', justifyContent: 'center' },
        }, 'Done'),
      ),
    ),
  );
}

Object.assign(window, { StatsBand, SignupModal });
