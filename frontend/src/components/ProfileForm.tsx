import { useEffect, useState, type FormEvent } from "react";

import {
  getMyProfile,
  saveMyProfile,
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

export function ProfileForm() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<StudentProfileInput>(emptyProfile);
  const [existingProfile, setExistingProfile] = useState<StudentProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
      } catch {
        if (active) setError("Your profile could not be loaded.");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [user]);

  function updateField(field: keyof StudentProfileInput, value: string) {
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
    try {
      const token = await user!.getIdToken();
      const savedProfile = await saveMyProfile(
        token,
        profile,
        existingProfile !== null,
      );
      setExistingProfile(savedProfile);
      setSuccess("Profile saved.");
    } catch {
      setError("Check the profile details and try again.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p role="status">Loading profile...</p>;
  }

  return (
    <section className="profile-panel" aria-labelledby="profile-title">
      <p className="eyebrow">Student profile</p>
      <h2 id="profile-title">Your university details</h2>
      <p className="profile-note">Your profile is private to your authenticated account.</p>
      <form className="profile-form" onSubmit={handleSubmit}>
        <label>Full name<input required maxLength={100} onChange={(event) => updateField("full_name", event.target.value)} value={profile.full_name} /></label>
        <label>Roll number<input required maxLength={50} onChange={(event) => updateField("roll_number", event.target.value)} value={profile.roll_number} /></label>
        <label>Class / section<input required maxLength={100} onChange={(event) => updateField("class_section", event.target.value)} value={profile.class_section} /></label>
        <label>Course / program<input required maxLength={150} onChange={(event) => updateField("course_program", event.target.value)} value={profile.course_program} /></label>
        <label>Semester<input max={20} min={1} onChange={(event) => updateField("semester", event.target.value)} required type="number" value={profile.semester} /></label>
        <label>Phone number<input required maxLength={20} onChange={(event) => updateField("phone_number", event.target.value)} value={profile.phone_number} /></label>
        <label>University email<input required maxLength={254} onChange={(event) => updateField("university_email", event.target.value)} type="email" value={profile.university_email} /></label>
        <label>Campus<input required maxLength={100} onChange={(event) => updateField("campus", event.target.value)} value={profile.campus} /></label>
        {error && <p className="error-message" role="alert">{error}</p>}
        {success && <p className="success-message" role="status">{success}</p>}
        <button className="primary-button" disabled={saving} type="submit">{saving ? "Saving..." : "Save profile"}</button>
      </form>
    </section>
  );
}
