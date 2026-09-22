import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App, { firebaseErrorMessage, getFirebaseErrorCode } from "./App";
import { useAuth } from "./auth/AuthContext";

vi.mock("./auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("./services/api", () => ({
  getMyProfile: vi.fn().mockResolvedValue(null),
  getMyLostItems: vi.fn().mockResolvedValue([]),
  getMyFoundItems: vi.fn().mockResolvedValue([]),
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
    </section>
  ),
}));

const mockedUseAuth = vi.mocked(useAuth);

function mockAuthenticatedUser() {
  mockedUseAuth.mockReturnValue({
    user: {
      email: "student@example.edu",
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
