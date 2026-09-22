import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FoundItemForm } from "./FoundItemForm";
import { useAuth } from "../auth/AuthContext";
import {
  analyzeItemImage,
  createFoundItem,
  deleteFoundItem,
  getMyFoundItems,
  triggerFoundItemAnalysis,
  updateFoundItem,
  uploadFoundItemImage,
} from "../services/api";

vi.mock("../auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("../services/api", () => ({
  analyzeItemImage: vi.fn(),
  createFoundItem: vi.fn(),
  deleteFoundItem: vi.fn(),
  getMyFoundItems: vi.fn(),
  triggerFoundItemAnalysis: vi.fn(),
  updateFoundItem: vi.fn(),
  uploadFoundItemImage: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);
const mockedAnalyzeImage = vi.mocked(analyzeItemImage);
const mockedCreateFoundItem = vi.mocked(createFoundItem);
const mockedDeleteFoundItem = vi.mocked(deleteFoundItem);
const mockedGetMyFoundItems = vi.mocked(getMyFoundItems);
const mockedTriggerAnalysis = vi.mocked(triggerFoundItemAnalysis);
const mockedUpdateFoundItem = vi.mocked(updateFoundItem);
const mockedUploadImage = vi.mocked(uploadFoundItemImage);
const mockedUser = { getIdToken: vi.fn().mockResolvedValue("verified-token") };
const foundItem = {
  id: 3,
  status: "REPORTED",
  found_date: "2026-09-19",
  found_location: "Library",
  campus: "North Campus",
  item_name: "water bottle",
  category: "Personal Items",
  color: "black",
  brand: "Hydro Flask",
  description: "Black matte stainless steel water bottle.",
  distinctive_features: "campus sticker",
  image_reference: "found-items/owner/3/photo.png",
  analysis_status: "ANALYZED",
  analysis_error: null,
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
    mockedGetMyFoundItems.mockResolvedValue([]);
  });

  it("reports a found item with manual inputs and uploads its photo", async () => {
    mockedAnalyzeImage.mockResolvedValue({
      success: false,
      message: "AI analysis is unavailable; you can fill details manually.",
    });
    mockedCreateFoundItem.mockResolvedValue({ ...foundItem, image_reference: null });
    mockedUploadImage.mockResolvedValue(foundItem);

    render(<FoundItemForm />);
    await screen.findByRole("heading", { name: /Report an item you found/i });
    fireEvent.change(screen.getByLabelText(/Found date/i), { target: { value: "2026-09-19" } });
    fireEvent.change(screen.getByLabelText(/Found location/i), { target: { value: "Library" } });
    fireEvent.change(screen.getByLabelText(/Campus/i), { target: { value: "North Campus" } });
    fireEvent.change(screen.getByLabelText(/Description/i), {
      target: { value: "Black water bottle found on table" },
    });

    const image = new File(["image"], "found.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText(/Found-item photo/i), { target: { files: [image] } });

    await waitFor(() => expect(mockedAnalyzeImage).toHaveBeenCalled());

    const form = screen.getByRole("button", { name: "Report found item" }).closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => expect(mockedCreateFoundItem).toHaveBeenCalled());
    expect(mockedCreateFoundItem.mock.calls[0]?.[0]).toBe("verified-token");
    expect(mockedUploadImage.mock.calls[0]?.[2]).toBe(image);
    expect(screen.getByText("Found item reported successfully.")).toBeVisible();
    expect(screen.getByText("Analysis status: ANALYZED")).toBeVisible();
  });

  it("auto-fills description and attributes from AI analysis and allows user editing before submitting", async () => {
    mockedAnalyzeImage.mockResolvedValue({
      success: true,
      message: "AI analyzed the item photo successfully.",
      description: "AI-generated description of black water bottle.",
      item_name: "water bottle",
      category: "Personal Items",
      color: "black",
      brand: "Hydro Flask",
      distinctive_features: "stickers on side",
      attributes: {
        description: "AI-generated description of black water bottle.",
        object_type: "water bottle",
      },
    });
    mockedCreateFoundItem.mockResolvedValue(foundItem);
    mockedUploadImage.mockResolvedValue(foundItem);

    render(<FoundItemForm />);
    await screen.findByRole("heading", { name: /Report an item you found/i });
    const image = new File(["image"], "found.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText(/Found-item photo/i), { target: { files: [image] } });

    await waitFor(() => {
      expect(
        (screen.getByLabelText(/Description/i) as HTMLTextAreaElement).value,
      ).toBe("AI-generated description of black water bottle.");
    });
    expect((screen.getByLabelText(/Item name/i) as HTMLInputElement).value).toBe("water bottle");
    expect((screen.getByLabelText(/Category/i) as HTMLInputElement).value).toBe("Personal Items");
    expect((screen.getByLabelText(/Primary color/i) as HTMLInputElement).value).toBe("black");
    expect((screen.getByLabelText(/Brand/i) as HTMLInputElement).value).toBe("Hydro Flask");
    expect((screen.getByLabelText(/Distinctive features/i) as HTMLTextAreaElement).value).toBe("stickers on side");
    expect(screen.getByText(/AI analyzed the photo/)).toBeVisible();

    // User edits the description before submitting
    fireEvent.change(screen.getByLabelText(/Description/i), {
      target: { value: "Edited user description for water bottle." },
    });
    expect((screen.getByLabelText(/Description/i) as HTMLTextAreaElement).value).toBe(
      "Edited user description for water bottle.",
    );

    fireEvent.change(screen.getByLabelText(/Found date/i), { target: { value: "2026-09-19" } });
    const form = screen.getByRole("button", { name: "Report found item" }).closest("form")!;
    fireEvent.submit(form);

    await waitFor(() => expect(mockedCreateFoundItem).toHaveBeenCalled());
    const payload = mockedCreateFoundItem.mock.calls[0]?.[1];
    expect(payload).toMatchObject({
      description: "Edited user description for water bottle.",
      item_name: "water bottle",
      category: "Personal Items",
      color: "black",
      brand: "Hydro Flask",
      found_date: "2026-09-19",
    });
  });

  it("loads user's found reports and enables editing a found report", async () => {
    mockedGetMyFoundItems.mockResolvedValue([foundItem]);
    mockedUpdateFoundItem.mockResolvedValue({ ...foundItem, description: "Updated bottle desc" });

    render(<FoundItemForm />);

    expect(await screen.findByText("water bottle")).toBeVisible();
    expect(screen.getByText("Personal Items · REPORTED")).toBeVisible();

    // Click Edit button
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));

    expect((screen.getByLabelText(/Description/i) as HTMLTextAreaElement).value).toBe(
      "Black matte stainless steel water bottle.",
    );
    expect((screen.getByLabelText(/Found location/i) as HTMLInputElement).value).toBe("Library");

    fireEvent.change(screen.getByLabelText(/Description/i), {
      target: { value: "Updated bottle desc" },
    });

    const updateBtn = screen.getByRole("button", { name: "Update report" });
    fireEvent.click(updateBtn);

    await waitFor(() => expect(mockedUpdateFoundItem).toHaveBeenCalled());
    expect(mockedUpdateFoundItem).toHaveBeenCalledWith(
      "verified-token",
      foundItem.id,
      expect.objectContaining({ description: "Updated bottle desc" }),
    );
  });

  it("deletes a found report when user confirms deletion", async () => {
    mockedGetMyFoundItems.mockResolvedValue([foundItem]);
    mockedDeleteFoundItem.mockResolvedValue();
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(<FoundItemForm />);

    expect(await screen.findByText("water bottle")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(mockedDeleteFoundItem).toHaveBeenCalledWith("verified-token", foundItem.id));
  });

  it("cancels deletion when user declines confirmation", async () => {
    mockedGetMyFoundItems.mockResolvedValue([foundItem]);
    vi.spyOn(window, "confirm").mockReturnValue(false);

    render(<FoundItemForm />);

    expect(await screen.findByText("water bottle")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(mockedDeleteFoundItem).not.toHaveBeenCalled();
  });
});
