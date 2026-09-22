import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LostItemForm } from "./LostItemForm";
import { useAuth } from "../auth/AuthContext";
import {
  deleteLostItem,
  getMyLostItems,
  saveLostItem,
  uploadLostItemImage,
} from "../services/api";

vi.mock("../auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("../services/api", () => ({
  deleteLostItem: vi.fn(),
  getMyLostItems: vi.fn(),
  saveLostItem: vi.fn(),
  uploadLostItemImage: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);
const mockedGetMyLostItems = vi.mocked(getMyLostItems);
const mockedSaveLostItem = vi.mocked(saveLostItem);
const mockedUploadLostItemImage = vi.mocked(uploadLostItemImage);
const mockedDeleteLostItem = vi.mocked(deleteLostItem);
const mockedUser = { getIdToken: vi.fn().mockResolvedValue("verified-token") };

const report = {
  id: 1,
  status: "ACTIVE",
  item_name: "Blue backpack",
  category: "Bags",
  color: "Navy blue",
  brand: "ExampleBrand",
  lost_date: "2026-09-18",
  approximate_location: "Library west entrance",
  description: "A navy backpack with a silver zipper and two front pockets.",
  distinctive_features: "Small astronomy patch.",
  image_reference: "lost-items/user-1/backpack.jpg",
  created_at: "2026-09-19T00:00:00Z",
  updated_at: "2026-09-19T00:00:00Z",
};

