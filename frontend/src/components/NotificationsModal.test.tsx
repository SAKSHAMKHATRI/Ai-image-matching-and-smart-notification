import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { NotificationsModal } from "./NotificationsModal";
import * as api from "../services/api";

// Mock AuthContext
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: {
      getIdToken: vi.fn().mockResolvedValue("mock-token"),
    },
  }),
}));

describe("NotificationsModal", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders notification list and handles click to open lost item matches", async () => {
    const mockNotifications: api.AppNotification[] = [
      {
        id: 1,
        user_id: 10,
        type: "POSSIBLE_MATCH",
        title: "Possible Match Found",
        message: 'A newly found item ("Black Wildcraft Backpack") matches your lost report.',
        entity_id: 42,
        is_read: false,
        created_at: "2026-09-23T02:00:00Z",
      },
    ];

    vi.spyOn(api, "getNotifications").mockResolvedValue({
      notifications: mockNotifications,
      unread_count: 1,
      total: 1,
    });

    const markReadSpy = vi.spyOn(api, "markNotificationAsRead").mockResolvedValue(undefined);

    const onClose = vi.fn();
    const onOpenLostItemMatches = vi.fn();
    const onUnreadCountChange = vi.fn();

    render(
      <NotificationsModal
        isOpen={true}
        onClose={onClose}
        onOpenLostItemMatches={onOpenLostItemMatches}
        onUnreadCountChange={onUnreadCountChange}
      />
    );

    expect(await screen.findByText("Possible Match Found")).toBeInTheDocument();
    expect(screen.getByText(/Black Wildcraft Backpack/)).toBeInTheDocument();

    const notifItem = screen.getByTestId("notification-item-1");
    fireEvent.click(notifItem);

    await waitFor(() => {
      expect(markReadSpy).toHaveBeenCalledWith("mock-token", 1);
      expect(onClose).toHaveBeenCalled();
      expect(onOpenLostItemMatches).toHaveBeenCalledWith(42);
    });
  });

  it("handles mark all as read", async () => {
    const mockNotifications: api.AppNotification[] = [
      {
        id: 2,
        user_id: 10,
        type: "POSSIBLE_MATCH",
        title: "Possible Match Found",
        message: "Match found",
        entity_id: 43,
        is_read: false,
        created_at: "2026-09-23T02:00:00Z",
      },
    ];

    vi.spyOn(api, "getNotifications").mockResolvedValue({
      notifications: mockNotifications,
      unread_count: 1,
      total: 1,
    });

    const markAllSpy = vi.spyOn(api, "markAllNotificationsAsRead").mockResolvedValue(undefined);

    const onClose = vi.fn();
    const onOpenLostItemMatches = vi.fn();
    const onUnreadCountChange = vi.fn();

    render(
      <NotificationsModal
        isOpen={true}
        onClose={onClose}
        onOpenLostItemMatches={onOpenLostItemMatches}
        onUnreadCountChange={onUnreadCountChange}
      />
    );

    expect(await screen.findByText("Possible Match Found")).toBeInTheDocument();
    const markAllBtn = screen.getByRole("button", { name: /Mark all as read/i });
    fireEvent.click(markAllBtn);

    await waitFor(() => {
      expect(markAllSpy).toHaveBeenCalledWith("mock-token");
      expect(onUnreadCountChange).toHaveBeenCalledWith(0);
    });
  });
});
