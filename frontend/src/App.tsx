import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { useAuth } from "./auth/AuthContext";
import { LostItemForm } from "./components/LostItemForm";
import { FoundItemForm } from "./components/FoundItemForm";
import { ProfileForm } from "./components/ProfileForm";
import { MatchResultsView } from "./components/MatchResultsView";
import { Dashboard, type DashboardView } from "./components/Dashboard";
import { AdminDashboard } from "./components/AdminDashboard";
import { ManualSearchBrowse } from "./components/ManualSearchBrowse";
import { verifyAdminStatus, type FoundItem, type LostItem } from "./services/api";

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

export function GoogleIcon() {
  return (
    <svg
      aria-hidden="true"
      className="google-icon"
      height="18"
      viewBox="0 0 24 24"
      width="18"
    >
      <path
        d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.66-5.17 3.66-9.17z"
        fill="#4285F4"
      />
      <path
        d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.25v3.15C3.26 21.36 7.33 24 12 24z"
        fill="#34A853"
      />
      <path
        d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.25C.45 8.17 0 9.98 0 12s.45 3.83 1.25 5.42l4.03-3.15z"
        fill="#FBBC05"
      />
      <path
        d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.33 0 3.26 2.64 1.25 6.58l4.03 3.15c.95-2.83 3.6-4.98 6.72-4.98z"
        fill="#EA4335"
      />
    </svg>
  );
}

