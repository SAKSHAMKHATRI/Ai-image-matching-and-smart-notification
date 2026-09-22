import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import {
  CANONICAL_BRANDS,
  CANONICAL_CATEGORIES,
  CANONICAL_COLORS,
} from "../constants/itemAttributes";
import {
  ApiError,
  getSearchSystemStatus,
  searchPublicFoundItems,
  searchPublicLostItems,
  type ManualSearchParams,
  type PublicFoundItem,
  type PublicLostItem,
  type SearchSystemStatus,
} from "../services/api";

const CAMPUS_OPTIONS = [
  "Main Campus",
  "North Campus",
  "South Campus",
  "East Campus",
  "West Campus",
  "Central Campus",
];

type ManualSearchBrowseProps = {
  onBack: () => void;
  onNavigateToLostReport?: () => void;
  onNavigateToFoundReport?: () => void;
};

type ActiveTab = "found" | "lost";

export function ManualSearchBrowse({
  onBack,
  onNavigateToLostReport,
  onNavigateToFoundReport,
}: ManualSearchBrowseProps) {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<ActiveTab>("found");

  // Filter form state
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [campus, setCampus] = useState("");
  const [location, setLocation] = useState("");
  const [color, setColor] = useState("");
  const [brand, setBrand] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  // Results state
  const [foundItems, setFoundItems] = useState<PublicFoundItem[]>([]);
  const [lostItems, setLostItems] = useState<PublicLostItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // System status
  const [systemStatus, setSystemStatus] = useState<SearchSystemStatus | null>(null);

  // Load status on mount
  useEffect(() => {
    let mounted = true;
    void (async () => {
      if (!user) return;
      try {
        const token = await user.getIdToken();
        const status = await getSearchSystemStatus(token);
        if (mounted) setSystemStatus(status);
      } catch {
        // Non-blocking fallback
      }
    })();
    return () => {
      mounted = false;
    };
  }, [user]);

  // Execute search
  const executeSearch = async (tab: ActiveTab = activeTab) => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const token = await user.getIdToken();
      const params: ManualSearchParams = {
        query: query.trim() || undefined,
        category: category || undefined,
        campus: campus || undefined,
        location: location.trim() || undefined,
        color: color || undefined,
        brand: brand || undefined,
        from_date: fromDate || undefined,
        to_date: toDate || undefined,
      };

      if (tab === "found") {
        const result = await searchPublicFoundItems(token, params);
        setFoundItems(result.items);
        setTotalCount(result.total);
      } else {
        const result = await searchPublicLostItems(token, params);
        setLostItems(result.items);
        setTotalCount(result.total);
      }
    } catch (searchError) {
      setError(
        searchError instanceof ApiError
          ? searchError.message
          : "Search could not be completed. Please check your connection."
      );
    } finally {
      setLoading(false);
    }
  };

  // Trigger search when activeTab changes
  useEffect(() => {
    void executeSearch(activeTab);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  const handleFilterSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void executeSearch(activeTab);
  };

  const handleResetFilters = () => {
    setQuery("");
    setCategory("");
    setCampus("");
    setLocation("");
    setColor("");
    setBrand("");
    setFromDate("");
    setToDate("");
    if (!user) return;
    setLoading(true);
    setError(null);
    void (async () => {
      try {
        const token = await user.getIdToken();
        if (activeTab === "found") {
          const res = await searchPublicFoundItems(token);
          setFoundItems(res.items);
          setTotalCount(res.total);
        } else {
          const res = await searchPublicLostItems(token);
          setLostItems(res.items);
          setTotalCount(res.total);
        }
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Reset failed.");
      } finally {
        setLoading(false);
      }
    })();
  };

  return (
    <div className="manual-search-view" data-testid="manual-search-view">
      <div className="search-header-row">
        <button
          className="secondary-button"
          onClick={onBack}
          type="button"
          data-testid="search-back-btn"
        >
          ← Back to Dashboard
        </button>
        <h1 className="search-title">🔍 Browse &amp; Manual Search</h1>
      </div>

      <p className="search-intro">
        Browse active lost and found items on campus, filter by structured attributes, or perform keyword queries.
      </p>

      {systemStatus && !systemStatus.ai_available && (
        <aside className="fallback-banner" role="status" data-testid="ai-fallback-indicator">
          <strong>⚡ Manual Fallback Active:</strong> AI assistance is currently in offline mode. Direct keyword and attribute search is fully available.
        </aside>
      )}

      {/* Tabs */}
      <div className="search-tab-bar" role="tablist" aria-label="Search Categories">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "found"}
          className={`search-tab ${activeTab === "found" ? "active" : ""}`}
          onClick={() => setActiveTab("found")}
          data-testid="tab-found-items"
        >
          📦 Found Items On Campus ({activeTab === "found" ? totalCount : "Browse"})
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "lost"}
          className={`search-tab ${activeTab === "lost" ? "active" : ""}`}
          onClick={() => setActiveTab("lost")}
          data-testid="tab-lost-items"
        >
          🔎 Lost Items Reported ({activeTab === "lost" ? totalCount : "Browse"})
        </button>
      </div>

      {/* Search & Filter Form */}
      <form
        className="search-filter-form"
        role="search"
        aria-label="Filter items"
        onSubmit={handleFilterSubmit}
      >
        <div className="filter-grid">
          <div className="filter-field filter-query">
            <label htmlFor="search-query-input">Keywords / Item Name</label>
            <input
              id="search-query-input"
              type="text"
              placeholder="e.g. blue backpack, Hydro Flask, calculator..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>

          <div className="filter-field">
            <label htmlFor="search-category-select">Category</label>
            <select
              id="search-category-select"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="">All Categories</option>
              {CANONICAL_CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-field">
            <label htmlFor="search-campus-select">Campus</label>
            <select
              id="search-campus-select"
              value={campus}
              onChange={(e) => setCampus(e.target.value)}
            >
              <option value="">All Campuses</option>
              {CAMPUS_OPTIONS.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-field">
            <label htmlFor="search-color-select">Primary Color</label>
            <select
              id="search-color-select"
              value={color}
              onChange={(e) => setColor(e.target.value)}
            >
              <option value="">All Colors</option>
              {CANONICAL_COLORS.map((col) => (
                <option key={col} value={col}>
                  {col}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-field">
            <label htmlFor="search-brand-select">Brand</label>
            <select
              id="search-brand-select"
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
            >
              <option value="">All Brands</option>
              {CANONICAL_BRANDS.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-field">
            <label htmlFor="search-from-date">From Date</label>
            <input
              id="search-from-date"
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
            />
          </div>

          <div className="filter-field">
            <label htmlFor="search-to-date">To Date</label>
            <input
              id="search-to-date"
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
            />
          </div>
        </div>

        <div className="filter-actions">
          <button
            type="submit"
            className="primary-button"
            disabled={loading}
            data-testid="search-submit-btn"
          >
            {loading ? "Searching..." : "Apply Filters"}
          </button>
          <button
            type="button"
            className="secondary-button"
            onClick={handleResetFilters}
            disabled={loading}
            data-testid="search-reset-btn"
          >
            Clear Filters
          </button>
        </div>
      </form>

      {/* Results Header */}
      <div className="search-results-summary">
        <h2>
          {activeTab === "found" ? "Found Items" : "Lost Reports"} ({totalCount}{" "}
          {totalCount === 1 ? "result" : "results"})
        </h2>
        {error && (
          <p className="error-message" role="alert">
            {error}
          </p>
        )}
      </div>

      {/* Results List */}
      {loading ? (
        <p className="loading-state" role="status">
          Loading items...
        </p>
      ) : totalCount === 0 ? (
        <div className="empty-search-state" data-testid="empty-search-state">
          <p>No {activeTab === "found" ? "found" : "lost"} items match your search criteria.</p>
          <div className="empty-actions">
            {activeTab === "found" && onNavigateToLostReport && (
              <button
                type="button"
                className="secondary-button"
                onClick={onNavigateToLostReport}
              >
                📝 Report Your Lost Item Instead
              </button>
            )}
            {activeTab === "lost" && onNavigateToFoundReport && (
              <button
                type="button"
                className="secondary-button"
                onClick={onNavigateToFoundReport}
              >
                📦 Report A Found Item Instead
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="search-results-grid" data-testid="search-results-grid">
          {activeTab === "found"
            ? foundItems.map((item) => (
                <article
                  key={`found-${item.id}`}
                  className="search-item-card"
                  data-testid={`found-card-${item.id}`}
                >
                  <div className="item-card-header">
                    <span className="item-badge found-badge">FOUND</span>
                    <span className="item-date">Date: {item.found_date || "Unknown"}</span>
                  </div>
                  <h3 className="item-title">{item.item_name || item.category || "Found Item"}</h3>
                  <div className="item-tags">
                    {item.category && <span className="tag category-tag">{item.category}</span>}
                    {item.color && <span className="tag color-tag">{item.color}</span>}
                    {item.brand && <span className="tag brand-tag">{item.brand}</span>}
                  </div>
                  <p className="item-location">
                    📍 {item.campus ? `${item.campus} — ` : ""}
                    {item.found_location || "Location not specified"}
                  </p>
                  {item.description && (
                    <p className="item-description">{item.description}</p>
                  )}
                  {item.distinctive_features && (
                    <p className="item-features">
                      <strong>Features:</strong> {item.distinctive_features}
                    </p>
                  )}
                  <div className="item-card-footer">
                    <span className="item-note">
                      💡 If this item belongs to you, log a lost report to connect with staff.
                    </span>
                  </div>
                </article>
              ))
            : lostItems.map((item) => (
                <article
                  key={`lost-${item.id}`}
                  className="search-item-card"
                  data-testid={`lost-card-${item.id}`}
                >
                  <div className="item-card-header">
                    <span className="item-badge lost-badge">LOST</span>
                    <span className="item-date">Date: {item.lost_date || "Unknown"}</span>
                  </div>
                  <h3 className="item-title">{item.item_name}</h3>
                  <div className="item-tags">
                    {item.category && <span className="tag category-tag">{item.category}</span>}
                    {item.color && <span className="tag color-tag">{item.color}</span>}
                    {item.brand && <span className="tag brand-tag">{item.brand}</span>}
                  </div>
                  <p className="item-location">
                    📍 {item.campus ? `${item.campus} — ` : ""}
                    {item.approximate_location || "Location not specified"}
                  </p>
                  {item.description && (
                    <p className="item-description">{item.description}</p>
                  )}
                  {item.distinctive_features && (
                    <p className="item-features">
                      <strong>Features:</strong> {item.distinctive_features}
                    </p>
                  )}
                  <div className="item-card-footer">
                    <span className="item-note">
                      🤝 If you found this item, please submit a found item report.
                    </span>
                  </div>
                </article>
              ))}
        </div>
      )}
    </div>
  );
}
