import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MatchResultsView } from "./MatchResultsView";
import { useAuth } from "../auth/AuthContext";
import {
  evaluateMatches,
  getLostItemMatches,
  type FoundItem,
  type LostItem,
  type MatchSearchResponse,
} from "../services/api";

vi.mock("../auth/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("../services/api", () => ({
  evaluateMatches: vi.fn(),
  getLostItemMatches: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(msg: string) {
      super(msg);
    }
  },
}));

const mockedUseAuth = vi.mocked(useAuth);
const mockedEvaluateMatches = vi.mocked(evaluateMatches);
const mockedGetLostItemMatches = vi.mocked(getLostItemMatches);
const mockedUser = { getIdToken: vi.fn().mockResolvedValue("test-auth-token") };

const mockFoundItem: FoundItem = {
  id: 42,
  status: "REPORTED",
  found_date: "2026-09-20",
  found_location: "Main Library 2nd Floor",
  campus: "North Campus",
  item_name: "Black ThinkPad Laptop",
  category: "Laptops",
  color: "Black",
  brand: "Lenovo",
  description: "Black Lenovo laptop with charger.",
  distinctive_features: "Linux sticker on lid",
  image_reference: "found-items/42/photo.jpg",
  analysis_status: "ANALYZED",
  analysis_error: null,
  created_at: "2026-09-20T10:00:00Z",
  updated_at: "2026-09-20T10:00:00Z",
};

const mockMatchResponse: MatchSearchResponse = {
  found_item_id: 42,
  total_matches: 2,
  strong_matches_count: 1,
  possible_matches_count: 1,
  low_confidence_count: 0,
  disclaimer:
    "Match confidence is for ranking and candidate review only and does not establish proof of ownership.",
  matches: [
    {
      id: 101,
      lost_item_id: 101,
      match_id: 1,
      status: "ACTIVE",
      item_name: "Lost Lenovo ThinkPad X1",
      category: "Laptops",
      color: "Black",
      brand: "Lenovo",
      campus: "North Campus",
      approximate_location: "Library Study Room",
      lost_date: "2026-09-19",
      description: "Black thinkpad with stickers.",
      distinctive_features: "Red trackpoint and linux logo",
      image_reference: null,
      score: 0.88,
      score_percent: 88,
      classification: "STRONG_CANDIDATE",
      classification_label: "Strong candidate",
      reasons: [
        "Same category: Laptops",
        "Brand appears consistent: Lenovo",
        "Matching color: Black",
        "Compatible campus: North Campus",
      ],
      components: {
        image_text: { score: 0.90, weight: 0.55, contribution: 0.495 },
        attributes: { score: 1.0, weight: 0.20, contribution: 0.20 },
        location: { score: 0.80, weight: 0.15, contribution: 0.12 },
        date: { score: 1.0, weight: 0.10, contribution: 0.10 },
      },
      created_at: "2026-09-19T14:00:00Z",
    },
    {
      id: 102,
      lost_item_id: 102,
      match_id: 2,
      status: "ACTIVE",
      item_name: "Dell XPS 13",
      category: "Laptops",
      color: "Silver",
      brand: "Dell",
      campus: "North Campus",
      approximate_location: "Cafeteria",
      lost_date: "2026-09-15",
      description: "Silver laptop in black sleeve.",
      distinctive_features: null,
      image_reference: null,
      score: 0.72,
      score_percent: 72,
      classification: "POSSIBLE_CANDIDATE",
      classification_label: "Possible candidate",
      reasons: [
        "Same category: Laptops",
        "Compatible campus: North Campus",
      ],
      components: {
        image_text: { score: 0.70, weight: 0.55, contribution: 0.385 },
        attributes: { score: 0.50, weight: 0.20, contribution: 0.10 },
        location: { score: 0.80, weight: 0.15, contribution: 0.12 },
        date: { score: 0.90, weight: 0.10, contribution: 0.09 },
      },
      created_at: "2026-09-15T10:00:00Z",
    },
  ],
};

