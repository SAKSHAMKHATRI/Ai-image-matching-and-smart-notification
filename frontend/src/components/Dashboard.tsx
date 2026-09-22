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

export type DashboardView = "dashboard" | "profile" | "lost" | "found";

type DashboardProps = {
  userEmail?: string;
  onNavigate: (view: DashboardView) => void;
};

function formatCount(count: number, singular: string) {
  return count === 1 ? `1 ${singular}` : `${count} ${singular}s`;
}

export function Dashboard({ userEmail, onNavigate }: DashboardProps) {
  const { user, logOut } = useAuth();
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [lostItems, setLostItems] = useState<LostItem[]>([]);
  const [foundItems, setFoundItems] = useState<FoundItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  if (loading) {
    return <p role="status">Loading dashboard...</p>;
  }

  return (
    <section className="welcome-panel dashboard" aria-labelledby="dashboard-title">
      <p className="eyebrow">University services</p>
      <h1 id="dashboard-title">Lost &amp; Found</h1>
      <p className="intro">Choose what you would like to do.</p>

      <div className="identity-panel">
        <strong>Signed in</strong>
        <span>{userEmail || "No email returned"}</span>
      </div>

      {error && <p className="error-message" role="alert">{error}</p>}

      <div className="dashboard-grid">
        <article className="action-card" aria-labelledby="profile-card-title">
          <h2 id="profile-card-title">Student profile</h2>
          {profile ? (
            <dl className="profile-summary">
              <div>
                <dt>Name</dt>
                <dd>{profile.full_name}</dd>
              </div>
              <div>
                <dt>Roll number</dt>
                <dd>{profile.roll_number}</dd>
              </div>
              <div>
                <dt>Course</dt>
                <dd>{profile.course_program}</dd>
              </div>
              <div>
                <dt>Campus</dt>
                <dd>{profile.campus}</dd>
              </div>
            </dl>
          ) : (
            <p className="profile-note">
              No profile yet. Add your university details so reports can be traced back
              to you.
            </p>
          )}
          <button
            className="secondary-button"
            onClick={() => onNavigate("profile")}
            type="button"
          >
            {profile ? "View profile" : "Create profile"}
          </button>
        </article>

        <article className="action-card" aria-labelledby="lost-card-title">
          <h2 id="lost-card-title">Report Lost Item</h2>
          <p className="profile-note">
            You lost something on campus. Create a lost report so it can be matched
            with found items.
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

        <article className="action-card" aria-labelledby="reports-card-title">
          <h2 id="reports-card-title">Your reports</h2>
          {lostItems.length === 0 && foundItems.length === 0 ? (
            <p className="profile-note">No reports yet.</p>
          ) : (
            <ul className="report-summary-list">
              {lostItems.slice(0, 3).map((item) => (
                <li key={`lost-${item.id}`}>
                  Lost · {item.item_name} ({item.status})
                </li>
              ))}
              {foundItems.slice(0, 3).map((item) => (
                <li key={`found-${item.id}`}>
                  Found · {item.found_date} ({item.status})
                </li>
              ))}
            </ul>
          )}
        </article>
      </div>

      <div className="button-row">
        <button className="secondary-button" onClick={() => void logOut()} type="button">
          Log out
        </button>
      </div>
    </section>
  );
}