export function EyeIcon() {
  return (
    <svg
      aria-hidden="true"
      className="eye-icon"
      fill="none"
      height="18"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="18"
    >
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

export function EyeOffIcon() {
  return (
    <svg
      aria-hidden="true"
      className="eye-icon"
      fill="none"
      height="18"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="18"
    >
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
      <line x1="1" x2="23" y1="1" y2="23" />
    </svg>
  );
}

export type AuthMode = "login" | "signup" | "admin";

type AuthFormProps = {
  initialMode?: AuthMode;
  onAdminLoginSuccess?: () => void;
  onModeChange?: (mode: AuthMode) => void;
};

export function AuthForm({
  initialMode = "login",
  onAdminLoginSuccess,
  onModeChange,
}: AuthFormProps) {
  const { signUp, logIn, logInWithGoogle, logOut } = useAuth();
  const [mode, setMode] = useState<AuthMode>(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [developmentError, setDevelopmentError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setMode(initialMode);
  }, [initialMode]);

  function switchMode(nextMode: AuthMode) {
    setMode(nextMode);
    setError(null);
    setDevelopmentError(null);
    if (onModeChange) {
      onModeChange(nextMode);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setDevelopmentError(null);

    if (mode === "signup") {
      if (!password) {
        setError("Password is required.");
        return;
      }
      if (!confirmPassword) {
        setError("Confirm Password is required.");
        return;
      }
      if (password !== confirmPassword) {
        setError("Passwords do not match.");
        return;
      }
    }

    setSubmitting(true);
    try {
      if (mode === "signup") {
        await signUp(email, password);
      } else if (mode === "admin") {
        await logIn(email, password);
        try {
          const { getFirebaseAuth } = await import("./services/firebase");
          const auth = await getFirebaseAuth();
          const token = await auth.currentUser?.getIdToken(true);
          if (!token) {
            throw new Error("Missing authentication token.");
          }
          const adminCheck = await verifyAdminStatus(token);
          if (adminCheck.role !== "ADMIN" && !adminCheck.is_admin) {
            await logOut();
            setError("Access denied. Administrator privileges required.");
            return;
          }
          if (onAdminLoginSuccess) {
            onAdminLoginSuccess();
          }
        } catch {
          await logOut();
          setError("Access denied. Administrator privileges required.");
          return;
        }
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
      <p className="eyebrow">
        {mode === "admin" ? "Campus Administration" : "University services"}
      </p>
      <h1 id="auth-title">
        {mode === "admin" ? "Admin Portal" : "Lost & Found"}
      </h1>
      <p className="intro">
        {mode === "admin"
          ? "Sign in with authorized administrator credentials to manage campus lost and found operations."
          : "Sign in to access your protected university account. Report lost belongings or items you found."}
      </p>

      <div className="mode-switch" aria-label="Authentication mode">
        <button
          className={mode === "login" ? "selected" : ""}
          onClick={() => switchMode("login")}
          type="button"
        >
          Log in
        </button>
        <button
          className={mode === "signup" ? "selected" : ""}
          onClick={() => switchMode("signup")}
          type="button"
        >
          Sign up
        </button>
        <button
          className={mode === "admin" ? "selected" : ""}
          onClick={() => switchMode("admin")}
          type="button"
        >
          🛡️ Admin Login
        </button>
      </div>

      <form className="auth-form" onSubmit={handleSubmit}>
        <label>
          {mode === "admin" ? "Administrator email" : "University email"}
          <input
            autoComplete="email"
            onChange={(event) => setEmail(event.target.value)}
            placeholder={mode === "admin" ? "admin@chitkara.edu.in" : "student@chitkara.edu.in"}
            required
            type="email"
            value={email}
          />
        </label>

        <label>
          Password
          <div className="password-input-wrapper">
            <input
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
              minLength={6}
              onChange={(event) => setPassword(event.target.value)}
              required
              type={showPassword ? "text" : "password"}
              value={password}
            />
            <button
              aria-label={showPassword ? "Hide password" : "Show password"}
              className="password-toggle-btn"
              data-testid="toggle-password-visibility"
              onClick={() => setShowPassword(!showPassword)}
              type="button"
            >
              {showPassword ? <EyeOffIcon /> : <EyeIcon />}
            </button>
          </div>
        </label>

        {mode === "signup" && (
          <label>
            Confirm Password
            <div className="password-input-wrapper">
              <input
                autoComplete="new-password"
                minLength={6}
                onChange={(event) => setConfirmPassword(event.target.value)}
                required
                type={showConfirmPassword ? "text" : "password"}
                value={confirmPassword}
              />
              <button
                aria-label={
                  showConfirmPassword
                    ? "Hide confirm password"
                    : "Show confirm password"
                }
                className="password-toggle-btn"
                data-testid="toggle-confirm-password-visibility"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                type="button"
              >
                {showConfirmPassword ? <EyeOffIcon /> : <EyeIcon />}
              </button>
            </div>
          </label>
        )}

        {error && <p className="error-message" role="alert">{error}</p>}
        {developmentError && <p className="error-code" role="status">{developmentError}</p>}

        <button className="primary-button" disabled={submitting} type="submit">
          {submitting
            ? "Working..."
            : mode === "signup"
              ? "Create account"
              : mode === "admin"
                ? "Admin Sign In"
                : "Log in"}
        </button>

        {mode !== "admin" ? (
          <button
            className="secondary-button google-button"
            disabled={submitting}
            onClick={() => void handleGoogleLogin()}
            type="button"
          >
            <GoogleIcon />
            <span>Continue with Google</span>
          </button>
        ) : (
          <div className="admin-login-link">
            <button onClick={() => switchMode("login")} type="button">
              ← Return to Student Login
            </button>
          </div>
        )}
      </form>
    </section>
  );
}

type ProtectedPageProps = {
  initialView?: DashboardView;
  onNavigate?: (view: DashboardView) => void;
};

export function ProtectedPage({ initialView = "dashboard", onNavigate }: ProtectedPageProps) {
  const { user } = useAuth();
  const [view, setView] = useState<DashboardView>(initialView);
  const [selectedFoundItem, setSelectedFoundItem] = useState<FoundItem | null>(null);
  const [selectedLostItem, setSelectedLostItem] = useState<LostItem | null>(null);
  const [selectedLostItemId, setSelectedLostItemId] = useState<number | null>(null);

  useEffect(() => {
    setView(initialView);
  }, [initialView]);

  function handleNavigate(nextView: DashboardView) {
    setView(nextView);
    if (onNavigate) {
      onNavigate(nextView);
    }
  }

  if (view === "dashboard") {
    return (
      <Dashboard
        userEmail={user?.email ?? undefined}
        onNavigate={handleNavigate}
        onSelectFoundItemForMatches={(item) => {
          setSelectedFoundItem(item);
          setSelectedLostItem(null);
          setSelectedLostItemId(null);
        }}
        onSelectLostItemForMatches={(item) => {
          setSelectedLostItem(item);
          setSelectedLostItemId(item.id);
          setSelectedFoundItem(null);
        }}
        onSelectLostItemIdForMatches={(lostId) => {
          setSelectedLostItemId(lostId);
          setSelectedLostItem(null);
          setSelectedFoundItem(null);
        }}
      />
    );
  }

  return (
    <section
      className={`welcome-panel ${view === "admin" ? "admin-dashboard" : ""}`}
      aria-labelledby="protected-title"
    >
      {view !== "matches" && view !== "admin" && view !== "search" && (
        <div className="button-row page-nav">
          <button
            className="secondary-button"
            onClick={() => handleNavigate("dashboard")}
            type="button"
          >
            ← Back to dashboard
          </button>
        </div>
      )}
      {view === "profile" && <ProfileForm />}
      {view === "lost" && <LostItemForm />}
      {view === "found" && <FoundItemForm />}
      {view === "admin" && <AdminDashboard onBack={() => handleNavigate("dashboard")} />}
      {view === "search" && (
        <ManualSearchBrowse
          onBack={() => handleNavigate("dashboard")}
          onNavigateToLostReport={() => handleNavigate("lost")}
          onNavigateToFoundReport={() => handleNavigate("found")}
        />
      )}
      {view === "matches" && (selectedFoundItem || selectedLostItem || selectedLostItemId) && (
        <MatchResultsView
          foundItem={selectedFoundItem}
          lostItem={selectedLostItem}
          lostItemId={selectedLostItemId}
          onBack={() => handleNavigate("dashboard")}
        />
      )}
    </section>
  );
}

function resolvePathState(): { mode: AuthMode; view: DashboardView } {
  if (typeof window === "undefined") {
    return { mode: "login", view: "dashboard" };
  }
  const path = window.location.pathname.toLowerCase();
  if (path === "/admin-login") {
    return { mode: "admin", view: "dashboard" };
  }
  if (path === "/admin") {
    return { mode: "admin", view: "admin" };
  }
  if (path === "/signup") {
    return { mode: "signup", view: "dashboard" };
  }
  return { mode: "login", view: "dashboard" };
}

function syncUrl(path: string) {
  if (typeof window !== "undefined" && window.location.pathname !== path) {
    window.history.pushState(null, "", path);
  }
}

function App() {
  const { user, loading, configurationError } = useAuth();
  const [routeState, setRouteState] = useState(resolvePathState());

  useEffect(() => {
    function handlePopState() {
      setRouteState(resolvePathState());
    }
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  if (loading) {
    return (
      <main className="app-shell">
        <p role="status">Loading authentication...</p>
      </main>
    );
  }

  if (configurationError) {
    return (
      <main className="app-shell">
        <p className="error-message" role="alert">
          {configurationError}
        </p>
      </main>
    );
  }

  return (
    <main className="app-shell">
      {user ? (
        <ProtectedPage
          initialView={routeState.view}
          onNavigate={(view) => {
            if (view === "admin") {
              syncUrl("/admin");
              setRouteState({ mode: "admin", view: "admin" });
            } else {
              syncUrl("/");
              setRouteState({ mode: "login", view });
            }
          }}
        />
      ) : (
        <AuthForm
          initialMode={routeState.mode}
          onAdminLoginSuccess={() => {
            syncUrl("/admin");
            setRouteState({ mode: "admin", view: "admin" });
          }}
          onModeChange={(nextMode) => {
            if (nextMode === "admin") {
              syncUrl("/admin-login");
            } else if (nextMode === "signup") {
              syncUrl("/signup");
            } else {
              syncUrl("/login");
            }
            setRouteState({ mode: nextMode, view: "dashboard" });
          }}
        />
      )}
    </main>
  );
}

export default App;
