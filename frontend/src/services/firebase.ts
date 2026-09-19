import { getApp, getApps, initializeApp } from "firebase/app";
import {
  browserLocalPersistence,
  getAuth,
  setPersistence,
  type Auth,
} from "firebase/auth";

const requiredConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

const missingConfig = Object.entries(requiredConfig)
  .filter(([, value]) => !value || value.startsWith("replace-with-"))
  .map(([key]) => key);

let authPromise: Promise<Auth> | undefined;

export function getFirebaseAuth(): Promise<Auth> {
  if (missingConfig.length > 0) {
    return Promise.reject(
      new Error("Firebase Authentication is not configured for this environment."),
    );
  }

  authPromise ??= (async () => {
    const app = getApps().length > 0 ? getApp() : initializeApp(requiredConfig);
    const authInstance = getAuth(app);
    await setPersistence(authInstance, browserLocalPersistence);
    return authInstance;
  })();

  return authPromise;
}
