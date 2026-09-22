import { useEffect, useState } from "react";
import {
  getNotifications,
  markAllNotificationsAsRead,
  markNotificationAsRead,
  type AppNotification,
} from "../services/api";
import { useAuth } from "../auth/AuthContext";

type NotificationsModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onOpenLostItemMatches: (lostItemId: number) => void;
  onUnreadCountChange?: (count: number) => void;
};

export function NotificationsModal({
  isOpen,
  onClose,
  onOpenLostItemMatches,
  onUnreadCountChange,
}: NotificationsModalProps) {
  const { user } = useAuth();
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function fetchNotifications() {
    if (!user) return;
    try {
      setLoading(true);
      setError(null);
      const token = await user.getIdToken();
      const res = await getNotifications(token);
      setNotifications(res.notifications);
      onUnreadCountChange?.(res.unread_count);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load notifications.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (isOpen) {
      void fetchNotifications();
    }
  }, [isOpen, user]);

  async function handleNotificationClick(notification: AppNotification) {
    if (!user) return;
    if (!notification.is_read) {
      try {
        const token = await user.getIdToken();
        await markNotificationAsRead(token, notification.id);
        setNotifications((prev) =>
          prev.map((n) => (n.id === notification.id ? { ...n, is_read: true } : n)),
        );
        onUnreadCountChange?.(
          Math.max(0, notifications.filter((n) => !n.is_read && n.id !== notification.id).length),
        );
      } catch {
        // Continue navigation even if marking read fails
      }
    }

    if (notification.type === "POSSIBLE_MATCH" && notification.entity_id) {
      onClose();
      onOpenLostItemMatches(notification.entity_id);
    }
  }

  async function handleMarkAllRead() {
    if (!user) return;
    try {
      const token = await user.getIdToken();
      await markAllNotificationsAsRead(token);
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      onUnreadCountChange?.(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not mark all as read.");
    }
  }

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="notifications-title">
      <div className="modal-content notification-modal" data-testid="notifications-modal">
        <div className="modal-header">
          <div className="notification-header-title">
            <h2 id="notifications-title">🔔 Notifications</h2>
            {notifications.some((n) => !n.is_read) && (
              <span className="badge badge-unread">New Updates</span>
            )}
          </div>
          <div className="notification-header-actions">
            {notifications.some((n) => !n.is_read) && (
              <button
                type="button"
                className="btn-link"
                onClick={() => void handleMarkAllRead()}
              >
                Mark all as read
              </button>
            )}
            <button
              type="button"
              className="close-button"
              onClick={onClose}
              aria-label="Close notifications"
            >
              ✕
            </button>
          </div>
        </div>

        {error && <p className="error-message" role="alert">{error}</p>}

        <div className="notification-body">
          {loading ? (
            <p className="loading-text" role="status">Loading notifications...</p>
          ) : notifications.length === 0 ? (
            <div className="notification-empty" data-testid="notifications-empty">
              <span className="empty-icon">📭</span>
              <p><strong>No notifications yet</strong></p>
              <p className="subtext">
                You will be automatically notified here when Microsoft AI Foundry discovers possible matches for your lost items.
              </p>
            </div>
          ) : (
            <ul className="notification-list" role="list">
              {notifications.map((n) => (
                <li
                  key={n.id}
                  className={`notification-item ${n.is_read ? "read" : "unread"}`}
                  onClick={() => void handleNotificationClick(n)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      void handleNotificationClick(n);
                    }
                  }}
                  data-testid={`notification-item-${n.id}`}
                >
                  <div className="notification-icon">
                    {n.type === "POSSIBLE_MATCH" ? "🎯" : "ℹ️"}
                  </div>
                  <div className="notification-content">
                    <div className="notification-top">
                      <strong className="notification-title">{n.title}</strong>
                      <span className="notification-time">{n.created_at?.slice(0, 16).replace("T", " ")}</span>
                    </div>
                    <p className="notification-message">{n.message}</p>
                    {n.type === "POSSIBLE_MATCH" && (
                      <span className="notification-action-hint">
                        Click to view match details &amp; deterministic scores →
                      </span>
                    )}
                  </div>
                  {!n.is_read && <span className="unread-dot" title="Unread" />}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="modal-footer">
          <button type="button" className="secondary-button" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
