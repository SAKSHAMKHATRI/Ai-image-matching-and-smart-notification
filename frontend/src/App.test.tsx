import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App, { firebaseErrorMessage, getFirebaseErrorCode } from "./App";
import { useAuth } from "./auth/AuthContext";
import { verifyAdminStatus } from "./services/api";

vi.mock("./auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("./services/api", () => ({
  getMyProfile: vi.fn().mockResolvedValue(null),
  getMyLostItems: vi.fn().mockResolvedValue([]),
  getMyFoundItems: vi.fn().mockResolvedValue([]),
  verifyAdminStatus: vi.fn().mockResolvedValue({ status: "ok", role: "ADMIN", is_admin: true }),
}));

vi.mock("./services/firebase", () => ({
  getFirebaseAuth: vi.fn().mockResolvedValue({
    currentUser: {
      getIdToken: vi.fn().mockResolvedValue("mock-admin-token"),
    },
  }),
}));

vi.mock("./components/ProfileForm", () => ({
  ProfileForm: () => <section aria-label="profile form">Profile</section>,
}));

vi.mock("./components/LostItemForm", () => ({
  LostItemForm: ({ onBack }: { onBack?: () => void }) => (
    <button onClick={onBack} type="button">lost-form</button>
  ),
}));

vi.mock("./components/FoundItemForm", () => ({
  FoundItemForm: ({ onBack }: { onBack?: () => void }) => (
    <button onClick={onBack} type="button">found-form</button>
  ),
}));

vi.mock("./components/AdminDashboard", () => ({
  AdminDashboard: ({ onBack }: { onBack?: () => void }) => (
    <section aria-label="admin dashboard view">
      <span>Admin Moderation View</span>
      <button onClick={onBack} type="button">back-to-student</button>
    </section>
  ),
}));

vi.mock("./components/Dashboard", () => ({
  Dashboard: ({
    onNavigate,
    userEmail,
  }: {
    onNavigate: (view: string) => void;
    userEmail?: string;
  }) => (
    <section aria-label="dashboard">
      <span>{userEmail}</span>
      <button onClick={() => onNavigate("profile")} type="button">dashboard-profile</button>
      <button onClick={() => onNavigate("lost")} type="button">dashboard-lost</button>
      <button onClick={() => onNavigate("found")} type="button">dashboard-found</button>
      <button onClick={() => onNavigate("admin")} type="button">dashboard-admin</button>
    </section>
  ),
}));

const mockedUseAuth = vi.mocked(useAuth);
const mockedVerifyAdminStatus = vi.mocked(verifyAdminStatus);

function mockAuthenticatedUser(email = "student@example.edu") {
  mockedUseAuth.mockReturnValue({
    user: {
      email,
      getIdToken: vi.fn().mockResolvedValue("token"),
    } as never,
    loading: false,
    configurationError: null,
    signUp: vi.fn(),
    logIn: vi.fn(),
    logInWithGoogle: vi.fn(),
    logOut: vi.fn(),
  });
}

describe("authentication UI states", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it.each([
    ["auth/unauthorized-domain", "This app domain is not authorized"],
    ["auth/operation-not-allowed", "sign-in method is not enabled"],
    ["auth/popup-blocked", "browser blocked the sign-in popup"],
    ["auth/popup-closed-by-user", "popup was closed"],
    ["auth/cancelled-popup-request", "Another sign-in popup"],
    ["auth/configuration-not-found", "configuration was not found"],
  ])("maps %s without exposing error details", (code, expectedMessage) => {
    const error = { code, message: "internal Firebase detail" };

    expect(getFirebaseErrorCode(error)).toBe(code);
    expect(firebaseErrorMessage(error)).toContain(expectedMessage);
    expect(firebaseErrorMessage(error)).not.toContain("internal Firebase detail");
  });

  it("shows the sign-in form when no user is authenticated", () => {
    mockedUseAuth.mockReturnValue({
      user: null,
      loading: false,
      configurationError: null,
      signUp: vi.fn(),
      logIn: vi.fn(),
      logInWithGoogle: vi.fn(),
      logOut: vi.fn(),
    });

    render(<App />);

    expect(screen.getByRole("heading", { name: "Lost & Found" })).toBeVisible();
    expect(screen.getAllByRole("button", { name: "Log in" })).toHaveLength(2);
    expect(screen.getByLabelText("University email")).toBeVisible();
    expect(screen.getByRole("button", { name: /Continue with Google/i })).toBeVisible();
  });

  it("shows the dashboard for an authenticated user", () => {
    mockAuthenticatedUser();

    render(<App />);

    expect(screen.getByLabelText("dashboard")).toBeVisible();
    expect(screen.getByText("student@example.edu")).toBeVisible();
    expect(screen.queryByRole("heading", { name: "You are signed in" })).toBeNull();
    expect(screen.queryByLabelText("profile form")).toBeNull();
    expect(screen.queryByRole("button", { name: "lost-form" })).toBeNull();
  });

  it("navigates from the dashboard to the profile page and back", () => {
    mockAuthenticatedUser();

    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "dashboard-profile" }));

    expect(screen.getByText("Profile")).toBeVisible();
    expect(screen.getByRole("button", { name: /Back to dashboard/ })).toBeVisible();
    expect(screen.queryByLabelText("dashboard")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /Back to dashboard/ }));
    expect(screen.getByLabelText("dashboard")).toBeVisible();
  });

  it("navigates to Report Lost and Report Found separately", () => {
    mockAuthenticatedUser();

    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "dashboard-lost" }));

    expect(screen.getByRole("button", { name: "lost-form" })).toBeVisible();
    expect(screen.queryByLabelText("dashboard")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /Back to dashboard/ }));
    fireEvent.click(screen.getByRole("button", { name: "dashboard-found" }));

    expect(screen.getByRole("button", { name: "found-form" })).toBeVisible();
    expect(screen.queryByLabelText("dashboard")).toBeNull();
  });

  it("shows a configuration error without exposing implementation details", () => {
    mockedUseAuth.mockReturnValue({
      user: null,
      loading: false,
      configurationError: "Authentication is not configured.",
      signUp: vi.fn(),
      logIn: vi.fn(),
      logInWithGoogle: vi.fn(),
      logOut: vi.fn(),
    });

    render(<App />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Authentication is not configured.",
    );
    expect(screen.queryByText(/private key|service account/i)).not.toBeInTheDocument();
  });
});

