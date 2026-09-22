import { useEffect, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import {
  ApiError,
  evaluateMatches,
  getLostItemMatches,
  type FoundItem,
  type LostItem,
  type MatchSearchResponse,
  type ScoredMatchItem,
} from "../services/api";

type MatchResultsViewProps = {
  foundItem?: FoundItem | null;
  lostItem?: LostItem | null;
  onBack: () => void;
};

type FilterCategory = "all" | "strong" | "possible" | "low";

export function MatchResultsView({ foundItem, lostItem, onBack }: MatchResultsViewProps) {
  const { user } = useAuth();
  const [data, setData] = useState<MatchSearchResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterCategory>("all");
  const [selectedMatch, setSelectedMatch] = useState<ScoredMatchItem | null>(null);

  const isLostView = Boolean(lostItem);

  async function loadMatches(refresh = false) {
    if (!user) return;
    if (refresh) setEvaluating(true);
    else setLoading(true);
    setError(null);

    try {
      const token = await user.getIdToken();
      if (isLostView && lostItem) {
        const response = await getLostItemMatches(token, lostItem.id, refresh);
        setData(response);
      } else if (foundItem) {
        const response = await evaluateMatches(token, foundItem.id);
        setData(response);
      }
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Unable to retrieve match results at this time.",
      );
    } finally {
      setLoading(false);
      setEvaluating(false);
    }
  }

  useEffect(() => {
    void loadMatches();
  }, [foundItem?.id, lostItem?.id, user]);

  const matches = data?.matches || [];
  const filteredMatches = matches.filter((m) => {
    if (filter === "strong") return m.classification === "STRONG_CANDIDATE";
    if (filter === "possible") return m.classification === "POSSIBLE_CANDIDATE";
    if (filter === "low") return m.classification === "LOW_CONFIDENCE";
    return true;
  });

  const getBadgeClass = (classification: string) => {
    switch (classification) {
      case "STRONG_CANDIDATE":
        return "badge-strong";
      case "POSSIBLE_CANDIDATE":
        return "badge-possible";
      default:
        return "badge-low";
    }
  };

  return (
    <div className="match-results-container" data-testid="match-results-view">
      {/* Header & Item Context */}
      <div className="match-header">
        <button
          className="secondary-button back-btn"
          onClick={onBack}
          type="button"
        >
          ← Back
        </button>
        <div className="match-header-info">
          {isLostView && lostItem ? (
            <>
              <h2>Potential Matches for Lost Item #{lostItem.id}</h2>
              <p className="found-context-summary">
                <strong>Lost:</strong> {lostItem.item_name || "Unlabeled item"}{" "}
                {lostItem.category ? `· ${lostItem.category}` : ""}{" "}
                {lostItem.campus ? `· ${lostItem.campus}` : ""} on{" "}
                {lostItem.lost_date}
              </p>
            </>
          ) : foundItem ? (
            <>
              <h2>Potential Matches for Found Item #{foundItem.id}</h2>
              <p className="found-context-summary">
                <strong>Found:</strong> {foundItem.item_name || "Unlabeled item"}{" "}
                {foundItem.category ? `· ${foundItem.category}` : ""}{" "}
                {foundItem.campus ? `· ${foundItem.campus}` : ""} on{" "}
                {foundItem.found_date}
              </p>
            </>
          ) : null}
        </div>
        <button
          className="secondary-button refresh-btn"
          disabled={loading || evaluating}
          onClick={() => void loadMatches(true)}
          type="button"
        >
          {evaluating ? "Scanning..." : "Re-evaluate"}
        </button>
      </div>

      {/* Safety & Legal Disclaimer */}
      <div className="disclaimer-banner" role="note">
        <span className="disclaimer-icon">ℹ️</span>
        <div className="disclaimer-text">
          <strong>Review Notice:</strong> Match confidence is computed from visual,
          textual, and metadata compatibility. Scores are for candidate ranking and
          review only and do not establish proof of ownership.
        </div>
      </div>

      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}

      {loading ? (
        <div className="loading-state" role="status">
          <p>Analyzing candidate matches across campus records...</p>
        </div>
      ) : (
        <>
          {/* Filter Bar & Match Counters */}
          {data && data.total_matches > 0 && (
            <div className="match-filter-bar">
              <div className="filter-chips">
                <button
                  className={`chip ${filter === "all" ? "active" : ""}`}
                  onClick={() => setFilter("all")}
                  type="button"
                >
                  All ({data.total_matches})
                </button>
                <button
                  className={`chip chip-strong ${filter === "strong" ? "active" : ""}`}
                  onClick={() => setFilter("strong")}
                  type="button"
                >
                  Strong ({data.strong_matches_count})
                </button>
                <button
                  className={`chip chip-possible ${filter === "possible" ? "active" : ""}`}
                  onClick={() => setFilter("possible")}
                  type="button"
                >
                  Possible ({data.possible_matches_count})
                </button>
                <button
                  className={`chip chip-low ${filter === "low" ? "active" : ""}`}
                  onClick={() => setFilter("low")}
                  type="button"
                >
                  Low ({data.low_confidence_count})
                </button>
              </div>
            </div>
          )}

          {/* Empty State Fallback */}
          {matches.length === 0 ? (
            <div className="empty-matches-card" data-testid="empty-matches">
              <div className="empty-icon">🔍</div>
              <h3>
                {isLostView
                  ? "No matching found items discovered yet"
                  : "No matching lost items found"}
              </h3>
              <p>
                {isLostView
                  ? "We could not find any active found-item reports matching this lost item's category, location, or visual attributes."
                  : "We could not find any active lost-item reports matching this found item's category, location, or visual attributes."}
              </p>
              <p className="sub-text">
                {isLostView
                  ? "When someone reports a found item matching your report, it will automatically appear here."
                  : "When students report newly lost items matching this report, they will automatically be evaluated here."}
              </p>
            </div>
          ) : filteredMatches.length === 0 ? (
            <div className="empty-matches-card">
              <p>No matches found in the "{filter}" category.</p>
              <button
                className="secondary-button"
                onClick={() => setFilter("all")}
                type="button"
              >
                Show All Matches
              </button>
            </div>
          ) : (
            <>
              {/* All low confidence fallback warning */}
              {data &&
                data.strong_matches_count === 0 &&
                data.possible_matches_count === 0 && (
                  <div className="warning-callout" role="alert">
                    <strong>Low Confidence Results:</strong> None of the available
                    candidates exceed the 70% threshold. Please perform thorough physical
                    verification before proceeding.
                  </div>
                )}

              {/* Match Cards List */}
              <div className="matches-grid">
                {filteredMatches.map((match) => {
                  const cardId = isLostView
                    ? (match.found_item_id || match.id)
                    : (match.lost_item_id || match.id);
                  return (
                    <article
                      className="match-card"
                      data-testid={`match-card-${cardId}`}
                      key={`match-${cardId}-${match.match_id}`}
                    >
                      <div className="match-card-header">
                        <div className="match-title-area">
                          <span className="lost-tag">
                            {isLostView
                              ? `Found Report #${match.found_item_id || match.id}`
                              : `Lost Report #${match.lost_item_id || match.id}`}
                          </span>
                          <h3 className="match-item-name">{match.item_name}</h3>
                        </div>
                        <div className={`score-badge ${getBadgeClass(match.classification)}`}>
                          <span className="score-number">{match.score_percent}%</span>
                          <span className="score-label">{match.classification_label}</span>
                        </div>
                      </div>

                      {/* Key safe attributes */}
                      <dl className="match-attributes-grid">
                        {match.category && (
                          <div>
                            <dt>Category</dt>
                            <dd>{match.category}</dd>
                          </div>
                        )}
                        {match.brand && (
                          <div>
                            <dt>Brand</dt>
                            <dd>{match.brand}</dd>
                          </div>
                        )}
                        {match.color && (
                          <div>
                            <dt>Color</dt>
                            <dd>{match.color}</dd>
                          </div>
                        )}
                        {match.campus && (
                          <div>
                            <dt>Campus</dt>
                            <dd>{match.campus}</dd>
                          </div>
                        )}
                        {(match.found_location || match.approximate_location) && (
                          <div>
                            <dt>{isLostView ? "Found Near" : "Lost Near"}</dt>
                            <dd>{match.found_location || match.approximate_location}</dd>
                          </div>
                        )}
                        {(match.found_date || match.lost_date) && (
                          <div>
                            <dt>{isLostView ? "Date Found" : "Date Lost"}</dt>
                            <dd>{match.found_date || match.lost_date}</dd>
                          </div>
                        )}
                      </dl>

                      {match.description && (
                        <p className="match-description">{match.description}</p>
                      )}

                      {match.distinctive_features && (
                        <div className="distinctive-box">
                          <strong>Distinctive Features:</strong>{" "}
                          {match.distinctive_features}
                        </div>
                      )}

                      {/* Explanations Section */}
                      {match.reasons && match.reasons.length > 0 && (
                        <div className="match-reasons-section">
                          <h4>Why this is being suggested:</h4>
                          <ul className="reasons-list">
                            {match.reasons.map((reason, idx) => (
                              <li key={idx}>
                                <span className="check-icon">✓</span> {reason}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Action buttons */}
                      <div className="match-card-actions">
                        <button
                          className="secondary-button detail-btn"
                          onClick={() => setSelectedMatch(match)}
                          type="button"
                        >
                          View Breakdown &amp; Details
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
            </>
          )}
        </>
      )}

      {/* Detail Modal */}
      {selectedMatch && (
        <div
          className="modal-backdrop"
          onClick={() => setSelectedMatch(null)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="modal-content match-detail-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <h3>Match Detail — {selectedMatch.item_name}</h3>
              <button
                className="close-btn"
                onClick={() => setSelectedMatch(null)}
                type="button"
                aria-label="Close detail modal"
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              <div className="detail-score-summary">
                <div
                  className={`score-badge large ${getBadgeClass(selectedMatch.classification)}`}
                >
                  <span className="score-number">{selectedMatch.score_percent}%</span>
                  <span className="score-label">
                    {selectedMatch.classification_label}
                  </span>
                </div>
                <p className="detail-disclaimer">
                  Deterministic score calculated from multi-signal analysis.
                </p>
              </div>

              {/* Component breakdown */}
              {selectedMatch.components && (
                <div className="components-breakdown">
                  <h4>Component Score Breakdown</h4>
                  <table className="breakdown-table">
                    <thead>
                      <tr>
                        <th>Component</th>
                        <th>Raw Score</th>
                        <th>Weight</th>
                        <th>Contribution</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(selectedMatch.components).map(([key, comp]) => (
                        <tr key={key}>
                          <td className="comp-name">
                            {key === "image_text"
                              ? "Image / Text Semantic"
                              : key === "lost_image"
                              ? "Lost Image Similarity"
                              : key === "attributes"
                              ? "Attribute Matching"
                              : key === "location"
                              ? "Location Compatibility"
                              : key === "date"
                              ? "Date Compatibility"
                              : key}
                          </td>
                          <td>{(comp.score * 100).toFixed(1)}%</td>
                          <td>{(comp.weight * 100).toFixed(0)}%</td>
                          <td><strong>{(comp.contribution * 100).toFixed(1)}%</strong></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Explanations */}
              {selectedMatch.reasons && selectedMatch.reasons.length > 0 && (
                <div className="detail-reasons">
                  <h4>Explanation Factors</h4>
                  <ul>
                    {selectedMatch.reasons.map((r, i) => (
                      <li key={i}>
                        <span className="check-icon">✓</span> {r}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Safe metadata */}
              <div className="detail-metadata">
                <h4>Safe Item Information</h4>
                <p className="privacy-note">
                  🔒 Private student identity data (phone, email, roll number) is
                  protected and hidden.
                </p>
                <dl className="meta-list">
                  <div>
                    <dt>Report ID</dt>
                    <dd>
                      {isLostView
                        ? `Found #${selectedMatch.found_item_id || selectedMatch.id}`
                        : `Lost #${selectedMatch.lost_item_id || selectedMatch.id}`}
                    </dd>
                  </div>
                  <div>
                    <dt>Item Name</dt>
                    <dd>{selectedMatch.item_name}</dd>
                  </div>
                  <div>
                    <dt>Category</dt>
                    <dd>{selectedMatch.category || "Not specified"}</dd>
                  </div>
                  <div>
                    <dt>Campus</dt>
                    <dd>{selectedMatch.campus || "Not specified"}</dd>
                  </div>
                  <div>
                    <dt>Location</dt>
                    <dd>
                      {selectedMatch.found_location ||
                        selectedMatch.approximate_location ||
                        "Not specified"}
                    </dd>
                  </div>
                  <div>
                    <dt>{isLostView ? "Found Date" : "Lost Date"}</dt>
                    <dd>
                      {selectedMatch.found_date ||
                        selectedMatch.lost_date ||
                        "Not specified"}
                    </dd>
                  </div>
                </dl>
              </div>
            </div>

            <div className="modal-footer">
              <button
                className="secondary-button"
                onClick={() => setSelectedMatch(null)}
                type="button"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
