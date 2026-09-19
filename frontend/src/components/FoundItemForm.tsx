import { useState, type FormEvent } from "react";

import { useAuth } from "../auth/AuthContext";
import {
  createFoundItem,
  triggerFoundItemAnalysis,
  uploadFoundItemImage,
  type FoundItem,
} from "../services/api";

export function FoundItemForm() {
  const { user } = useAuth();
  const [foundDate, setFoundDate] = useState("");
  const [foundLocation, setFoundLocation] = useState("");
  const [campus, setCampus] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [foundItem, setFoundItem] = useState<FoundItem | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const token = await user!.getIdToken();
      const created = await createFoundItem(token, foundDate, foundLocation, campus);
      const stored = image
        ? await uploadFoundItemImage(token, created.id, image)
        : created;
      setFoundItem(stored);
      if (stored.image_reference) {
        const analysis = await triggerFoundItemAnalysis(token, stored.id);
        setFoundItem(analysis.found_item);
        setMessage(analysis.message);
      } else {
        setMessage("Found item reported. Add a photo before requesting analysis.");
      }
    } catch {
      setError("The found item could not be reported. Check the details and image.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="profile-panel" aria-labelledby="found-items-title">
      <p className="eyebrow">Found items</p>
      <h2 id="found-items-title">Report an item you found</h2>
      <p className="profile-note">
        Your photo is stored securely. AI analysis is a separate step and remains optional when unavailable.
      </p>
      <form className="profile-form" onSubmit={handleSubmit}>
        <label>Found date<input required onChange={(event) => setFoundDate(event.target.value)} type="date" value={foundDate} /></label>
        <label>Found location<input maxLength={160} onChange={(event) => setFoundLocation(event.target.value)} value={foundLocation} /></label>
        <label>Campus<input maxLength={100} onChange={(event) => setCampus(event.target.value)} value={campus} /></label>
        <label>Found-item photo<input accept="image/jpeg,image/png,image/webp" onChange={(event) => setImage(event.target.files?.[0] ?? null)} required type="file" /></label>
        {error && <p className="error-message" role="alert">{error}</p>}
        {message && <p className="success-message" role="status">{message}</p>}
        <button className="primary-button" disabled={saving} type="submit">{saving ? "Reporting..." : "Report and analyze"}</button>
      </form>
      {foundItem && (
        <div className="identity-panel" role="status">
          <strong>Report status: {foundItem.status}</strong>
          <span>Analysis status: {foundItem.analysis_status}</span>
        </div>
      )}
    </section>
  );
}
