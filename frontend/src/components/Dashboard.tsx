import { useEffect, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import {
  ApiError,
  getMyFoundItems,
  getMyLostItems,
  getMyProfile,
  type FoundItem,
  type LostItem,
  type StudentProfile,
} from "../services/api";

export type DashboardView = "dashboard" | "profile" | "lost" | "found" | "matches" | "admin" | "search";

type DashboardProps = {
  userEmail?: string;
  onNavigate: (view: DashboardView) => void;
  onSelectFoundItemForMatches?: (foundItem: FoundItem) => void;
  onSelectLostItemForMatches?: (lostItem: LostItem) => void;
};

function formatCount(count: number, singular: string) {
  return count === 1 ? `1 ${singular}` : `${count} ${singular}s`;
}

export function Dashboard({
  userEmail,
  onNavigate,
  onSelectFoundItemForMatches,
  onSelectLostItemForMatches,
}: DashboardProps) {
  const { user, logOut } = useAuth();
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [lostItems, setLostItems] = useState<LostItem[]>([]);
  const [foundItems, setFoundItems] = useState<FoundItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isAdmin = Boolean(
    userEmail?.toLowerCase().includes("admin") ||
    profile?.university_email?.toLowerCase().includes("admin")
  );

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const token = await user!.getIdToken();
        const [loadedProfile, lost, found] = await Promise.all([
          getMyProfile(token),
          getMyLostItems(token),
          getMyFoundItems(token),
        ]);
        if (!active) return;
        setProfile(loadedProfile);
        setLostItems(lost);
        setFoundItems(found);
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

  if (loading) {
    return <p role="status">Loading dashboard...</p>;
  }

  return (
    <section className="welcome-panel dashboard" aria-labelledby="dashboard-title">
      <p className="eyebrow">University services</p>
      <h1 id="dashboard-title">Lost &amp; Found</h1>
      <p className="lead">
        Welcome to the campus Lost &amp; Found portal. Report missing belongings, submit
        items you found, or check existing reports for potential matches.
      </p>

      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}

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
