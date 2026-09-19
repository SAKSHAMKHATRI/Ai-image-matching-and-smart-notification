import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LostItemForm } from "./LostItemForm";
import { useAuth } from "../auth/AuthContext";
import { deleteLostItem, getMyLostItems, saveLostItem } from "../services/api";

vi.mock("../auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("../services/api", () => ({
  deleteLostItem: vi.fn(),
  getMyLostItems: vi.fn(),
  saveLostItem: vi.fn(),
}));

const mockedUseAuth = vi.mocked(useAuth);
const mockedGetMyLostItems = vi.mocked(getMyLostItems);
const mockedSaveLostItem = vi.mocked(saveLostItem);
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

    render(<LostItemForm />);

    await screen.findByRole("heading", { name: "Report a lost item" });
    fireEvent.change(screen.getByLabelText("Item name"), { target: { value: "Wallet" } });
    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "Accessories" } });
    fireEvent.change(screen.getByLabelText("Lost date"), { target: { value: "2026-09-18" } });
    fireEvent.change(screen.getByLabelText("Approximate location"), { target: { value: "Student center" } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Black leather wallet with a small tear." } });
    fireEvent.click(screen.getByRole("button", { name: "Create report" }));

    await waitFor(() => expect(mockedSaveLostItem).toHaveBeenCalled());
    expect(mockedSaveLostItem.mock.calls[0]?.[0]).toBe("verified-token");
    expect(mockedSaveLostItem.mock.calls[0]?.[2]).toBeUndefined();
  });
});