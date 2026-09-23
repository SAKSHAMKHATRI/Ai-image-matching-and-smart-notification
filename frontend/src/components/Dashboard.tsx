import { useEffect, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import {
  ApiError,
  getMyClaims,
  getMyFoundItems,
  getMyLostItems,
  getMyProfile,
  getNotifications,
  type ClaimSummary,
  type FoundItem,
  type LostItem,
  type StudentProfile,
} from "../services/api";
import { NotificationsModal } from "./NotificationsModal";

export type DashboardView = "dashboard" | "profile" | "lost" | "found" | "matches" | "admin" | "search";

type DashboardProps = {
  userEmail?: string;
  onNavigate: (view: DashboardView) => void;
  onSelectFoundItemForMatches?: (foundItem: FoundItem) => void;
  onSelectLostItemForMatches?: (lostItem: LostItem) => void;
  onSelectLostItemIdForMatches?: (lostItemId: number) => void;
};

function formatCount(count: number, singular: string) {
  return count === 1 ? `1 ${singular}` : `${count} ${singular}s`;
}

export function Dashboard({
  userEmail,
  onNavigate,
  onSelectFoundItemForMatches,
  onSelectLostItemForMatches,
  onSelectLostItemIdForMatches,
}: DashboardProps) {
  const { user, logOut } = useAuth();
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [lostItems, setLostItems] = useState<LostItem[]>([]);
  const [foundItems, setFoundItems] = useState<FoundItem[]>([]);
  const [myClaims, setMyClaims] = useState<ClaimSummary[]>([]);
  const [unreadNotifications, setUnreadNotifications] = useState(0);
  const [showNotifications, setShowNotifications] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isAdmin = Boolean(
    profile?.role === "ADMIN" ||
    userEmail?.toLowerCase().includes("admin") ||
    profile?.university_email?.toLowerCase().includes("admin")
  );

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const token = await user!.getIdToken();
        const [loadedProfile, lost, found, notifs, claims] = await Promise.all([
          getMyProfile(token),
          getMyLostItems(token),
          getMyFoundItems(token),
          getNotifications(token).catch(() => ({ notifications: [], unread_count: 0, total: 0 })),
          getMyClaims(token).catch(() => []),
        ]);
        if (!active) return;
        setProfile(loadedProfile);
        setLostItems(lost);
        setFoundItems(found);
        setMyClaims(claims);
        setUnreadNotifications(notifs.unread_count);
      } catch (loadError) {
        if (active) {
          setError(
            loadError instanceof ApiError
              ? loadError.message
              : "Your dashboard could not be loaded.",
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [user]);

  function handleViewMatches(foundItem: FoundItem) {
    if (onSelectFoundItemForMatches) {
      onSelectFoundItemForMatches(foundItem);
    }
    onNavigate("matches");
  }

  function handleViewLostMatches(lostItem: LostItem) {
    if (onSelectLostItemForMatches) {
      onSelectLostItemForMatches(lostItem);
    }
    onNavigate("matches");
  }

  function handleOpenLostItemMatchesFromNotification(lostItemId: number) {
    if (onSelectLostItemIdForMatches) {
      onSelectLostItemIdForMatches(lostItemId);
    } else {
      const match = lostItems.find((item) => item.id === lostItemId);
      if (match && onSelectLostItemForMatches) {
        onSelectLostItemForMatches(match);
      }
    }
    onNavigate("matches");
  }

  if (loading) {
    return <p role="status">Loading dashboard...</p>;
  }

  return (
    <section className="welcome-panel dashboard" aria-labelledby="dashboard-title">
      <div className="dashboard-header-row">
        <div>
          <p className="eyebrow">University services</p>
          <h1 id="dashboard-title">Lost &amp; Found</h1>
        </div>
        <div className="dashboard-header-actions">
          <button
            type="button"
            className="secondary-button notification-bell-btn"
            onClick={() => setShowNotifications(true)}
            aria-label="View notifications"
            data-testid="notification-bell-btn"
          >
            🔔 Notifications
            {unreadNotifications > 0 && (
              <span className="badge badge-unread-counter" data-testid="notification-badge-count">
                {unreadNotifications}
              </span>
            )}
          </button>
        </div>
      </div>

      <p className="lead">
        Welcome to the campus Lost &amp; Found portal. Report missing belongings, submit
        items you found, or check existing reports for potential matches.
      </p>

      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}

      <NotificationsModal
        isOpen={showNotifications}
        onClose={() => setShowNotifications(false)}
        onOpenLostItemMatches={handleOpenLostItemMatchesFromNotification}
        onUnreadCountChange={setUnreadNotifications}
      />

      <div className="dashboard-grid">
        <article className="action-card" aria-labelledby="profile-card-title">
          <h2 id="profile-card-title">Student Profile</h2>
          <p className="profile-note">
            Keep your official contact information up to date so we can reach you
            when a match is found.
          </p>
          <div className="profile-summary">
            <strong>{profile?.full_name ?? "Loading profile..."}</strong>
            <span>{profile?.university_email ?? userEmail ?? "No email"}</span>
            <span>{profile?.phone_number ?? "No phone added"}</span>
            <span>{profile?.campus ?? "No campus set"}</span>
          </div>
          <button
            className="secondary-button"
            onClick={() => onNavigate("profile")}
            type="button"
          >
            Edit Profile
          </button>
        </article>

        <article className="action-card" aria-labelledby="lost-card-title">
          <h2 id="lost-card-title">Report Lost Item</h2>
          <p className="profile-note">
            Create a detailed description of what you lost. We will check it against
            all reported found items automatically.
          </p>
          <span className="report-count">
            {formatCount(lostItems.length, "lost report")}
          </span>
          <button
            className="primary-button"
            onClick={() => onNavigate("lost")}
            type="button"
          >
            Report Lost
          </button>
        </article>

        <article className="action-card" aria-labelledby="found-card-title">
          <h2 id="found-card-title">Report Found Item</h2>
          <p className="profile-note">
            You found someone else's item. Report it so its owner can be matched and
            notified.
          </p>
          <span className="report-count">
            {formatCount(foundItems.length, "found report")}
          </span>
          <button
            className="primary-button"
            onClick={() => onNavigate("found")}
            type="button"
          >
            Report Found
          </button>
        </article>

        <article className="action-card" aria-labelledby="search-card-title">
          <h2 id="search-card-title">🔍 Browse &amp; Search</h2>
          <p className="profile-note">
            Browse all active lost and found items on campus. Filter by category, color, campus, or keyword.
          </p>
          <button
            className="secondary-button"
            onClick={() => onNavigate("search")}
            type="button"
            data-testid="browse-search-btn"
          >
            Browse All Items
          </button>
        </article>

        <article className="action-card" aria-labelledby="reports-card-title">
          <h2 id="reports-card-title">Your reports &amp; matches</h2>
          {lostItems.length === 0 && foundItems.length === 0 ? (
            <p className="profile-note">No reports yet.</p>
          ) : (
            <div className="reports-with-actions">
              <ul className="report-summary-list">
                {lostItems.slice(0, 3).map((item) => (
                  <li key={`lost-${item.id}`} className="report-summary-item found-with-match-btn">
                    <div className="found-info-row">
                      <span>Lost · {item.item_name} ({item.status})</span>
                      <button
                        className="match-link-btn"
                        onClick={() => handleViewLostMatches(item)}
                        type="button"
                        data-testid={`view-lost-matches-btn-${item.id}`}
                      >
                        🔍 View Matches
                      </button>
                    </div>
                  </li>
                ))}
                {foundItems.slice(0, 3).map((item) => (
                  <li key={`found-${item.id}`} className="report-summary-item found-with-match-btn">
                    <div className="found-info-row">
                      <span>Found · {item.item_name || item.category || "Item"} ({item.found_date})</span>
                      <button
                        className="match-link-btn"
                        onClick={() => handleViewMatches(item)}
                        type="button"
                        data-testid={`view-matches-btn-${item.id}`}
                      >
                        🔍 View Matches
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </article>

        {myClaims.some((c) => c.is_finder || foundItems.some((f) => f.id === c.found_item_id)) && (
          <article className="action-card" aria-labelledby="claims-card-title">
            <h2 id="claims-card-title">📦 Claims on Items You Found</h2>
            <p className="profile-note">
              Students who identified an item you reported found have filed these claims.
            </p>
            <div className="reports-with-actions">
              <ul className="report-summary-list">
                {myClaims
                  .filter((c) => c.is_finder || foundItems.some((f) => f.id === c.found_item_id))
                  .map((claim) => (
                    <li key={`claim-${claim.id}`} className="report-summary-item">
                      <div className="found-info-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
                        <div>
                          <strong>Item: {claim.found_item_name || claim.item_name || "Found Item"}</strong>
                          <div style={{ fontSize: "0.85rem", color: "#64748b", marginTop: "2px" }}>
                            Claimant: {claim.claimant_name || "Campus Student"}
                          </div>
                        </div>
                        <span
                          className={`status-tag status-${claim.status.toLowerCase()}`}
                          style={{
                            fontSize: "0.75rem",
                            padding: "2px 8px",
                            borderRadius: "999px",
                            fontWeight: 600,
                            background: claim.status === "CLAIM_REQUESTED" ? "#fef3c7" : "#e0f2fe",
                            color: claim.status === "CLAIM_REQUESTED" ? "#92400e" : "#0369a1",
                          }}
                        >
                          {claim.status === "CLAIM_REQUESTED" ? "UNDER REVIEW" : claim.status}
                        </span>
                      </div>
                    </li>
                  ))}
              </ul>
            </div>
          </article>
        )}

        {isAdmin && (
          <article className="action-card admin-card" aria-labelledby="admin-card-title">
            <h2 id="admin-card-title">🛡️ Admin Moderation</h2>
            <p className="profile-note">
              Platform administration: review all reports, mediate disputes, moderate users, and inspect audit logs.
            </p>
            <button
              className="primary-button"
              onClick={() => onNavigate("admin")}
              type="button"
              data-testid="admin-panel-btn"
            >
              Open Admin Center
            </button>
          </article>
        )}
      </div>

      <div className="button-row">
        {isAdmin && (
          <button
            className="secondary-button"
            onClick={() => onNavigate("admin")}
            type="button"
          >
            🛡️ Admin Center
          </button>
        )}
        <button className="secondary-button" onClick={() => void logOut()} type="button">
          Log out
        </button>
      </div>
    </section>
  );
}
