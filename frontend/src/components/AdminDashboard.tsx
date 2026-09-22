import { useEffect, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import {
  ApiError,
  getAdminAuditLogs,
  getAdminClaims,
  getAdminFoundItems,
  getAdminLostItems,
  getAdminOverview,
  getAdminUsers,
  overrideAdminClaim,
  updateAdminFoundItemStatus,
  updateAdminLostItemStatus,
  updateAdminUserStatus,
  type AdminAuditLogEntry,
  type AdminOverviewStats,
  type AdminUserSummary,
  type FoundItem,
  type LostItem,
} from "../services/api";

type AdminTab = "overview" | "disputes" | "lost" | "found" | "users" | "audit";

type AdminDashboardProps = {
  onBack: () => void;
};

export function AdminDashboard({ onBack }: AdminDashboardProps) {
  const { user } = useAuth();
  const [tab, setTab] = useState<AdminTab>("overview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Data states
  const [stats, setStats] = useState<AdminOverviewStats | null>(null);
  const [usersList, setUsersList] = useState<AdminUserSummary[]>([]);
  const [lostList, setLostList] = useState<LostItem[]>([]);
  const [foundList, setFoundList] = useState<FoundItem[]>([]);
  const [claimsList, setClaimsList] = useState<Array<Record<string, unknown>>>([]);
  const [auditLogs, setAuditLogs] = useState<AdminAuditLogEntry[]>([]);

  // Override Modal state
  const [overrideClaimId, setOverrideClaimId] = useState<number | null>(null);
  const [overrideStatus, setOverrideStatus] = useState<string>("APPROVED");
  const [overrideNotes, setOverrideNotes] = useState<string>("");
  const [submittingAction, setSubmittingAction] = useState(false);

  async function loadData() {
    if (!user) return;
    setLoading(true);
    setError(null);

    try {
      const token = await user.getIdToken();
      const [overviewData, usersData, lostData, foundData, claimsData, auditData] =
        await Promise.all([
          getAdminOverview(token),
          getAdminUsers(token),
          getAdminLostItems(token),
          getAdminFoundItems(token),
          getAdminClaims(token),
          getAdminAuditLogs(token, { limit: "50" }),
        ]);

      setStats(overviewData);
      setUsersList(usersData);
      setLostList(lostData);
      setFoundList(foundData);
      setClaimsList(claimsData);
      setAuditLogs(auditData);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Administrative dashboard could not be loaded. Please ensure you have administrator privileges.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
  }, [user]);

  async function handleToggleUserStatus(userId: number, currentStatus: string) {
    if (!user) return;
    const targetStatus = currentStatus === "SUSPENDED" ? "ACTIVE" : "SUSPENDED";
    const reason = prompt(
      `Enter reason for setting user status to ${targetStatus}:`,
      targetStatus === "SUSPENDED" ? "Suspected fraudulent activity" : "Account reactivated by admin",
    );
    if (!reason) return;

    setSubmittingAction(true);
    setError(null);
    try {
      const token = await user.getIdToken();
      await updateAdminUserStatus(token, userId, targetStatus, reason);
      setSuccessMsg(`User #${userId} status updated to ${targetStatus}.`);
      void loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update user status.");
    } finally {
      setSubmittingAction(false);
    }
  }

  async function handleModerateItem(type: "lost" | "found", id: number, targetStatus: string) {
    if (!user) return;
    const reason = prompt(`Enter moderation reason for closing ${type} report #${id}:`, "Spam / duplicate report");
    if (!reason) return;

    setSubmittingAction(true);
    setError(null);
    try {
      const token = await user.getIdToken();
      if (type === "lost") {
        await updateAdminLostItemStatus(token, id, targetStatus, reason);
      } else {
        await updateAdminFoundItemStatus(token, id, targetStatus, reason);
      }
      setSuccessMsg(`${type.toUpperCase()} report #${id} marked as ${targetStatus}.`);
      void loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : `Failed to update ${type} report status.`);
    } finally {
      setSubmittingAction(false);
    }
  }

  async function handleExecuteClaimOverride() {
    if (!user || overrideClaimId === null) return;
    setSubmittingAction(true);
    setError(null);
    try {
      const token = await user.getIdToken();
      await overrideAdminClaim(token, overrideClaimId, overrideStatus, overrideNotes);
      setSuccessMsg(`Claim #${overrideClaimId} status updated to ${overrideStatus}.`);
      setOverrideClaimId(null);
      setOverrideNotes("");
      void loadData();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to override claim status.");
    } finally {
      setSubmittingAction(false);
    }
  }

  if (loading) {
    return (
      <section className="welcome-panel admin-dashboard" aria-labelledby="admin-title">
        <p role="status">Loading Administrator Dashboard...</p>
      </section>
    );
  }

  return (
    <section className="welcome-panel admin-dashboard" aria-labelledby="admin-title" data-testid="admin-dashboard">
      <div className="admin-header">
        <div className="admin-header-title">
          <p className="eyebrow">Staff &amp; Administration</p>
          <h1 id="admin-title">Admin Moderation Center</h1>
        </div>
        <button className="secondary-button" onClick={onBack} type="button">
          ← Back to Student View
        </button>
      </div>

      {error && <p className="error-message" role="alert">{error}</p>}
      {successMsg && <p className="success-message" role="status">{successMsg}</p>}

      {/* Navigation Tabs */}
      <nav className="mode-switch admin-tabs" aria-label="Admin Navigation">
        <button
          className={tab === "overview" ? "selected" : ""}
          onClick={() => setTab("overview")}
          type="button"
        >
          📊 Overview
        </button>
        <button
          className={tab === "disputes" ? "selected" : ""}
          onClick={() => setTab("disputes")}
          type="button"
        >
          ⚖️ Disputes &amp; Claims ({stats?.disputed_claims ?? 0})
        </button>
        <button
          className={tab === "lost" ? "selected" : ""}
          onClick={() => setTab("lost")}
          type="button"
        >
          🔍 Lost Reports ({stats?.total_lost_items ?? 0})
        </button>
        <button
          className={tab === "found" ? "selected" : ""}
          onClick={() => setTab("found")}
          type="button"
        >
          📦 Found Reports ({stats?.total_found_items ?? 0})
        </button>
        <button
          className={tab === "users" ? "selected" : ""}
          onClick={() => setTab("users")}
          type="button"
        >
          👥 Users ({stats?.total_users ?? 0})
        </button>
        <button
          className={tab === "audit" ? "selected" : ""}
          onClick={() => setTab("audit")}
          type="button"
        >
          📜 Audit Logs
        </button>
      </nav>

      {/* TAB 1: OVERVIEW */}
      {tab === "overview" && stats && (
        <div className="admin-overview-grid">
          <div className="stat-card">
            <span className="stat-label">Total Users</span>
            <span className="stat-value">{stats.total_users}</span>
            <span className="stat-sub">{stats.active_users} active · {stats.suspended_users} suspended</span>
          </div>
          <div className="stat-card stat-alert">
            <span className="stat-label">Disputed Claims</span>
            <span className="stat-value">{stats.disputed_claims}</span>
            <span className="stat-sub">Requiring Admin Mediation</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Total Lost Reports</span>
            <span className="stat-value">{stats.total_lost_items}</span>
            <span className="stat-sub">{stats.active_lost_items} active · {stats.returned_lost_items} returned</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Total Found Reports</span>
            <span className="stat-value">{stats.total_found_items}</span>
            <span className="stat-sub">{stats.active_found_items} active · {stats.returned_found_items} returned</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Total Claims</span>
            <span className="stat-value">{stats.total_claims}</span>
            <span className="stat-sub">{stats.approved_claims} approved · {stats.returned_claims} completed</span>
          </div>
        </div>
      )}

      {/* TAB 2: CLAIMS & DISPUTES */}
      {tab === "disputes" && (
        <div className="admin-table-container">
          <h3>Claims &amp; Escalated Disputes</h3>
          <p className="section-note">Review active claims and mediate disputes flagged for administrator review.</p>
          {claimsList.length === 0 ? (
            <p className="profile-note">No claims recorded yet.</p>
          ) : (
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Claim ID</th>
                  <th>Status</th>
                  <th>Lost Item</th>
                  <th>Found Item</th>
                  <th>Claimant</th>
                  <th>Score</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {claimsList.map((c) => (
                  <tr key={String(c.id)} className={c.status === "ADMIN_REVIEW" ? "row-highlight" : ""}>
                    <td><strong>#{String(c.id)}</strong></td>
                    <td>
                      <span className={`status-tag status-${String(c.status).toLowerCase()}`}>
                        {String(c.status)}
                      </span>
                    </td>
                    <td>{String(c.lost_item_name || `Lost #${String(c.lost_item_id)}`)}</td>
                    <td>{String(c.found_item_name || `Found #${String(c.found_item_id)}`)}</td>
                    <td>{String(c.claimant_name || c.claimant_email || `User #${String(c.claimant_user_id)}`)}</td>
                    <td>{c.match_score ? `${(Number(c.match_score) * 100).toFixed(0)}%` : "N/A"}</td>
                    <td>
                      <button
                        className="secondary-button btn-small"
                        onClick={() => {
                          setOverrideClaimId(Number(c.id));
                          setOverrideStatus(String(c.status));
                        }}
                        type="button"
                      >
                        ⚙️ Override / Moderate
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* TAB 3: LOST REPORTS */}
      {tab === "lost" && (
        <div className="admin-table-container">
          <h3>Lost Item Reports</h3>
          <table className="admin-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Item Name</th>
                <th>Category</th>
                <th>Campus</th>
                <th>Lost Date</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {lostList.map((item) => (
                <tr key={item.id}>
                  <td>#{item.id}</td>
                  <td><strong>{item.item_name}</strong></td>
                  <td>{item.category || "N/A"}</td>
                  <td>{item.campus || "N/A"}</td>
                  <td>{item.lost_date || "N/A"}</td>
                  <td>
                    <span className={`status-tag status-${item.status.toLowerCase()}`}>{item.status}</span>
                  </td>
                  <td>
                    {item.status !== "CLOSED" && (
                      <button
                        className="secondary-button btn-small"
                        disabled={submittingAction}
                        onClick={() => void handleModerateItem("lost", item.id, "CLOSED")}
                        type="button"
                      >
                        🚫 Close / Flag Spam
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* TAB 4: FOUND REPORTS */}
      {tab === "found" && (
        <div className="admin-table-container">
          <h3>Found Item Reports</h3>
          <table className="admin-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Item Name</th>
                <th>Category</th>
                <th>Campus</th>
                <th>Found Date</th>
                <th>AI Status</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {foundList.map((item) => (
                <tr key={item.id}>
                  <td>#{item.id}</td>
                  <td><strong>{item.item_name || "Unlabeled"}</strong></td>
                  <td>{item.category || "N/A"}</td>
                  <td>{item.campus || "N/A"}</td>
                  <td>{item.found_date}</td>
                  <td><span className="badge-ai">{item.analysis_status}</span></td>
                  <td>
                    <span className={`status-tag status-${item.status.toLowerCase()}`}>{item.status}</span>
                  </td>
                  <td>
                    {item.status !== "CLOSED" && (
                      <button
                        className="secondary-button btn-small"
                        disabled={submittingAction}
                        onClick={() => void handleModerateItem("found", item.id, "CLOSED")}
                        type="button"
                      >
                        🚫 Close / Flag Spam
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* TAB 5: USERS */}
      {tab === "users" && (
        <div className="admin-table-container">
          <h3>Registered Users &amp; Profiles</h3>
          <table className="admin-table">
            <thead>
              <tr>
                <th>User ID</th>
                <th>Name</th>
                <th>Email</th>
                <th>Roll No</th>
                <th>Role</th>
                <th>Reports</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {usersList.map((u) => (
                <tr key={u.id}>
                  <td>#{u.id}</td>
                  <td><strong>{u.full_name || "No Profile"}</strong></td>
                  <td>{u.email || u.firebase_uid.slice(0, 10)}</td>
                  <td>{u.roll_number || "N/A"}</td>
                  <td><span className="role-tag">{u.role}</span></td>
                  <td>Lost: {u.lost_count} · Found: {u.found_count}</td>
                  <td>
                    <span className={`status-tag status-${u.status.toLowerCase()}`}>{u.status}</span>
                  </td>
                  <td>
                    <button
                      className={u.status === "SUSPENDED" ? "primary-button btn-small" : "secondary-button btn-small"}
                      disabled={submittingAction || u.role === "ADMIN"}
                      onClick={() => void handleToggleUserStatus(u.id, u.status)}
                      type="button"
                    >
                      {u.status === "SUSPENDED" ? "✓ Reactivate" : "⛔ Suspend"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* TAB 6: AUDIT LOGS */}
      {tab === "audit" && (
        <div className="admin-table-container">
          <h3>Immutable System Audit History</h3>
          <table className="admin-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Timestamp</th>
                <th>Entity</th>
                <th>Entity ID</th>
                <th>Action</th>
                <th>Actor</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {auditLogs.map((log) => (
                <tr key={log.id}>
                  <td>#{log.id}</td>
                  <td>{log.created_at}</td>
                  <td><code>{log.entity_type}</code></td>
                  <td>#{log.entity_id}</td>
                  <td><strong>{log.action}</strong></td>
                  <td>{log.actor_email || (log.actor_user_id ? `User #${log.actor_user_id}` : "System")}</td>
                  <td className="log-details-col">
                    {log.details ? JSON.stringify(log.details) : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* CLAIM OVERRIDE MODAL */}
      {overrideClaimId !== null && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-card">
            <h3>Moderate Claim #{overrideClaimId}</h3>
            <p className="section-note">
              Override the claim lifecycle status as an administrator. This action is permanently recorded in the audit log.
            </p>

            <label>
              New Lifecycle Status
              <select
                value={overrideStatus}
                onChange={(e) => setOverrideStatus(e.target.value)}
              >
                <option value="APPROVED">APPROVED (Approve ownership)</option>
                <option value="REJECTED">REJECTED (Reject claim)</option>
                <option value="ADMIN_REVIEW">ADMIN_REVIEW (Escalate for dispute review)</option>
                <option value="RETURNED">RETURNED (Confirm physical return)</option>
                <option value="CLAIM_REQUESTED">CLAIM_REQUESTED (Reset to initial)</option>
              </select>
            </label>

            <label>
              Administrative Reason / Notes
              <textarea
                value={overrideNotes}
                onChange={(e) => setOverrideNotes(e.target.value)}
                placeholder="Explain the reason for this administrative decision..."
                rows={3}
                required
              />
            </label>

            <div className="modal-footer">
              <button
                className="secondary-button"
                disabled={submittingAction}
                onClick={() => setOverrideClaimId(null)}
                type="button"
              >
                Cancel
              </button>
              <button
                className="primary-button"
                disabled={submittingAction || !overrideNotes.trim()}
                onClick={() => void handleExecuteClaimOverride()}
                type="button"
              >
                {submittingAction ? "Applying..." : "Apply Override"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