describe("LostItemForm", () => {
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

  it("loads the authenticated student's reports", async () => {
    mockedGetMyLostItems.mockResolvedValue([report]);

    render(<LostItemForm />);

    expect(await screen.findByText("Blue backpack")).toBeVisible();
    expect(screen.getByText("Bags · ACTIVE")).toBeVisible();
    expect(mockedUser.getIdToken).toHaveBeenCalled();
  });

  it("creates a new report through the authenticated API", async () => {
    mockedGetMyLostItems.mockResolvedValue([]);
    mockedSaveLostItem.mockResolvedValue(report);
    mockedUploadLostItemImage.mockResolvedValue(report);

    render(<LostItemForm />);

    await screen.findByRole("heading", { name: "Report a lost item" });
    fireEvent.change(screen.getByLabelText("Item name"), { target: { value: "Wallet" } });
    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "Clothing & Accessories" } });
    fireEvent.change(screen.getByLabelText("Lost date"), { target: { value: "2026-09-18" } });
    fireEvent.change(screen.getByLabelText("Approximate location"), { target: { value: "Student Center / Union" } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Black leather wallet with a small tear." } });
    fireEvent.click(screen.getByRole("button", { name: "Create report" }));

    await waitFor(() => expect(mockedSaveLostItem).toHaveBeenCalled());
    expect(mockedSaveLostItem.mock.calls[0]?.[0]).toBe("verified-token");
    expect(mockedSaveLostItem.mock.calls[0]?.[2]).toBeUndefined();
  });

  it("uploads an accepted image after creating a report", async () => {
    mockedGetMyLostItems.mockResolvedValue([]);
    mockedSaveLostItem.mockResolvedValue(report);
    mockedUploadLostItemImage.mockResolvedValue(report);

    render(<LostItemForm />);
    await screen.findByRole("heading", { name: "Report a lost item" });
    fireEvent.change(screen.getByLabelText("Item name"), { target: { value: "Wallet" } });
    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "Clothing & Accessories" } });
    fireEvent.change(screen.getByLabelText("Lost date"), { target: { value: "2026-09-18" } });
    fireEvent.change(screen.getByLabelText("Approximate location"), { target: { value: "Student Center / Union" } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Black leather wallet with a small tear." } });
    const image = new File(["image"], "wallet.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("Optional image"), {
      target: { files: [image] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create report" }));

    await waitFor(() => expect(mockedUploadLostItemImage).toHaveBeenCalled());
    expect(mockedUploadLostItemImage.mock.calls[0]?.[0]).toBe("verified-token");
    expect(mockedUploadLostItemImage.mock.calls[0]?.[1]).toBe(report.id);
    expect(mockedUploadLostItemImage.mock.calls[0]?.[2]).toBe(image);
  });

  it("submits canonical dropdown values correctly", async () => {
    mockedGetMyLostItems.mockResolvedValue([]);
    mockedSaveLostItem.mockResolvedValue(report);

    render(<LostItemForm />);
    await screen.findByRole("heading", { name: "Report a lost item" });

    fireEvent.change(screen.getByLabelText("Item name"), { target: { value: "Black Backpack" } });
    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "Bags & Backpacks" } });
    fireEvent.change(screen.getByLabelText("Color"), { target: { value: "Black" } });
    fireEvent.change(screen.getByLabelText("Brand"), { target: { value: "Nike" } });
    fireEvent.change(screen.getByLabelText("Lost date"), { target: { value: "2026-09-20" } });
    fireEvent.change(screen.getByLabelText("Approximate location"), { target: { value: "Main Library" } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Lost near 2nd floor study area." } });

    fireEvent.click(screen.getByRole("button", { name: "Create report" }));

    await waitFor(() => expect(mockedSaveLostItem).toHaveBeenCalled());
    const submittedPayload = mockedSaveLostItem.mock.calls[0]?.[1];
    expect(submittedPayload).toMatchObject({
      item_name: "Black Backpack",
      category: "Bags & Backpacks",
      color: "Black",
      brand: "Nike",
      lost_date: "2026-09-20",
      approximate_location: "Main Library",
      description: "Lost near 2nd floor study area.",
    });
  });

  it("allows specifying a custom brand with Other option", async () => {
    mockedGetMyLostItems.mockResolvedValue([]);
    mockedSaveLostItem.mockResolvedValue(report);

    render(<LostItemForm />);
    await screen.findByRole("heading", { name: "Report a lost item" });

    fireEvent.change(screen.getByLabelText("Item name"), { target: { value: "Thermos Flask" } });
    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "Bottles & Containers" } });
    fireEvent.change(screen.getByLabelText("Brand"), { target: { value: "OTHER_SPECIFY" } });

    // Custom brand text box appears
    const brandInput = await screen.findByLabelText("Specify brand name");
    fireEvent.change(brandInput, { target: { value: "Klean Kanteen" } });

    fireEvent.change(screen.getByLabelText("Lost date"), { target: { value: "2026-09-21" } });
    fireEvent.change(screen.getByLabelText("Approximate location"), { target: { value: "Student Center / Union" } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Stainless steel water container." } });

    fireEvent.click(screen.getByRole("button", { name: "Create report" }));

    await waitFor(() => expect(mockedSaveLostItem).toHaveBeenCalled());
    expect(mockedSaveLostItem.mock.calls[0]?.[1]?.brand).toBe("Klean Kanteen");
  });

  it("loads and edits an existing report with custom attributes without breaking", async () => {
    mockedGetMyLostItems.mockResolvedValue([report]);
    mockedSaveLostItem.mockResolvedValue({ ...report, item_name: "Updated Backpack" });

    render(<LostItemForm />);
    await screen.findByText("Blue backpack");

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));

    expect((screen.getByLabelText("Item name") as HTMLInputElement).value).toBe("Blue backpack");
    expect((screen.getByLabelText("Category") as HTMLSelectElement).value).toBe("Bags");
    expect((screen.getByLabelText("Approximate location") as HTMLSelectElement).value).toBe("Library west entrance");

    fireEvent.change(screen.getByLabelText("Item name"), { target: { value: "Updated Backpack" } });
    fireEvent.click(screen.getByRole("button", { name: "Update report" }));

    await waitFor(() => expect(mockedSaveLostItem).toHaveBeenCalled());
    expect(mockedSaveLostItem.mock.calls[0]?.[2]).toBe(report.id);
  });

  it("deletes a report when user confirms deletion", async () => {
    mockedGetMyLostItems.mockResolvedValue([report]);
    mockedDeleteLostItem.mockResolvedValue();
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(<LostItemForm />);
    await screen.findByText("Blue backpack");

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(deleteLostItem).toHaveBeenCalledWith("verified-token", report.id));
  });

  it("cancels deletion when user declines confirmation", async () => {
    mockedGetMyLostItems.mockResolvedValue([report]);
    vi.spyOn(window, "confirm").mockReturnValue(false);

    render(<LostItemForm />);
    await screen.findByText("Blue backpack");

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(mockedDeleteLostItem).not.toHaveBeenCalled();
  });
});