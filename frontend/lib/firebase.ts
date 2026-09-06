// Firebase config values (apiKey, authDomain, etc.) are public identifiers,
// not secrets — safe to embed in a client bundle; Firebase's actual
// security boundary is server-side (Auth rules, ID token verification in
// backend/app/auth.py), not keeping this object hidden. Copy these from
// Firebase Console -> Project settings -> your web app -> SDK setup.
import { initializeApp, getApps, type FirebaseOptions } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig: FirebaseOptions = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

// Guarded to only initialize in the browser: Next.js prerenders every
// page (including "use client" ones) on the server too, and initializeApp
// throws immediately on an invalid/missing apiKey rather than failing
// lazily — which would break the production build in any environment
// where env vars aren't wired up yet (this sandbox included). Real usage
// only ever happens client-side (useEffect/event handlers in lib/auth.ts),
// never during server rendering, so deferring is safe.
// The `getApps().length` guard is for dev-mode hot reload, which re-runs
// this module without a full page reload and would otherwise throw
// "app already exists".
export const firebaseApp = typeof window !== "undefined" ? (getApps().length ? getApps()[0]! : initializeApp(firebaseConfig)) : null;

export const firebaseAuth = firebaseApp ? getAuth(firebaseApp) : (null as unknown as ReturnType<typeof getAuth>);
