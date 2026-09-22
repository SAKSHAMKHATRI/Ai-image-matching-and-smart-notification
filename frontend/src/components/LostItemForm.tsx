import { useEffect, useState, type FormEvent } from "react";

import { useAuth } from "../auth/AuthContext";
import {
  ApiError,
  deleteLostItem,
  getMyLostItems,
  saveLostItem,
  uploadLostItemImage,
  type LostItem,
  type LostItemInput,
} from "../services/api";

const emptyItem: LostItemInput = {
  item_name: "",
  category: "",
  color: null,
  brand: null,
  lost_date: "",
  approximate_location: "",
  description: "",
  distinctive_features: null,
  image_reference: null,
};

type LostItemFormProps = {
  /** Optional: when provided, shows a "Back" action above the form. */
  onBack?: () => void;
};

export function LostItemForm({ onBack }: LostItemFormProps = {}) {
  const { user } = useAuth();
  const [reports, setReports] = useState<LostItem[]>([]);
  const [item, setItem] = useState<LostItemInput>(emptyItem);
  const [editingId, setEditingId] = useState<number | undefined>();
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function loadReports() {
    const token = await user!.getIdToken();
    setReports(await getMyLostItems(token));
  }

  useEffect(() => {
    let active = true;
    void loadReports()
      .catch(() => {
        if (active) setError("Your lost reports could not be loaded.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [user]);

  function updateField(field: keyof LostItemInput, value: string) {
    setItem((current) => ({ ...current, [field]: value || null }));
  }

  function editReport(report: LostItem) {
    setEditingId(report.id);
    setItem({
      item_name: report.item_name,
      category: report.category,
      color: report.color,
      brand: report.brand,
      lost_date: report.lost_date,
      approximate_location: report.approximate_location,
      description: report.description,
      distinctive_features: report.distinctive_features,
      image_reference: report.image_reference,
    });
    setSuccess(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const token = await user!.getIdToken();
      const savedItem = await saveLostItem(token, item, editingId);
      if (selectedImage) {
        await uploadLostItemImage(token, savedItem.id, selectedImage);
      }
      await loadReports();
      setItem(emptyItem);
      setEditingId(undefined);
      setSelectedImage(null);
      setSuccess(editingId ? "Lost report updated." : "Lost report created.");
    } catch (submitError) {
      setError(
        submitError instanceof ApiError
          ? submitError.message
          : "Check the report details and try again.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(itemId: number) {
    setError(null);
    try {
      const token = await user!.getIdToken();
      await deleteLostItem(token, itemId);
      await loadReports();
      setSuccess("Lost report deleted.");
    } catch (deleteError) {
      setError(
        deleteError instanceof ApiError
          ? deleteError.message
          : "The lost report could not be deleted.",
      );
    }
  }

  if (loading) {
    return <p role="status">Loading lost reports...</p>;
  }

  return (
    <section className="profile-panel" aria-labelledby="lost-items-title">
      <p className="eyebrow">Lost items</p>
      <h2 id="lost-items-title">Report a lost item</h2>
      <p className="profile-note">
        JPEG, PNG, and WebP images up to 5 MB are stored in protected Firebase Storage.
      </p>
      <form className="profile-form" onSubmit={handleSubmit}>
        <label>Item name<input required maxLength={120} onChange={(event) => updateField("item_name", event.target.value)} value={item.item_name} /></label>
        <label>Category<input required maxLength={80} onChange={(event) => updateField("category", event.target.value)} value={item.category} /></label>
        <label>Color<input maxLength={60} onChange={(event) => updateField("color", event.target.value)} value={item.color ?? ""} /></label>
        <label>Brand<input maxLength={80} onChange={(event) => updateField("brand", event.target.value)} value={item.brand ?? ""} /></label>
        <label>Lost date<input required onChange={(event) => updateField("lost_date", event.target.value)} type="date" value={item.lost_date} /></label>
        <label>Approximate location<input required maxLength={160} onChange={(event) => updateField("approximate_location", event.target.value)} value={item.approximate_location} /></label>
        <label>Description<textarea required maxLength={2000} minLength={10} onChange={(event) => updateField("description", event.target.value)} value={item.description} /></label>
        <label>Distinctive features<textarea maxLength={1000} onChange={(event) => updateField("distinctive_features", event.target.value)} value={item.distinctive_features ?? ""} /></label>
        <label>Optional image<input accept="image/jpeg,image/png,image/webp" onChange={(event) => setSelectedImage(event.target.files?.[0] ?? null)} type="file" /></label>
        {error && <p className="error-message" role="alert">{error}</p>}
        {success && <p className="success-message" role="status">{success}</p>}
      <div className="button-row">
        {onBack && (
          <button className="secondary-button" onClick={onBack} type="button">
            ← Back
          </button>
        )}
        <button className="primary-button" disabled={saving} type="submit">{saving ? "Saving..." : editingId ? "Update report" : "Create report"}</button>
        {editingId && <button className="secondary-button" onClick={() => { setEditingId(undefined); setItem(emptyItem); }} type="button">Cancel edit</button>}
      </div>
      </form>
      <div className="report-list" aria-label="Your lost reports">
        <h3>Your reports</h3>
        {reports.length === 0 && <p className="profile-note">No lost reports yet.</p>}
        {reports.map((report) => (
          <article className="report-row" key={report.id}>
            <div>
              <strong>{report.item_name}</strong>
              <span>{report.category} · {report.status}</span>
              <span>{report.approximate_location}</span>
            </div>
            <div className="button-row">
              <button className="secondary-button" onClick={() => editReport(report)} type="button">Edit</button>
              <button className="secondary-button" onClick={() => void handleDelete(report.id)} type="button">Delete</button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