describe("Task 1: Password Visibility Controls", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("toggles password visibility between password and text type in login mode", () => {
    mockedUseAuth.mockReturnValue({
      user: null,
      loading: false,
      configurationError: null,
      signUp: vi.fn(),
      logIn: vi.fn(),
      logInWithGoogle: vi.fn(),
      logOut: vi.fn(),
    });

    render(<App />);

    const passwordInput = screen.getByLabelText("Password");
    expect(passwordInput).toHaveAttribute("type", "password");

    const toggleBtn = screen.getByTestId("toggle-password-visibility");
    expect(toggleBtn).toHaveAttribute("aria-label", "Show password");

    // Click to show password
    fireEvent.click(toggleBtn);
    expect(passwordInput).toHaveAttribute("type", "text");
    expect(toggleBtn).toHaveAttribute("aria-label", "Hide password");

    // Click to hide password again
    fireEvent.click(toggleBtn);
    expect(passwordInput).toHaveAttribute("type", "password");
    expect(toggleBtn).toHaveAttribute("aria-label", "Show password");
  });

  it("toggles password and confirm password visibility in signup mode", () => {
    mockedUseAuth.mockReturnValue({
      user: null,
      loading: false,
      configurationError: null,
      signUp: vi.fn(),
      logIn: vi.fn(),
      logInWithGoogle: vi.fn(),
      logOut: vi.fn(),
    });

    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Sign up" }));

    const passwordInput = screen.getByLabelText("Password");
    const confirmPasswordInput = screen.getByLabelText("Confirm Password");
    expect(passwordInput).toHaveAttribute("type", "password");
    expect(confirmPasswordInput).toHaveAttribute("type", "password");

    const togglePasswordBtn = screen.getByTestId("toggle-password-visibility");
    const toggleConfirmBtn = screen.getByTestId("toggle-confirm-password-visibility");

    fireEvent.click(togglePasswordBtn);
    expect(passwordInput).toHaveAttribute("type", "text");
    expect(confirmPasswordInput).toHaveAttribute("type", "password");

    fireEvent.click(toggleConfirmBtn);
    expect(confirmPasswordInput).toHaveAttribute("type", "text");
  });
});

