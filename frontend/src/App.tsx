import { useState } from "react";
import type { FormEvent } from "react";

import { useAuth } from "./auth/AuthContext";
import { getCurrentIdentity, type AuthenticatedIdentity } from "./services/api";

type FirebaseAuthError = {
  code?: string;
  message?: string;
};

export function getFirebaseErrorCode(error: unknown): string | null {
  if (!error || typeof error !== "object") {
    return null;
  }

  const candidate = error as FirebaseAuthError;
  if (typeof candidate.code === "string" && candidate.code.startsWith("auth/")) {
    return candidate.code;
  }

  return null;
}

export function firebaseErrorMessage(error: unknown) {
  const firebaseError = error as FirebaseAuthError;
  const code = getFirebaseErrorCode(error) ?? firebaseError.message ?? "";
  if (code.includes("auth/invalid-credential")) {
    return "The email or password is incorrect.";
  }
  if (code.includes("auth/email-already-in-use")) {
    return "An account already exists for this email.";
  }
  if (code.includes("auth/weak-password")) {
    return "Choose a password with at least six characters.";
  }
  if (code.includes("auth/invalid-email")) {
    return "Enter a valid email address.";
  }
  if (code.includes("auth/unauthorized-domain")) {
    return "This app domain is not authorized for Firebase sign-in.";
  }
  if (code.includes("auth/operation-not-allowed")) {
    return "This Firebase sign-in method is not enabled.";
  }
  if (code.includes("auth/popup-blocked")) {
    return "Your browser blocked the sign-in popup. Allow popups and try again.";
  }
  if (code.includes("auth/popup-closed-by-user")) {
    return "The sign-in popup was closed before authentication completed.";
  }
  if (code.includes("auth/cancelled-popup-request")) {
    return "Another sign-in popup is already active.";
  }
  if (code.includes("auth/configuration-not-found")) {
    return "Firebase Authentication configuration was not found.";
  }
  return "Authentication failed. Check your details and try again.";
}

function firebaseDevelopmentError(error: unknown) {
  if (!import.meta.env.DEV) {
    return null;
  }

  const code = getFirebaseErrorCode(error);
  return code ? `Firebase error code: ${code}` : null;
}

function AuthForm() {
  const { signUp, logIn, logInWithGoogle } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [developmentError, setDevelopmentError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setDevelopmentError(null);
    try {
      if (mode === "signup") {
        await signUp(email, password);
      } else {
        await logIn(email, password);
      }
    } catch (authError) {
      setError(firebaseErrorMessage(authError));
      setDevelopmentError(firebaseDevelopmentError(authError));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleGoogleLogin() {
    setSubmitting(true);
    setError(null);
    setDevelopmentError(null);
    try {
      await logInWithGoogle();
    } catch (authError) {
      setError(firebaseErrorMessage(authError));
      setDevelopmentError(firebaseDevelopmentError(authError));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="welcome-panel" aria-labelledby="auth-title">
      <p className="eyebrow">University services</p>
      <h1 id="auth-title">Lost &amp; Found</h1>
      <p className="intro">
        Sign in to access your protected university account. Profile details
        will be added in the next project phase.
      </p>
      <div className="mode-switch" aria-label="Authentication mode">
        <button
          className={mode === "login" ? "selected" : ""}
          onClick={() => setMode("login")}
          type="button"
        >
          Log in
        </button>
        <button
          className={mode === "signup" ? "selected" : ""}
          onClick={() => setMode("signup")}
          type="button"
        >
          Sign up
        </button>
      </div>
      <form className="auth-form" onSubmit={handleSubmit}>
        <label>
          University email
          <input
            autoComplete="email"
            onChange={(event) => setEmail(event.target.value)}
            required
            type="email"
            value={email}
          />
        </label>
        <label>
          Password
          <input
            autoComplete={mode === "signup" ? "new-password" : "current-password"}
            minLength={6}
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
        </label>
        {error && <p className="error-message" role="alert">{error}</p>}
        {developmentError && <p className="error-code" role="status">{developmentError}</p>}
        <button className="primary-button" disabled={submitting} type="submit">
          {submitting ? "Working..." : mode === "signup" ? "Create account" : "Log in"}
        </button>
        <button
          className="secondary-button"
          disabled={submitting}
          onClick={() => void handleGoogleLogin()}
          type="button"
        >
          Continue with Google
        </button>
      </form>
    </section>
  );
}

function ProtectedPage() {
  const { user, logOut } = useAuth();
  const [identity, setIdentity] = useState<AuthenticatedIdentity | null>(null);
  const [backendError, setBackendError] = useState<string | null>(null);

  async function checkBackendIdentity() {
    setBackendError(null);
    try {
      const token = await user!.getIdToken();
      setIdentity(await getCurrentIdentity(token));
    } catch {
      setBackendError("The backend could not verify your session.");
    }
  }

  return (
    <section className="welcome-panel" aria-labelledby="protected-title">
      <p className="eyebrow">Protected account</p>
      <h1 id="protected-title">You are signed in</h1>
      <p className="intro">Firebase Authentication is active for this session.</p>
      <div className="identity-panel">
        <strong>Firebase account</strong>
        <span>{user?.email || "No email returned"}</span>
      </div>
      {identity && (
        <div className="identity-panel" role="status">
          <strong>Verified backend identity</strong>
          <span>UID: {identity.uid}</span>
          <span>Email verified: {identity.email_verified ? "yes" : "no"}</span>
        </div>
      )}
      {backendError && <p className="error-message" role="alert">{backendError}</p>}
      <div className="button-row">
        <button className="primary-button" onClick={checkBackendIdentity} type="button">
          Check protected API
        </button>
        <button className="secondary-button" onClick={() => void logOut()} type="button">
          Log out
        </button>
      </div>
    </section>
  );
}

function App() {
  const { user, loading, configurationError } = useAuth();

  if (loading) {
    return <main className="app-shell"><p role="status">Loading authentication...</p></main>;
  }

  if (configurationError) {
    return <main className="app-shell"><p className="error-message" role="alert">{configurationError}</p></main>;
  }

  return <main className="app-shell">{user ? <ProtectedPage /> : <AuthForm />}</main>;
}

export default App;