describe("MatchResultsView", () => {
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

  it("renders candidate matches with score badges, classifications, and explanations", async () => {
    mockedEvaluateMatches.mockResolvedValueOnce(mockMatchResponse);
    const onBack = vi.fn();

    render(<MatchResultsView foundItem={mockFoundItem} onBack={onBack} />);

    expect(screen.getByRole("status")).toHaveTextContent("Analyzing candidate matches");

    await waitFor(() => {
      expect(screen.getByText("Lost Lenovo ThinkPad X1")).toBeInTheDocument();
    });

    // Score badges and classification labels
    expect(screen.getByText("88%")).toBeInTheDocument();
    expect(screen.getByText("Strong candidate")).toBeInTheDocument();
    expect(screen.getByText("72%")).toBeInTheDocument();
    expect(screen.getByText("Possible candidate")).toBeInTheDocument();

    // Explanations reasons
    expect(screen.getAllByText(/Same category: Laptops/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Brand appears consistent: Lenovo/i)).toBeInTheDocument();


    // Disclaimer banner
    expect(screen.getByRole("note").textContent).toContain("do not establish proof of ownership");
  });




  it("never displays private student owner data (email, phone, roll number)", async () => {
    mockedEvaluateMatches.mockResolvedValueOnce(mockMatchResponse);
    render(<MatchResultsView foundItem={mockFoundItem} onBack={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("Lost Lenovo ThinkPad X1")).toBeInTheDocument();
    });

    const bodyText = document.body.textContent ?? "";
    expect(bodyText).not.toContain("student@university.edu");
    expect(bodyText).not.toContain("Phone Number");
    expect(bodyText).not.toContain("Roll Number");
  });

  it("filters matches by classification chip", async () => {
    mockedEvaluateMatches.mockResolvedValueOnce(mockMatchResponse);
    render(<MatchResultsView foundItem={mockFoundItem} onBack={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("Lost Lenovo ThinkPad X1")).toBeInTheDocument();
    });

    // Click Strong filter chip
    fireEvent.click(screen.getByRole("button", { name: /Strong \(1\)/i }));

    expect(screen.getByText("Lost Lenovo ThinkPad X1")).toBeInTheDocument();
    expect(screen.queryByText("Dell XPS 13")).not.toBeInTheDocument();

    // Click Possible filter chip
    fireEvent.click(screen.getByRole("button", { name: /Possible \(1\)/i }));

    expect(screen.queryByText("Lost Lenovo ThinkPad X1")).not.toBeInTheDocument();
    expect(screen.getByText("Dell XPS 13")).toBeInTheDocument();
  });

  it("displays empty state fallback when no candidate matches exist", async () => {
    mockedEvaluateMatches.mockResolvedValueOnce({
      found_item_id: 42,
      total_matches: 0,
      strong_matches_count: 0,
      possible_matches_count: 0,
      low_confidence_count: 0,
      disclaimer: "Disclaimer text",
      matches: [],
    });

    render(<MatchResultsView foundItem={mockFoundItem} onBack={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTestId("empty-matches")).toBeInTheDocument();
    });

    expect(screen.getByText("No matching lost items found")).toBeInTheDocument();
  });

  it("displays low-confidence warning when all matches are low-confidence", async () => {
    mockedEvaluateMatches.mockResolvedValueOnce({
      found_item_id: 42,
      total_matches: 1,
      strong_matches_count: 0,
      possible_matches_count: 0,
      low_confidence_count: 1,
      disclaimer: "Disclaimer text",
      matches: [
        {
          id: 105,
          lost_item_id: 105,
          status: "ACTIVE",
          item_name: "Generic Umbrella",
          score: 0.45,
          score_percent: 45,
          classification: "LOW_CONFIDENCE",
          classification_label: "Low confidence",
          reasons: ["Compatible campus: North Campus"],
          components: {},
          created_at: "2026-09-18T00:00:00Z",
        },
      ],
    });

    render(<MatchResultsView foundItem={mockFoundItem} onBack={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/Low Confidence Results/i);
    });
  });

  it("opens match detail breakdown modal and closes on close click", async () => {
    mockedEvaluateMatches.mockResolvedValueOnce(mockMatchResponse);
    render(<MatchResultsView foundItem={mockFoundItem} onBack={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText("Lost Lenovo ThinkPad X1")).toBeInTheDocument();
    });

    // Click View Breakdown button
    const detailButtons = screen.getAllByRole("button", { name: /View Breakdown/i });
    fireEvent.click(detailButtons[0]);

    // Modal dialog is displayed
    const modal = screen.getByRole("dialog");
    expect(modal).toBeInTheDocument();
    expect(screen.getByText("Match Detail — Lost Lenovo ThinkPad X1")).toBeInTheDocument();
    expect(screen.getByText("Component Score Breakdown")).toBeInTheDocument();
    expect(screen.getByText("Image / Text Semantic")).toBeInTheDocument();

    // Close modal
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("invokes onBack when clicking back button", async () => {
    mockedEvaluateMatches.mockResolvedValueOnce(mockMatchResponse);
    const onBack = vi.fn();
    render(<MatchResultsView foundItem={mockFoundItem} onBack={onBack} />);

    await waitFor(() => {
      expect(screen.getByText("Lost Lenovo ThinkPad X1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "← Back" }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it("loads and displays matches for a lost item report (Lost-owner view)", async () => {
    const mockLostItem: LostItem = {
      id: 101,
      status: "ACTIVE",
      item_name: "My Lost Backpack",
      category: "Bags & Backpacks",
      color: "Navy Blue",
      brand: "Nike",
      campus: "North Campus",
      lost_date: "2026-09-20",
      approximate_location: "Cafeteria",
      description: "Blue backpack with laptop inside.",
      distinctive_features: "Keychain attached",
      image_reference: null,
      created_at: "2026-09-20T10:00:00Z",
      updated_at: "2026-09-20T10:00:00Z",
    };

    const mockLostMatchResponse: MatchSearchResponse = {
      lost_item_id: 101,
      total_matches: 1,
      strong_matches_count: 1,
      possible_matches_count: 0,
      low_confidence_count: 0,
      disclaimer: "Match confidence is for ranking only.",
      matches: [
        {
          id: 55,
          found_item_id: 55,
          lost_item_id: 101,
          match_id: 10,
          status: "REPORTED",
          item_name: "Found Nike Navy Backpack",
          category: "Bags & Backpacks",
          color: "Navy Blue",
          brand: "Nike",
          campus: "North Campus",
          found_location: "Cafeteria Table 4",
          found_date: "2026-09-20",
          description: "Navy blue backpack found on cafeteria table.",
          distinctive_features: "Keychain attached",
          image_reference: null,
          score: 0.92,
          score_percent: 92,
          classification: "STRONG_CANDIDATE",
          classification_label: "Strong candidate",
          reasons: ["Same category", "Matching color", "Same campus"],
          components: {
            attributes: { score: 1.0, weight: 0.4, contribution: 0.4 },
            location: { score: 0.9, weight: 0.3, contribution: 0.27 },
            date: { score: 1.0, weight: 0.3, contribution: 0.3 },
          },
          created_at: "2026-09-20T12:00:00Z",
        },
      ],
    };

    mockedGetLostItemMatches.mockResolvedValueOnce(mockLostMatchResponse);
    render(<MatchResultsView lostItem={mockLostItem} onBack={vi.fn()} />);

    expect(screen.getByText(/Analyzing candidate matches across campus records/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Potential Matches for Lost Item #101")).toBeInTheDocument();
      expect(screen.getByText("Found Nike Navy Backpack")).toBeInTheDocument();
      expect(screen.getByText("92%")).toBeInTheDocument();
      expect(screen.getByText("Found Report #55")).toBeInTheDocument();
    });

    expect(mockedGetLostItemMatches).toHaveBeenCalledWith("test-auth-token", 101, false);
  });
});
