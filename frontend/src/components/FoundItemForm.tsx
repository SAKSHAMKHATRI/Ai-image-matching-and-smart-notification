import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";

import { useAuth } from "../auth/AuthContext";
import {
  ApiError,
  analyzeItemImage,
  createFoundItem,
  deleteFoundItem,
  getMyFoundItems,
  triggerFoundItemAnalysis,
  updateFoundItem,
  uploadFoundItemImage,
  type FoundItem,
  type FoundItemInput,
} from "../services/api";

type FoundItemFormProps = {
  /** Optional: when provided, shows a "Back" action above the form. */
  onBack?: () => void;
};

export function FoundItemForm({ onBack }: FoundItemFormProps = {}) {
  const { user } = useAuth();
  const [reports, setReports] = useState<FoundItem[]>([]);
  const [editingId, setEditingId] = useState<number | undefined>();

  const [foundDate, setFoundDate] = useState("");
  const [foundLocation, setFoundLocation] = useState("");
  const [campus, setCampus] = useState("");
  const [description, setDescription] = useState("");
  const [itemName, setItemName] = useState("");
  const [category, setCategory] = useState("");
  const [color, setColor] = useState("");
  const [brand, setBrand] = useState("");
  const [distinctiveFeatures, setDistinctiveFeatures] = useState("");
  const [aiAttributesJson, setAiAttributesJson] = useState<string | null>(null);

  const [image, setImage] = useState<File | null>(null);
  const [analyzingImage, setAnalyzingImage] = useState(false);
  const [aiStatusMessage, setAiStatusMessage] = useState<string | null>(null);
  const [aiUnavailable, setAiUnavailable] = useState(false);

  const [foundItem, setFoundItem] = useState<FoundItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function loadReports() {
    if (!user) return;
    const token = await user.getIdToken();
    setReports(await getMyFoundItems(token));
  }

  useEffect(() => {
    let active = true;
    void loadReports()
      .catch(() => {
        if (active) setError("Your found reports could not be loaded.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [user]);

  function resetForm() {
    setEditingId(undefined);
    setFoundDate("");
    setFoundLocation("");
    setCampus("");
    setDescription("");
    setItemName("");
    setCategory("");
    setColor("");
    setBrand("");
    setDistinctiveFeatures("");
    setAiAttributesJson(null);
    setImage(null);
    setAiStatusMessage(null);
  }

  function editReport(report: FoundItem) {
    setEditingId(report.id);
    setFoundDate(report.found_date);
    setFoundLocation(report.found_location || "");
    setCampus(report.campus || "");
    setDescription(report.description || "");
    setItemName(report.item_name || "");
    setCategory(report.category || "");
    setColor(report.color || "");
    setBrand(report.brand || "");
    setDistinctiveFeatures(report.distinctive_features || "");
    setAiAttributesJson(
      report.ai_attributes ? JSON.stringify(report.ai_attributes) : null,
    );
    setImage(null);
    setError(null);
    setMessage(null);
  }

  async function handleImageSelect(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    setImage(file);
    if (!file || !user) {
      return;
    }

    setAnalyzingImage(true);
    setAiStatusMessage(null);
    setAiUnavailable(false);
    try {
      const token = await user.getIdToken();
      const analysis = await analyzeItemImage(token, file);
      if (analysis.success) {
        if (analysis.description && !description) {
          setDescription(analysis.description);
        }
        if (analysis.item_name && !itemName) {
          setItemName(analysis.item_name);
        }
        if (analysis.category && !category) {
          setCategory(analysis.category);
        }
        if (analysis.color && !color) {
          setColor(analysis.color);
        }
        if (analysis.brand && !brand) {
          setBrand(analysis.brand);
        }
        if (analysis.distinctive_features && !distinctiveFeatures) {
          setDistinctiveFeatures(analysis.distinctive_features);
        }
        if (analysis.attributes) {
          setAiAttributesJson(JSON.stringify(analysis.attributes));
        }
        setAiStatusMessage(
          "AI analyzed the photo. You can edit any details below before submitting.",
        );
        setAiUnavailable(false);
      } else {
        setAiStatusMessage(
          analysis.message ||
            "AI analysis is unavailable; you can fill details manually.",
        );
        setAiUnavailable(true);
      }
    } catch {
      setAiStatusMessage(
        "AI analysis timed out or could not be completed; you can enter details manually.",
      );
      setAiUnavailable(true);
    } finally {
      setAnalyzingImage(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const token = await user!.getIdToken();
      const payload: FoundItemInput = {
        found_date: foundDate,
        found_location: foundLocation || null,
        campus: campus || null,
        item_name: itemName || null,
        category: category || null,
        color: color || null,
        brand: brand || null,
        description: description || null,
        distinctive_features: distinctiveFeatures || null,
        ai_attributes_json: aiAttributesJson || null,
      };

      if (editingId) {
        let updated = await updateFoundItem(token, editingId, payload);
        if (image) {
          updated = await uploadFoundItemImage(token, editingId, image);
        }
        setFoundItem(updated);
        await loadReports();
        resetForm();
        setMessage("Found report updated.");
      } else {
        const created = await createFoundItem(token, payload);
        let stored = created;
        if (image) {
          stored = await uploadFoundItemImage(token, created.id, image);
        }
        setFoundItem(stored);

        if (stored.image_reference && !stored.description) {
          try {
            const analysis = await triggerFoundItemAnalysis(token, stored.id);
            setFoundItem(analysis.found_item);
            setMessage(analysis.message);
          } catch {
            setMessage(
              "Found item reported successfully. (AI post-analysis unavailable).",
            );
          }
        } else {
          setMessage("Found item reported successfully.");
        }
        await loadReports();
        resetForm();
      }
    } catch (submitError) {
      setError(
        submitError instanceof ApiError
          ? submitError.message
          : "The found item could not be saved. Check the details and try again.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(itemId: number) {
    if (!window.confirm("Are you sure you want to delete this found report?")) {
      return;
    }
    setError(null);
    try {
      const token = await user!.getIdToken();
      await deleteFoundItem(token, itemId);
      await loadReports();
      if (editingId === itemId) {
        resetForm();
      }
      setMessage("Found report deleted.");
    } catch (deleteError) {
      setError(
        deleteError instanceof ApiError
          ? deleteError.message
          : "The found report could not be deleted.",
      );
    }
  }

  if (loading) {
    return <p role="status">Loading found reports...</p>;
  }

  return (
    <section className="profile-panel" aria-labelledby="found-items-title">
      <p className="eyebrow">Found items</p>
      <h2 id="found-items-title">
        {editingId ? "Edit found item report" : "Report an item you found"}
      </h2>
      <p className="profile-note">
        Upload a photo of the found item. AI will analyze the image and auto-fill
        details, which you can edit before submitting.
      </p>
      <form className="profile-form" onSubmit={handleSubmit}>
        <label>
          Found-item photo {editingId && "(Optional to replace)"}
          <input
            accept="image/jpeg,image/png,image/webp"
            onChange={handleImageSelect}
            required={!editingId}
            type="file"
          />
        </label>
        {analyzingImage && (
          <p className="ai-analyzing-badge" role="status">
            Analyzing photo with Microsoft Foundry AI...
          </p>
        )}
        {aiStatusMessage && (
          <p
            className={`ai-status-note ${aiUnavailable ? "unavailable" : ""}`}
            role="status"
          >
            {aiStatusMessage}
          </p>
        )}

        <label>
          Description
          <textarea
            maxLength={2000}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="e.g., Stainless steel water bottle found on library study table..."
            value={description}
          />
        </label>

        <label>
          Item name / object type
          <input
            maxLength={120}
            onChange={(event) => setItemName(event.target.value)}
            placeholder="e.g., Water bottle, Earbuds, Backpack"
            value={itemName}
          />
        </label>

        <label>
          Category
          <input
            maxLength={80}
            onChange={(event) => setCategory(event.target.value)}
            placeholder="e.g., Personal Items, Electronics, Bags"
            value={category}
          />
        </label>

        <label>
          Primary color
          <input
            maxLength={60}
            onChange={(event) => setColor(event.target.value)}
            placeholder="e.g., Black, Blue, Silver"
            value={color}
          />
        </label>

        <label>
          Brand (if visible)
          <input
            maxLength={80}
            onChange={(event) => setBrand(event.target.value)}
            placeholder="e.g., Hydro Flask, Apple, Nike"
            value={brand}
          />
        </label>

        <label>
          Distinctive features / visible text
          <textarea
            maxLength={1000}
            onChange={(event) => setDistinctiveFeatures(event.target.value)}
            placeholder="e.g., Scratch on bottom, campus stickers..."
            value={distinctiveFeatures}
          />
        </label>

        <label>
          Found date
          <input
            required
            onChange={(event) => setFoundDate(event.target.value)}
            type="date"
            value={foundDate}
          />
        </label>

        <label>
          Found location
          <input
            maxLength={160}
            onChange={(event) => setFoundLocation(event.target.value)}
            placeholder="e.g., Library 2nd floor east wing"
            value={foundLocation}
          />
        </label>

        <label>
          Campus
          <input
            maxLength={100}
            onChange={(event) => setCampus(event.target.value)}
            placeholder="e.g., Main Campus"
            value={campus}
          />
        </label>

        {error && (
          <p className="error-message" role="alert">
            {error}
          </p>
        )}
        {message && (
          <p className="success-message" role="status">
            {message}
          </p>
        )}

        <div className="button-row">
          {onBack && (
            <button className="secondary-button" onClick={onBack} type="button">
              ← Back
            </button>
          )}
          <button
            className="primary-button"
            disabled={saving || analyzingImage}
            type="submit"
          >
            {saving
              ? "Saving..."
              : editingId
                ? "Update report"
                : "Report found item"}
          </button>
          {editingId && (
            <button
              className="secondary-button"
              onClick={resetForm}
              type="button"
            >
              Cancel edit
            </button>
          )}
        </div>
      </form>

      {foundItem && (
        <div className="identity-panel" role="status">
          <strong>Report status: {foundItem.status}</strong>
          <span>Analysis status: {foundItem.analysis_status}</span>
          {foundItem.description && (
            <span>Description: {foundItem.description}</span>
          )}
        </div>
      )}

      <div className="report-list" aria-label="Your found reports">
        <h3>Your found reports</h3>
        {reports.length === 0 && (
          <p className="profile-note">No found reports yet.</p>
        )}
        {reports.map((report) => (
          <article className="report-row" key={report.id}>
            <div>
              <strong>
                {report.item_name || report.category || "Found item"}
              </strong>
              <span>
                {report.category || "Uncategorized"} · {report.status}
              </span>
              <span>
                {report.found_location || report.campus || report.found_date}
              </span>
            </div>
            <div className="button-row">
              <button
                className="secondary-button"
                onClick={() => editReport(report)}
                type="button"
              >
                Edit
              </button>
              <button
                className="secondary-button"
                onClick={() => void handleDelete(report.id)}
                type="button"
              >
                Delete
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
