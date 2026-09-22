import { useState, type ChangeEvent, type FormEvent } from "react";

import { useAuth } from "../auth/AuthContext";
import {
  ApiError,
  analyzeItemImage,
  createFoundItem,
  triggerFoundItemAnalysis,
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
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

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
        setAiStatusMessage("AI analyzed the photo. You can edit any details below before submitting.");
        setAiUnavailable(false);
      } else {
        setAiStatusMessage(analysis.message || "AI analysis is unavailable; you can fill details manually.");
        setAiUnavailable(true);
      }
    } catch {
      setAiStatusMessage("AI analysis timed out or could not be completed; you can enter details manually.");
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
          setMessage("Found item reported successfully. (AI post-analysis unavailable).");
        }
      } else {
        setMessage("Found item reported successfully.");
      }
    } catch (submitError) {
      setError(
        submitError instanceof ApiError
          ? submitError.message
          : "The found item could not be reported. Check the details and image.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="profile-panel" aria-labelledby="found-items-title">
      <p className="eyebrow">Found items</p>
      <h2 id="found-items-title">Report an item you found</h2>
      <p className="profile-note">
        Upload a photo of the found item. AI will analyze the image and auto-fill details, which you can edit before submitting.
      </p>
      <form className="profile-form" onSubmit={handleSubmit}>
        <label>
          Found-item photo
          <input
            accept="image/jpeg,image/png,image/webp"
            onChange={handleImageSelect}
            required
            type="file"
          />
        </label>
        {analyzingImage && (
          <p className="ai-analyzing-badge" role="status">
            Analyzing photo with Microsoft Foundry AI...
          </p>
        )}
        {aiStatusMessage && (
          <p className={`ai-status-note ${aiUnavailable ? "unavailable" : ""}`} role="status">
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

        {error && <p className="error-message" role="alert">{error}</p>}
        {message && <p className="success-message" role="status">{message}</p>}

        <div className="button-row">
          {onBack && (
            <button className="secondary-button" onClick={onBack} type="button">
              ← Back
            </button>
          )}
          <button className="primary-button" disabled={saving || analyzingImage} type="submit">
            {saving ? "Reporting..." : "Report found item"}
          </button>
        </div>
      </form>

      {foundItem && (
        <div className="identity-panel" role="status">
          <strong>Report status: {foundItem.status}</strong>
          <span>Analysis status: {foundItem.analysis_status}</span>
          {foundItem.description && <span>Description: {foundItem.description}</span>}
        </div>
      )}
    </section>
  );
}
