import {
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  GoogleAuthProvider,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
  type User,
} from "firebase/auth";
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { getFirebaseAuth } from "../services/firebase";

export type AuthContextValue = {
  user: User | null;
  loading: boolean;
  configurationError: string | null;
  signUp: (email: string, password: string) => Promise<void>;
  logIn: (email: string, password: string) => Promise<void>;
  logInWithGoogle: () => Promise<void>;
  logOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [configurationError, setConfigurationError] = useState<string | null>(
    null,
  );

  useEffect(() => {
    let unsubscribe: () => void = () => undefined;

    getFirebaseAuth()
      .then((auth) => {
        unsubscribe = onAuthStateChanged(auth, (nextUser) => {
          setUser(nextUser);
          setLoading(false);
        });
      })
      .catch(() => {
        setConfigurationError(
          "Authentication is not configured. Add Firebase web settings to your local .env file.",
        );
        setLoading(false);
      });

    return () => unsubscribe();
  }, []);

  async function signUp(email: string, password: string) {
    const auth = await getFirebaseAuth();
    await createUserWithEmailAndPassword(auth, email, password);
  }

  async function logIn(email: string, password: string) {
    const auth = await getFirebaseAuth();
    await signInWithEmailAndPassword(auth, email, password);
  }

  async function logInWithGoogle() {
    const auth = await getFirebaseAuth();
    await signInWithPopup(auth, new GoogleAuthProvider());
  }

  async function logOut() {
    const auth = await getFirebaseAuth();
    await signOut(auth);
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        configurationError,
        signUp,
        logIn,
        logInWithGoogle,
        logOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }
  return context;
}
