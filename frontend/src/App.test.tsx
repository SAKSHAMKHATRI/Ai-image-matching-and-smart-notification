import { render } from "@testing-library/react";
import { screen } from "@testing-library/dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App, { firebaseErrorMessage, getFirebaseErrorCode } from "./App";
import { useAuth } from "./auth/AuthContext";

vi.mock("./auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("./components/ProfileForm", () => ({
  ProfileForm: () => null,
}));

vi.mock("./components/LostItemForm", () => ({
  LostItemForm: () => null,
}));

const mockedUseAuth = vi.mocked(useAuth);

describe("authentication UI states", () => {
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

  it("shows the protected page for an authenticated user", () => {
    mockedUseAuth.mockReturnValue({
      user: {
        email: "student@example.edu",
        getIdToken: vi.fn(),
      } as never,
      loading: false,
      configurationError: null,
      signUp: vi.fn(),
      logIn: vi.fn(),
      logInWithGoogle: vi.fn(),
      logOut: vi.fn(),
    });

    render(<App />);

    expect(screen.getByRole("heading", { name: "You are signed in" })).toBeVisible();
    expect(screen.getByText("student@example.edu")).toBeVisible();
    expect(screen.getByRole("button", { name: "Check protected API" })).toBeVisible();
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