describe("Task 2: Authentication UI Improvements", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders Google login button with multicolor SVG icon and calls logInWithGoogle", () => {
    const logInWithGoogleMock = vi.fn().mockResolvedValue(undefined);
    mockedUseAuth.mockReturnValue({
      user: null,
      loading: false,
      configurationError: null,
      signUp: vi.fn(),
      logIn: vi.fn(),
      logInWithGoogle: logInWithGoogleMock,
      logOut: vi.fn(),
    });

    render(<App />);

    const googleBtn = screen.getByRole("button", { name: /Continue with Google/i });
    expect(googleBtn).toBeVisible();
    expect(googleBtn.querySelector("svg.google-icon")).toBeInTheDocument();

    fireEvent.click(googleBtn);
    expect(logInWithGoogleMock).toHaveBeenCalledTimes(1);
  });

  it("renders Confirm Password field in signup mode and validates non-empty matching passwords", async () => {
    const signUpMock = vi.fn().mockResolvedValue(undefined);
    mockedUseAuth.mockReturnValue({
      user: null,
      loading: false,
      configurationError: null,
      signUp: signUpMock,
      logIn: vi.fn(),
      logInWithGoogle: vi.fn(),
      logOut: vi.fn(),
    });

    render(<App />);

    // Switch to signup mode
    const signupTab = screen.getByRole("button", { name: "Sign up" });
    fireEvent.click(signupTab);

    expect(screen.getByLabelText("Password")).toBeVisible();
    expect(screen.getByLabelText("Confirm Password")).toBeVisible();

    // Fill email and mismatched passwords
    fireEvent.change(screen.getByLabelText("University email"), {
      target: { value: "newstudent@chitkara.edu.in" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "securePass123" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "differentPass456" },
    });

    const createAccountBtn = screen.getByRole("button", { name: "Create account" });
    fireEvent.click(createAccountBtn);

    // Mismatch error must match exact required text
    expect(screen.getByRole("alert")).toHaveTextContent("Passwords do not match.");
    expect(signUpMock).not.toHaveBeenCalled();

    // Fix password mismatch
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "securePass123" },
    });
    fireEvent.click(createAccountBtn);

    await waitFor(() => {
      // signUp should only be called with email and password, NOT confirmPassword
      expect(signUpMock).toHaveBeenCalledWith("newstudent@chitkara.edu.in", "securePass123");
    });
  });
});

describe("Task 2: Dedicated Admin Authentication & Dashboard", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders dedicated admin login portal mode and switches fields", () => {
    mockedUseAuth.mockReturnValue({
      user: null,
      loading: false,
      configurationError: null,
      signUp: vi.fn(),
      logIn: vi.fn(),
      logInWithGoogle: vi.fn(),
      logOut: vi.fn(),
    });

    render(<App />);

    const adminTab = screen.getByRole("button", { name: /Admin Login/i });
    fireEvent.click(adminTab);

    expect(screen.getByRole("heading", { name: "Admin Portal" })).toBeVisible();
    expect(screen.getByLabelText("Administrator email")).toBeVisible();
    expect(screen.getByPlaceholderText("admin@chitkara.edu.in")).toBeVisible();
    expect(screen.getByRole("button", { name: "Admin Sign In" })).toBeVisible();
    // In admin mode, Google login is not displayed
    expect(screen.queryByRole("button", { name: /Continue with Google/i })).toBeNull();
  });

  it("authenticates admin and verifies ADMIN role via backend", async () => {
    const logInMock = vi.fn().mockResolvedValue(undefined);
    mockedUseAuth.mockReturnValue({
      user: null,
      loading: false,
      configurationError: null,
      signUp: vi.fn(),
      logIn: logInMock,
      logInWithGoogle: vi.fn(),
      logOut: vi.fn(),
    });

    mockedVerifyAdminStatus.mockResolvedValueOnce({
      status: "ok",
      uid: "admin-uid-123",
      email: "admin@chitkara.edu.in",
      role: "ADMIN",
      is_admin: true,
    });

    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /Admin Login/i }));
    fireEvent.change(screen.getByLabelText("Administrator email"), {
      target: { value: "admin@chitkara.edu.in" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "admin1234" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Admin Sign In" }));

    await waitFor(() => {
      expect(logInMock).toHaveBeenCalledWith("admin@chitkara.edu.in", "admin1234");
      expect(mockedVerifyAdminStatus).toHaveBeenCalledWith("mock-admin-token");
    });
  });

  it("denies access to non-admin student attempting admin login", async () => {
    const logInMock = vi.fn().mockResolvedValue(undefined);
    const logOutMock = vi.fn().mockResolvedValue(undefined);

    mockedUseAuth.mockReturnValue({
      user: null,
      loading: false,
      configurationError: null,
      signUp: vi.fn(),
      logIn: logInMock,
      logInWithGoogle: vi.fn(),
      logOut: logOutMock,
    });

    // Backend returns STUDENT role (403 or non-admin)
    mockedVerifyAdminStatus.mockResolvedValueOnce({
      status: "ok",
      uid: "student-uid-456",
      email: "student@chitkara.edu.in",
      role: "STUDENT",
      is_admin: false,
    });

    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /Admin Login/i }));
    fireEvent.change(screen.getByLabelText("Administrator email"), {
      target: { value: "student@chitkara.edu.in" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "student1234" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Admin Sign In" }));

    await waitFor(() => {
      expect(logOutMock).toHaveBeenCalled();
      expect(screen.getByRole("alert")).toHaveTextContent("Access denied. Administrator privileges required.");
    });
  });

  it("allows navigating to admin dashboard for authenticated admin", () => {
    mockAuthenticatedUser("admin@chitkara.edu.in");

    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "dashboard-admin" }));

    expect(screen.getByLabelText("admin dashboard view")).toBeVisible();
    expect(screen.getByText("Admin Moderation View")).toBeVisible();
  });
});
