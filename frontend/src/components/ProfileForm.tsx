import { useEffect, useState, type FormEvent } from "react";

import {
  ApiError,
  getMyProfile,
  saveMyProfile,
  type FieldErrors,
  type StudentProfile,
  type StudentProfileInput,
} from "../services/api";
import { useAuth } from "../auth/AuthContext";

const emptyProfile: StudentProfileInput = {
  full_name: "",
  roll_number: "",
  class_section: "",
  course_program: "",
  semester: 1,
  phone_number: "",
  university_email: "",
  campus: "",
};

type ProfileField = keyof StudentProfileInput;

const fieldLabels: Record<ProfileField, string> = {
  full_name: "Full name",
  roll_number: "Roll number",
  class_section: "Class / section",
  course_program: "Course / program",
  semester: "Semester",
  phone_number: "Phone number",
  university_email: "University email",
  campus: "Campus",
};

/** Client-side checks that mirror the backend's Phase 2 validation rules. */
function validateProfile(profile: StudentProfileInput): FieldErrors {
  const errors: FieldErrors = {};
  const required: ProfileField[] = [
    "full_name",
    "roll_number",
    "class_section",
    "course_program",
    "phone_number",
    "university_email",
    "campus",
  ];
  for (const field of required) {
    if (!profile[field].toString().trim()) {
      errors[field] = `${fieldLabels[field]} is required.`;
    }
  }
  if (profile.full_name.trim() && profile.full_name.trim().length < 2) {
    errors.full_name = "Full name must be at least 2 characters.";
  }
  if (
    profile.university_email.trim() &&
    !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(profile.university_email.trim())
  ) {
    errors.university_email = "Enter a valid email address.";
  }
  if (profile.phone_number.trim() && !/^\+?[0-9][0-9 ()-]{5,18}[0-9]$/.test(profile.phone_number.trim())) {
    errors.phone_number = "Enter a valid phone number.";
  }
  if (!Number.isInteger(profile.semester) || profile.semester < 1 || profile.semester > 20) {
    errors.semester = "Semester must be a whole number between 1 and 20.";
  }
  return errors;
}

function fieldErrorFor(
  field: ProfileField,
  clientErrors: FieldErrors,
  apiFieldErrors: FieldErrors,
): string | null {
  return clientErrors[field] ?? apiFieldErrors[field] ?? null;
}

export function ProfileForm() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<StudentProfileInput>(emptyProfile);
  const [existingProfile, setExistingProfile] = useState<StudentProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [apiFieldErrors, setApiFieldErrors] = useState<FieldErrors>({});
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const token = await user!.getIdToken();
        const loadedProfile = await getMyProfile(token);
        if (!active) return;
        setExistingProfile(loadedProfile);
        if (loadedProfile) {
          setProfile({
            full_name: loadedProfile.full_name,
            roll_number: loadedProfile.roll_number,
            class_section: loadedProfile.class_section,
            course_program: loadedProfile.course_program,
            semester: loadedProfile.semester,
            phone_number: loadedProfile.phone_number,
            university_email: loadedProfile.university_email,
            campus: loadedProfile.campus,
          });
        }
      } catch (loadError) {
        if (active) {
          setError(
            loadError instanceof ApiError
              ? loadError.message
              : "Your profile could not be loaded.",
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

  function updateField(field: ProfileField, value: string) {
    setProfile((current) => ({
      ...current,
      [field]: field === "semester" ? Number(value) : value,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(null);

    const clientErrors = validateProfile(profile);
    setFieldErrors(clientErrors);
    setApiFieldErrors({});
    if (Object.keys(clientErrors).length > 0) {
      setSaving(false);
      return;
    }

    try {
      const token = await user!.getIdToken();
      const savedProfile = await saveMyProfile(
        token,
        profile,
        existingProfile !== null,
      );
      setExistingProfile(savedProfile);
      setSuccess("Profile saved.");
    } catch (saveError) {
      if (saveError instanceof ApiError) {
        setError(saveError.message);
        if (Object.keys(saveError.fieldErrors).length > 0) {
          setApiFieldErrors(saveError.fieldErrors);
        }
      } else {
        setError("The profile could not be saved. Check your connection and try again.");
      }
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p role="status">Loading profile...</p>;
  }

  const renderField = (
    field: ProfileField,
    inputProps: Record<string, string | number>,
  ) => {
    const message = fieldErrorFor(field, fieldErrors, apiFieldErrors);
    const describedBy = message ? `profile-${field}-error` : undefined;
    return (
      <label>
        {fieldLabels[field]}
        <input
          aria-describedby={describedBy}
          aria-invalid={message ? true : undefined}
          onChange={(event) => updateField(field, event.target.value)}
          value={profile[field] as string | number}
          {...inputProps}
        />
        {message && (
          <span className="field-error" id={`profile-${field}-error`} role="alert">
            {message}
          </span>
        )}
      </label>
    );
  };

  return (
    <section className="profile-panel" aria-labelledby="profile-title">
      <p className="eyebrow">Student profile</p>
      <h2 id="profile-title">Your university details</h2>
      <p className="profile-note">Your profile is private to your authenticated account.</p>
      <form className="profile-form" onSubmit={handleSubmit} noValidate>
        {renderField("full_name", { maxLength: 100 })}
        {renderField("roll_number", { maxLength: 50 })}
        {renderField("class_section", { maxLength: 100 })}
        {renderField("course_program", { maxLength: 150 })}
        {renderField("semester", { max: 20, min: 1, step: 1, type: "number" })}
        {renderField("phone_number", { maxLength: 20 })}
        {renderField("university_email", { type: "email", maxLength: 254 })}
        {renderField("campus", { maxLength: 100 })}
        {error && <p className="error-message" role="alert">{error}</p>}
        {success && <p className="success-message" role="status">{success}</p>}
        <button className="primary-button" disabled={saving} type="submit">{saving ? "Saving..." : "Save profile"}</button>
      </form>
    </section>
  );
}
