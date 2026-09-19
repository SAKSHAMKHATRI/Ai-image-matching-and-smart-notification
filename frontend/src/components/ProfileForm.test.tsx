import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProfileForm } from "./ProfileForm";
import { useAuth } from "../auth/AuthContext";
import { getMyProfile, saveMyProfile } from "../services/api";

vi.mock("../auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("../services/api", () => ({
  getMyProfile: vi.fn(),
  saveMyProfile: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);
const mockedGetMyProfile = vi.mocked(getMyProfile);
const mockedSaveMyProfile = vi.mocked(saveMyProfile);

const mockedUser = { getIdToken: vi.fn().mockResolvedValue("verified-token") };

describe("ProfileForm", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    mockedUseAuth.mockReturnValue({
      user: mockedUser as never,
      loading: false,
      configurationError: null,
      signUp: vi.fn(),
      logIn: vi.fn(),
      logInWithGoogle: vi.fn(),
      logOut: vi.fn(),
    });
  });

  it("loads an empty form for a student without a profile", async () => {
    mockedGetMyProfile.mockResolvedValue(null);

    render(<ProfileForm />);

    expect(await screen.findByRole("heading", { name: "Your university details" })).toBeVisible();
    expect(screen.getByLabelText("Full name")).toHaveValue("");
    expect(mockedUser.getIdToken).toHaveBeenCalled();
  });

  it("loads and saves the authenticated student's profile", async () => {
    const profile = {
      id: 1,
      firebase_uid: "verified-user",
      full_name: "Ada Lovelace",
      roll_number: "CS-001",
      class_section: "A",
      course_program: "Computer Science",
      semester: 3,
      phone_number: "+1 555 123 4567",
      university_email: "ada@example.edu",
      campus: "North Campus",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    mockedGetMyProfile.mockResolvedValue(profile);
    mockedSaveMyProfile.mockResolvedValue(profile);

    render(<ProfileForm />);

    expect(await screen.findByDisplayValue("Ada Lovelace")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Campus"), {
      target: { value: "South Campus" },
    });
    fireEvent.click(await screen.findByRole("button", { name: "Save profile" }));

    await waitFor(() => expect(mockedSaveMyProfile).toHaveBeenCalled());
    expect(mockedSaveMyProfile.mock.calls[0]?.[0]).toBe("verified-token");
    expect(mockedSaveMyProfile.mock.calls[0]?.[2]).toBe(true);
  });
});