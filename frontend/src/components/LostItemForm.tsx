import { useEffect, useState, type FormEvent } from "react";

import { useAuth } from "../auth/AuthContext";
import {
  CANONICAL_BRANDS,
  CANONICAL_CATEGORIES,
  CANONICAL_COLORS,
  CANONICAL_LOCATIONS,
} from "../constants/itemAttributes";
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
  const [customBrandMode, setCustomBrandMode] = useState(false);
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
    const isCustom = Boolean(
      report.brand &&
        !CANONICAL_BRANDS.includes(report.brand as (typeof CANONICAL_BRANDS)[number]) &&
        report.brand !== "Other",
    );
    setCustomBrandMode(isCustom);
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
      let imageUploadFailed = false;
      let imageErrorMessage = "";
      if (selectedImage) {
        try {
          await uploadLostItemImage(token, savedItem.id, selectedImage);
        } catch (imgErr) {
          imageUploadFailed = true;
          imageErrorMessage =
            imgErr instanceof ApiError
              ? imgErr.message
              : "Image storage is temporarily unavailable.";
        }
      }
      await loadReports();
      setItem(emptyItem);
      setEditingId(undefined);
      setCustomBrandMode(false);
      setSelectedImage(null);
      if (imageUploadFailed) {
        setSuccess(
          `Lost report ${editingId ? "updated" : "created"}, but image upload failed (${imageErrorMessage}).`,
        );
      } else {
        setSuccess(editingId ? "Lost report updated." : "Lost report created.");
      }
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
    if (!window.confirm("Are you sure you want to delete this lost report?")) {
      return;
    }
    setError(null);
    try {
      const token = await user!.getIdToken();
      await deleteLostItem(token, itemId);
      await loadReports();
      if (editingId === itemId) {
        setItem(emptyItem);
        setEditingId(undefined);
        setCustomBrandMode(false);
      }
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
        <label>
          Item name
          <input
            required
            maxLength={120}
            onChange={(event) => updateField("item_name", event.target.value)}
            placeholder="e.g., Hydro Flask Water Bottle, Navy Backpack"
            value={item.item_name}
          />
        </label>

        <label>
          Category
          <select
            required
            aria-label="Category"
            onChange={(event) => updateField("category", event.target.value)}
            value={item.category}
          >
            <option value="">Select a category</option>
            {item.category &&
              !CANONICAL_CATEGORIES.includes(
                item.category as (typeof CANONICAL_CATEGORIES)[number],
              ) && (
                <option value={item.category}>{item.category}</option>
              )}
            {CANONICAL_CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </label>

        <label>
          Color
          <select
            aria-label="Color"
            onChange={(event) => updateField("color", event.target.value)}
            value={item.color ?? ""}
          >
            <option value="">Select primary color (optional)</option>
            {item.color &&
              !CANONICAL_COLORS.includes(
                item.color as (typeof CANONICAL_COLORS)[number],
              ) && <option value={item.color}>{item.color}</option>}
            {CANONICAL_COLORS.map((col) => (
              <option key={col} value={col}>
                {col}
              </option>
            ))}
          </select>
        </label>

        <label>
          Brand
          <select
            aria-label="Brand"
            onChange={(event) => {
              const val = event.target.value;
              if (val === "OTHER_SPECIFY") {
                setCustomBrandMode(true);
                updateField("brand", "");
              } else {
                setCustomBrandMode(false);
                updateField("brand", val);
              }
            }}
            value={
              customBrandMode
                ? "OTHER_SPECIFY"
                : item.brand &&
                    !CANONICAL_BRANDS.includes(
                      item.brand as (typeof CANONICAL_BRANDS)[number],
                    )
                  ? item.brand
                  : (item.brand ?? "")
            }
          >
            <option value="">Select brand (optional)</option>
            {item.brand &&
              !customBrandMode &&
              !CANONICAL_BRANDS.includes(
                item.brand as (typeof CANONICAL_BRANDS)[number],
              ) && <option value={item.brand}>{item.brand}</option>}
            {CANONICAL_BRANDS.map((br) => (
              <option key={br} value={br === "Other" ? "OTHER_SPECIFY" : br}>
                {br === "Other" ? "Other (specify below)" : br}
              </option>
            ))}
          </select>
        </label>

        {customBrandMode && (
          <label>
            Specify brand name
            <input
              aria-label="Specify brand name"
              maxLength={80}
              onChange={(event) => updateField("brand", event.target.value)}
              placeholder="e.g., Herschel, Jansport, Dell"
              value={item.brand ?? ""}
            />
          </label>
        )}

        <label>
          Lost date
          <input
            required
            onChange={(event) => updateField("lost_date", event.target.value)}
            type="date"
            value={item.lost_date}
          />
        </label>

        <label>
          Approximate location
          <select
            required
            aria-label="Approximate location"
            onChange={(event) =>
              updateField("approximate_location", event.target.value)
            }
            value={item.approximate_location}
          >
            <option value="">Select approximate location</option>
            {item.approximate_location &&
              !CANONICAL_LOCATIONS.includes(
                item.approximate_location as (typeof CANONICAL_LOCATIONS)[number],
              ) && (
                <option value={item.approximate_location}>
                  {item.approximate_location}
                </option>
              )}
            {CANONICAL_LOCATIONS.map((loc) => (
              <option key={loc} value={loc}>
                {loc}
              </option>
            ))}
          </select>
        </label>

        <label>
          Description
          <textarea
            required
            maxLength={2000}
            minLength={10}
            onChange={(event) => updateField("description", event.target.value)}
            placeholder="Provide a detailed description of the lost item..."
            value={item.description}
          />
        </label>

        <label>
          Distinctive features
          <textarea
            maxLength={1000}
            onChange={(event) =>
              updateField("distinctive_features", event.target.value)
            }
            placeholder="e.g., Stickers on back, small scratch near corner, keychains..."
            value={item.distinctive_features ?? ""}
          />
        </label>

        <label>
          Optional image
          <input
            accept="image/jpeg,image/png,image/webp"
            onChange={(event) =>
              setSelectedImage(event.target.files?.[0] ?? null)
            }
            type="file"
          />
        </label>

        {error && (
          <p className="error-message" role="alert">
            {error}
          </p>
        )}
        {success && (
          <p className="success-message" role="status">
            {success}
          </p>
        )}

        <div className="button-row">
          {onBack && (
            <button className="secondary-button" onClick={onBack} type="button">
              ← Back
            </button>
          )}
          <button className="primary-button" disabled={saving} type="submit">
            {saving
              ? "Saving..."
              : editingId
                ? "Update report"
                : "Create report"}
          </button>
          {editingId && (
            <button
              className="secondary-button"
              onClick={() => {
                setEditingId(undefined);
                setCustomBrandMode(false);
                setItem(emptyItem);
              }}
              type="button"
            >
              Cancel edit
            </button>
          )}
        </div>
      </form>

      <div className="report-list" aria-label="Your lost reports">
        <h3>Your reports</h3>
        {reports.length === 0 && (
          <p className="profile-note">No lost reports yet.</p>
        )}
        {reports.map((report) => (
          <article className="report-row" key={report.id}>
            <div>
              <strong>{report.item_name}</strong>
              <span>
                {report.category} · {report.status}
              </span>
              <span>{report.approximate_location}</span>
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
