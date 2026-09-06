// Real Firebase Authentication (docs/plan.md §4 — no longer deferred now
// that the GCP billing block on this project is resolved). Email/password
// only, the simplest provider Firebase offers and the one the existing
// /login form already matches; every request lib/api.ts makes attaches the
// current user's ID token as `Authorization: Bearer <token>`, verified
// server-side by backend/app/auth.py — this file owns sign-up/sign-in/
// sign-out and getting that token, nothing about authorization decisions
// (those live entirely on the backend).
import {
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut,
  type User,
} from "firebase/auth";
import { firebaseAuth } from "./firebase";

export async function signUp(email: string, password: string): Promise<void> {
  await createUserWithEmailAndPassword(firebaseAuth, email, password);
}

export async function signIn(email: string, password: string): Promise<void> {
  await signInWithEmailAndPassword(firebaseAuth, email, password);
}

export async function logOut(): Promise<void> {
  await signOut(firebaseAuth);
}

// Firebase restores a signed-in session asynchronously on page load (it's
// reading from IndexedDB), so `firebaseAuth.currentUser` can briefly be
// null even for someone who's genuinely logged in. Callers that need to
// know "is anyone logged in, and who" (AuthGate, the API client's token
// attachment) should wait for the first onAuthStateChanged firing rather
// than reading currentUser directly at import time.
let authReadyPromise: Promise<User | null> | null = null;

export function waitForAuthReady(): Promise<User | null> {
  if (!authReadyPromise) {
    authReadyPromise = new Promise((resolve) => {
      const unsubscribe = onAuthStateChanged(firebaseAuth, (user) => {
        unsubscribe();
        resolve(user);
      });
    });
  }
  return authReadyPromise;
}

export function subscribeToAuthState(callback: (user: User | null) => void): () => void {
  return onAuthStateChanged(firebaseAuth, callback);
}

// The one thing lib/api.ts needs per request — null when nobody's signed
// in, in which case the request goes out with no Authorization header and
// the backend's get_current_user_id rejects it with 401.
export async function getIdToken(): Promise<string | null> {
  const user = firebaseAuth.currentUser ?? (await waitForAuthReady());
  if (!user) return null;
  return user.getIdToken();
}
