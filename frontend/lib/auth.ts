// Mock auth only — no real backend identity exists yet (Firebase Auth is
// still a later docs/plan.md §4 item; the whole backend runs on one seeded
// demo user, see backend/app/seed.py). This just gates the UI behind a
// login screen and gives the frontend a "logged in" concept to build a
// profile/log-out flow around, so there's an actual landing/login/profile
// experience rather than none at all — it does not protect any data.
const STORAGE_KEY = "smw-logged-in";

export function isLoggedIn(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

export function logIn(): void {
  try {
    localStorage.setItem(STORAGE_KEY, "true");
  } catch {
    // ignore — private-browsing contexts can throw on localStorage writes
  }
}

export function logOut(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}
