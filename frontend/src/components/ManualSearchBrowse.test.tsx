import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ManualSearchBrowse } from "./ManualSearchBrowse";

const {
  mockFoundResult,
  mockLostResult,
  mockSystemStatusOnline,
  mockSystemStatusOffline,
  mockGetIdToken,
  mockUser,
} = vi.hoisted(() => {
  const mockGetIdToken = vi.fn().mockResolvedValue("mock-token-123");
  const mockUser = {
    uid: "student-uid-1",
    email: "student@university.edu",
    getIdToken: mockGetIdToken,
  };

  const mockFoundResult = {
    items: [
      {
        id: 101,
        status: "ANALYZED",
        found_date: "2026-09-18",
        found_location: "Library 2nd Floor",
        campus: "Main Campus",
        item_name: "Blue Water Bottle",
        category: "Bottles & Containers",
        color: "Blue",
        brand: "Hydro Flask",
        description: "Insulated water bottle with stickers.",
        distinctive_features: "Mountain sticker.",
        image_reference: null,
        created_at: "2026-09-18T10:00:00",
      },
    ],
    total: 1,
    limit: 50,
    offset: 0,
    filters_applied: {},
  };

  const mockLostResult = {
    items: [
      {
        id: 201,
        status: "ACTIVE",
        lost_date: "2026-09-19",
        approximate_location: "Science Complex",
        campus: "North Campus",
        item_name: "TI-84 Graphing Calculator",
        category: "Electronics",
        color: "Black",
        brand: "Texas Instruments",
        description: "Calculator in black sliding case.",
        distinctive_features: "Yellow sticker on back.",
        image_reference: null,
        created_at: "2026-09-19T12:00:00",
      },
    ],
    total: 1,
    limit: 50,
    offset: 0,
    filters_applied: {},
  };

  const mockSystemStatusOnline = {
    ai_available: true,
    foundry_configured: true,
    ocr_configured: true,
    embeddings_configured: true,
    manual_search_available: true,
  };

  const mockSystemStatusOffline = {
    ai_available: false,
    foundry_configured: false,
    ocr_configured: false,
    embeddings_configured: false,
    manual_search_available: true,
  };

  return {
    mockFoundResult,
    mockLostResult,
    mockSystemStatusOnline,
    mockSystemStatusOffline,
    mockGetIdToken,
    mockUser,
  };
});

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: mockUser,
  }),
}));

vi.mock("../services/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../services/api")>();
  return {
    ...actual,
    getSearchSystemStatus: vi.fn().mockResolvedValue(mockSystemStatusOnline),
    searchPublicFoundItems: vi.fn().mockResolvedValue(mockFoundResult),
    searchPublicLostItems: vi.fn().mockResolvedValue(mockLostResult),
  };
});

describe("ManualSearchBrowse Component", () => {
  const onBack = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders search interface, tabs, and filter controls", async () => {
    render(<ManualSearchBrowse onBack={onBack} />);

    expect(screen.getByText(/Browse & Manual Search/i)).toBeDefined();
    expect(screen.getByTestId("tab-found-items")).toBeDefined();
    expect(screen.getByTestId("tab-lost-items")).toBeDefined();
    expect(screen.getByLabelText(/Keywords \/ Item Name/i)).toBeDefined();
    expect(screen.getByLabelText(/Category/i)).toBeDefined();
    expect(screen.getByLabelText(/Campus/i)).toBeDefined();

    await waitFor(() => {
      expect(screen.getByText("Blue Water Bottle")).toBeDefined();
    });
  });

  it("displays fallback indicator when AI system is offline", async () => {
    const { getSearchSystemStatus } = await import("../services/api");
    vi.mocked(getSearchSystemStatus).mockResolvedValueOnce(mockSystemStatusOffline);

    render(<ManualSearchBrowse onBack={onBack} />);

    await waitFor(() => {
      expect(screen.getByTestId("ai-fallback-indicator")).toBeDefined();
      expect(screen.getByText(/Manual Fallback Active/i)).toBeDefined();
    });
  });

  it("switches to lost items tab and fetches lost reports", async () => {
    const { searchPublicLostItems } = await import("../services/api");

    render(<ManualSearchBrowse onBack={onBack} />);

    const lostTab = screen.getByTestId("tab-lost-items");
    fireEvent.click(lostTab);

    await waitFor(() => {
      expect(searchPublicLostItems).toHaveBeenCalled();
      expect(screen.getByText("TI-84 Graphing Calculator")).toBeDefined();
    });
  });

  it("submits filter query and calls search API with parameters", async () => {
    const { searchPublicFoundItems } = await import("../services/api");

    render(<ManualSearchBrowse onBack={onBack} />);

    await waitFor(() => {
      expect(screen.getByText("Blue Water Bottle")).toBeDefined();
    });

    const queryInput = screen.getByLabelText(/Keywords \/ Item Name/i);
    fireEvent.change(queryInput, { target: { value: "Hydro Flask" } });

    const form = screen.getByRole("search");
    fireEvent.submit(form);

    await waitFor(() => {
      expect(searchPublicFoundItems).toHaveBeenCalledWith(
        "mock-token-123",
        expect.objectContaining({ query: "Hydro Flask" })
      );
    });
  });

  it("navigates back when back button is clicked", () => {
    render(<ManualSearchBrowse onBack={onBack} />);

    const backBtn = screen.getByTestId("search-back-btn");
    fireEvent.click(backBtn);
    expect(onBack).toHaveBeenCalledTimes(1);
  });
});
