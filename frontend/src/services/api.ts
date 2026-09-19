const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export type AuthenticatedIdentity = {
  uid: string;
  email: string | null;
  email_verified: boolean;
};

export type StudentProfile = {
  id: number;
  firebase_uid: string;
  full_name: string;
  roll_number: string;
  class_section: string;
  course_program: string;
  semester: number;
  phone_number: string;
  university_email: string;
  campus: string;
  created_at: string;
  updated_at: string;
};

export type StudentProfileInput = Omit<
  StudentProfile,
  "id" | "firebase_uid" | "created_at" | "updated_at"
>;

export type LostItem = {
  id: number;
  status: string;
  item_name: string;
  category: string;
  color: string | null;
  brand: string | null;
  lost_date: string;
  approximate_location: string;
  description: string;
  distinctive_features: string | null;
  image_reference: string | null;
  created_at: string;
  updated_at: string;
};

export type LostItemInput = Omit<LostItem, "id" | "status" | "created_at" | "updated_at">;

export type FoundItem = {
  id: number;
  status: string;
  found_date: string;
  found_location: string | null;
  campus: string | null;
  image_reference: string | null;
  analysis_status: string;
  analysis_error: string | null;
  created_at: string;
  updated_at: string;
};

export async function getCurrentIdentity(
  idToken: string,
): Promise<AuthenticatedIdentity> {
  const response = await fetch(`${apiBaseUrl}/api/auth/me`, {
    headers: {
      Authorization: `Bearer ${idToken}`,
    },
  });

  if (!response.ok) {
    throw new Error("The backend could not verify your authentication.");
  }

  return response.json() as Promise<AuthenticatedIdentity>;
}

async function profileRequest(
  idToken: string,
  method: "GET" | "POST" | "PATCH",
  body?: StudentProfileInput,
): Promise<Response> {
  return fetch(`${apiBaseUrl}/api/profile`, {
    method,
    headers: {
      Authorization: `Bearer ${idToken}`,
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
}

export async function getMyProfile(idToken: string): Promise<StudentProfile | null> {
  const response = await profileRequest(idToken, "GET");
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error("The profile could not be loaded.");
  }
  return response.json() as Promise<StudentProfile>;
}

export async function saveMyProfile(
  idToken: string,
  profile: StudentProfileInput,
  exists: boolean,
): Promise<StudentProfile> {
  const response = await profileRequest(idToken, exists ? "PATCH" : "POST", profile);
  if (!response.ok) {
    throw new Error("The profile could not be saved.");
  }
  return response.json() as Promise<StudentProfile>;
}

export async function getMyLostItems(idToken: string): Promise<LostItem[]> {
  const response = await fetch(`${apiBaseUrl}/api/lost-items`, {
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw new Error("Lost reports could not be loaded.");
  }
  return response.json() as Promise<LostItem[]>;
}

export async function saveLostItem(
  idToken: string,
  item: LostItemInput,
  itemId?: number,
): Promise<LostItem> {
  const response = await fetch(
    `${apiBaseUrl}/api/lost-items${itemId ? `/${itemId}` : ""}`,
    {
      method: itemId ? "PATCH" : "POST",
      headers: {
        Authorization: `Bearer ${idToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(item),
    },
  );
  if (!response.ok) {
    throw new Error("Lost report could not be saved.");
  }
  return response.json() as Promise<LostItem>;
}

export async function deleteLostItem(idToken: string, itemId: number): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/lost-items/${itemId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw new Error("Lost report could not be deleted.");
  }
}

export async function uploadLostItemImage(
  idToken: string,
  itemId: number,
  image: File,
): Promise<LostItem> {
  const formData = new FormData();
  formData.append("image", image);
  const response = await fetch(`${apiBaseUrl}/api/lost-items/${itemId}/image`, {
    method: "POST",
    headers: { Authorization: `Bearer ${idToken}` },
    body: formData,
  });
  if (!response.ok) {
    throw new Error("Image could not be stored.");
  }
  return response.json() as Promise<LostItem>;
}

export async function createFoundItem(
  idToken: string,
  foundDate: string,
  foundLocation: string,
  campus: string,
): Promise<FoundItem> {
  const response = await fetch(`${apiBaseUrl}/api/found-items`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${idToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      found_date: foundDate,
      found_location: foundLocation || null,
      campus: campus || null,
    }),
  });
  if (!response.ok) {
    throw new Error("Found item could not be reported.");
  }
  return response.json() as Promise<FoundItem>;
}

export async function uploadFoundItemImage(
  idToken: string,
  itemId: number,
  image: File,
): Promise<FoundItem> {
  const formData = new FormData();
  formData.append("image", image);
  const response = await fetch(`${apiBaseUrl}/api/found-items/${itemId}/image`, {
    method: "POST",
    headers: { Authorization: `Bearer ${idToken}` },
    body: formData,
  });
  if (!response.ok) {
    throw new Error("Found-item image could not be stored.");
  }
  return response.json() as Promise<FoundItem>;
}

export async function triggerFoundItemAnalysis(
  idToken: string,
  itemId: number,
): Promise<{ found_item: FoundItem; accepted: boolean; message: string }> {
  const response = await fetch(`${apiBaseUrl}/api/found-items/${itemId}/analyze`, {
    method: "POST",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw new Error("Found-item analysis could not be started.");
  }
  return response.json() as Promise<{
    found_item: FoundItem;
    accepted: boolean;
    message: string;
  }>;
}
