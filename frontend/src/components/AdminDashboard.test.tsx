import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AdminDashboard } from "./AdminDashboard";

const mockGetIdToken = vi.fn().mockResolvedValue("mock-admin-token");
const mockUser = {
  uid: "admin-uid-1",
  email: "admin@university.edu",
  getIdToken: mockGetIdToken,
};

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: mockUser,
  }),
}));

const mockOverview = {
  total_users: 5,
  active_users: 4,
  suspended_users: 1,
  total_lost_items: 8,
  active_lost_items: 6,
  returned_lost_items: 2,
  closed_lost_items: 0,
  total_found_items: 7,
  active_found_items: 5,
  returned_found_items: 2,
  closed_found_items: 0,
  total_matches: 4,
  suggested_matches: 2,
  claimed_matches: 2,
  total_claims: 3,
  active_claims: 1,
  disputed_claims: 1,
  approved_claims: 1,
  returned_claims: 1,
  rejected_claims: 0,
};

const mockUsers = [
  {
    id: 1,
    firebase_uid: "uid-1",
    status: "ACTIVE",
    role: "ADMIN",
    email: "admin@university.edu",
    full_name: "Admin User",
    roll_number: "ADM-001",
    campus: "Main Campus",
    lost_count: 0,
    found_count: 0,
    claim_count: 0,
    created_at: "2026-09-01",
    updated_at: "2026-09-01",
  },
  {
    id: 2,
    firebase_uid: "uid-2",
    status: "ACTIVE",
    role: "STUDENT",
    email: "student@university.edu",
    full_name: "John Student",
    roll_number: "CS-001",
    campus: "North Campus",
    lost_count: 2,
    found_count: 1,
    claim_count: 1,
    created_at: "2026-09-02",
    updated_at: "2026-09-02",
  },
];

const mockLostItems = [
  {
    id: 101,
    item_name: "Lost Laptop",
    category: "Laptops",
    campus: "North Campus",
    status: "ACTIVE",
    lost_date: "2026-09-10",
  },
];

const mockFoundItems = [
  {
    id: 201,
    item_name: "Found Laptop",
    category: "Laptops",
    campus: "North Campus",
    status: "REPORTED",
    found_date: "2026-09-11",
    analysis_status: "ANALYZED",
  },
];

const mockClaims = [
  {
    id: 301,
    match_id: 1,
    claimant_user_id: 2,
    status: "ADMIN_REVIEW",
    lost_item_name: "Lost Laptop",
    found_item_name: "Found Laptop",
    claimant_name: "John Student",
    match_score: 0.92,
  },
];

const mockAuditLogs = [
  {
    id: 1,
    actor_user_id: 1,
    actor_email: "admin@university.edu",
    entity_type: "claims",
    entity_id: 301,
    action: "CLAIM_ESCALATED_ADMIN_REVIEW",
    details: { reason: "Disputed serial" },
    created_at: "2026-09-12 10:00:00",
  },
];

vi.mock("../services/api", () => ({
  ApiError: class extends Error {},
  getAdminOverview: vi.fn().mockImplementation(() => Promise.resolve(mockOverview)),
  getAdminUsers: vi.fn().mockImplementation(() => Promise.resolve(mockUsers)),
  getAdminLostItems: vi.fn().mockImplementation(() => Promise.resolve(mockLostItems)),
  getAdminFoundItems: vi.fn().mockImplementation(() => Promise.resolve(mockFoundItems)),
  getAdminClaims: vi.fn().mockImplementation(() => Promise.resolve(mockClaims)),
  getAdminAuditLogs: vi.fn().mockImplementation(() => Promise.resolve(mockAuditLogs)),
  updateAdminUserStatus: vi.fn().mockResolvedValue({}),
  updateAdminLostItemStatus: vi.fn().mockResolvedValue({}),
  updateAdminFoundItemStatus: vi.fn().mockResolvedValue({}),
  overrideAdminClaim: vi.fn().mockResolvedValue({}),
}));

describe("AdminDashboard Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders overview metrics after loading", async () => {
    const onBack = vi.fn();
    render(<AdminDashboard onBack={onBack} />);

    expect(screen.getByRole("status")).toHaveTextContent(/Loading Administrator Dashboard/i);

    await waitFor(() => {
      expect(screen.getByTestId("admin-dashboard")).toBeInTheDocument();
    });

    expect(screen.getByText("Total Users")).toBeInTheDocument();
    expect(screen.getByText("Disputed Claims")).toBeInTheDocument();
    expect(screen.getByText("Total Lost Reports")).toBeInTheDocument();
  });

  it("allows switching between navigation tabs", async () => {
    const onBack = vi.fn();
    render(<AdminDashboard onBack={onBack} />);

    await waitFor(() => {
      expect(screen.getByTestId("admin-dashboard")).toBeInTheDocument();
    });

    // Switch to Disputes tab
    const disputesTab = screen.getByRole("button", { name: /Disputes & Claims/i });
    fireEvent.click(disputesTab);
    expect(screen.getByText(/Claims & Escalated Disputes/i)).toBeInTheDocument();
    expect(screen.getByText("#301")).toBeInTheDocument();

    // Switch to Users tab
    const usersTab = screen.getByRole("button", { name: /Users/i });
    fireEvent.click(usersTab);
    expect(screen.getByText("John Student")).toBeInTheDocument();
    expect(screen.getByText("student@university.edu")).toBeInTheDocument();
  });

  it("calls onBack when back button is clicked", async () => {
    const onBack = vi.fn();
    render(<AdminDashboard onBack={onBack} />);

    await waitFor(() => {
      expect(screen.getByTestId("admin-dashboard")).toBeInTheDocument();
    });

    const backBtn = screen.getByRole("button", { name: /Back to Student View/i });
    fireEvent.click(backBtn);
    expect(onBack).toHaveBeenCalledTimes(1);
  });
});

