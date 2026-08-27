// Lightweight client-side demo gate. NOT real authentication — it only decides
// whether to show the login screen or the app for a polished demo. The single
// demo account below is intentionally hardcoded; there is no backend check.
const DEMO_EMAIL = 'demo@add.ai';
const DEMO_PASSWORD = 'demo1234';
const KEY = 'add_demo_auth';

export const DEMO_CREDENTIALS = { email: DEMO_EMAIL, password: DEMO_PASSWORD };

export function isAuthenticated(): boolean {
  try {
    return localStorage.getItem(KEY) === '1';
  } catch {
    return false;
  }
}

/** Returns true and persists the session on a correct demo login. */
export function login(email: string, password: string): boolean {
  const ok =
    email.trim().toLowerCase() === DEMO_EMAIL && password === DEMO_PASSWORD;
  if (ok) {
    try { localStorage.setItem(KEY, '1'); } catch { /* ignore */ }
  }
  return ok;
}

export function logout(): void {
  try { localStorage.removeItem(KEY); } catch { /* ignore */ }
}
