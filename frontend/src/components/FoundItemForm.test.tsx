import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FoundItemForm } from "./FoundItemForm";
import { useAuth } from "../auth/AuthContext";
import {
  createFoundItem,
  triggerFoundItemAnalysis,
  uploadFoundItemImage,
} from "../services/api";

vi.mock("../auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("../services/api", () => ({
  createFoundItem: vi.fn(),
  triggerFoundItemAnalysis: vi.fn(),
  uploadFoundItemImage: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);
const mockedCreateFoundItem = vi.mocked(createFoundItem);
const mockedTriggerAnalysis = vi.mocked(triggerFoundItemAnalysis);
const mockedUploadImage = vi.mocked(uploadFoundItemImage);
const mockedUser = { getIdToken: vi.fn().mockResolvedValue("verified-token") };
const foundItem = {
  id: 3,
  status: "REPORTED",
  found_date: "2026-09-19",
  found_location: "Library",
  campus: "North Campus",
  image_reference: "found-items/owner/3/photo.png",
  analysis_status: "UNAVAILABLE",
  analysis_error: "AI analysis is unavailable; reporting remains available.",
  created_at: "2026-09-19T00:00:00Z",
  updated_at: "2026-09-19T00:00:00Z",
};

describe("FoundItemForm", () => {
  afterEach(cleanup);

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

  it("reports a found item, uploads its photo, and triggers analysis", async () => {
    mockedCreateFoundItem.mockResolvedValue({ ...foundItem, image_reference: null });
    mockedUploadImage.mockResolvedValue(foundItem);
    mockedTriggerAnalysis.mockResolvedValue({
      found_item: foundItem,
      accepted: false,
      message: "Found item saved. AI analysis is not configured yet.",
    });

    render(<FoundItemForm />);
    fireEvent.change(screen.getByLabelText("Found date"), { target: { value: "2026-09-19" } });
    fireEvent.change(screen.getByLabelText("Found location"), { target: { value: "Library" } });
    fireEvent.change(screen.getByLabelText("Campus"), { target: { value: "North Campus" } });
    const image = new File(["image"], "found.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("Found-item photo"), { target: { files: [image] } });
    const form = screen.getByRole("button", { name: "Report and analyze" }).closest("form");
    expect(form).not.toBeNull();
    fireEvent.submit(form!);

    await waitFor(() => expect(mockedTriggerAnalysis).toHaveBeenCalled());
    expect(mockedCreateFoundItem.mock.calls[0]?.[0]).toBe("verified-token");
    expect(mockedUploadImage.mock.calls[0]?.[2]).toBe(image);
    expect(screen.getByText("Found item saved. AI analysis is not configured yet.")).toBeVisible();
    expect(screen.getByText("Analysis status: UNAVAILABLE")).toBeVisible();
  });
});
