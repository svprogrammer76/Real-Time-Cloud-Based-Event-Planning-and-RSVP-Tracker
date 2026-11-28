import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { createClient } from '@supabase/supabase-js';
import '../app.js';

function AuthForm({ supabase }) {
  const [signup, setSignup] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setNotice('');
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      if (signup) {
        const { data: result, error: authError } = await supabase.auth.signUp({
          email: data.email,
          password: data.password,
          options: {
            data: { username: data.username, role: data.role },
            emailRedirectTo: window.location.origin,
          },
        });
        if (authError) throw authError;
        if (result.session) {
          window.dispatchEvent(new CustomEvent('gather:authenticated', { detail: { token: result.session.access_token, notify: true, action: 'Sign-up' } }));
        } else {
          setNotice('Check your email to confirm your account, then sign in.');
          setSignup(false);
        }
      } else {
        const { data: result, error: authError } = await supabase.auth.signInWithPassword({ email: data.email, password: data.password });
        if (authError) throw authError;
        window.dispatchEvent(new CustomEvent('gather:authenticated', { detail: { token: result.session.access_token, notify: true, action: 'Sign-in' } }));
      }
    } catch (cause) {
      setError(cause.message || 'Could not authenticate. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  return <form id="login" onSubmit={submit}>
    <h2>{signup ? 'Create an account' : 'Welcome back'}</h2>
    {signup && <>
      <input name="username" placeholder="Username" minLength="3" maxLength="50" pattern="[A-Za-z0-9_.-]+" title="Use letters, numbers, dots, underscores, or hyphens." required />
      <select name="role" defaultValue="ATTENDEE"><option>ATTENDEE</option><option>ORGANIZER</option></select>
    </>}
    <input name="email" placeholder="Email" type="email" required />
    <input name="password" placeholder="Password (10+ characters)" type="password" minLength={signup ? 10 : undefined} required />
    {error && <p className="error" role="alert">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    <button id="submit" disabled={busy}>{busy ? 'Please wait…' : signup ? 'Join Gather' : 'Sign in'}</button>
    <button type="button" id="toggle" className="link" onClick={() => { setSignup(!signup); setError(''); setNotice(''); }}>{signup ? 'Sign in instead' : 'Create account'}</button>
  </form>;
}

async function start() {
  const root = createRoot(document.getElementById('auth-root'));
  try {
    const response = await fetch('/config.json');
    const config = await response.json();
    if (!response.ok || !config.supabaseUrl || !config.supabaseAnonKey) throw new Error('Supabase Auth is not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY on the API service.');
    const supabase = createClient(config.supabaseUrl, config.supabaseAnonKey);
    supabase.auth.onAuthStateChange((event, session) => {
      if (session?.access_token) {
        localStorage.setItem('gather-token', session.access_token);
        if (event === 'INITIAL_SESSION') {
          window.dispatchEvent(new CustomEvent('gather:authenticated', { detail: { token: session.access_token, notify: false } }));
        }
      } else if (localStorage.getItem('gather-token')?.split('.').length === 3) {
        window.dispatchEvent(new Event('gather:session-ended'));
      }
    });
    window.addEventListener('gather:logout', () => { supabase.auth.signOut(); });
    root.render(<AuthForm supabase={supabase} />);
  } catch (cause) {
    root.render(<p className="error" role="alert">{cause.message}</p>);
  }
}

start();
