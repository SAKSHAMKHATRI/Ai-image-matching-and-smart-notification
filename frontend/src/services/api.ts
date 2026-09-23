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
  role?: string;
  created_at: string;
  updated_at: string;
};

export type StudentProfileInput = Omit<
  StudentProfile,
  "id" | "firebase_uid" | "created_at" | "updated_at" | "role"
>;

export type LostItem = {
  id: number;
  status: string;
  item_name: string;
  category: string;
  color: string | null;
  brand: string | null;
  campus?: string | null;
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
  item_name?: string | null;
  category?: string | null;
  color?: string | null;
  brand?: string | null;
  description?: string | null;
  distinctive_features?: string | null;
  image_reference: string | null;
  ai_attributes?: Record<string, unknown> | null;
  analysis_status: string;
  analysis_error: string | null;
  created_at: string;
  updated_at: string;
};

export type FoundItemInput = {
  found_date: string;
  found_location?: string | null;
  campus?: string | null;
  item_name?: string | null;
  category?: string | null;
  color?: string | null;
  brand?: string | null;
  description?: string | null;
  distinctive_features?: string | null;
  ai_attributes_json?: string | null;
};

export type ImageAnalysisResult = {
  success: boolean;
  message: string;
  description?: string | null;
  item_name?: string | null;
  category?: string | null;
  color?: string | null;
  brand?: string | null;
  distinctive_features?: string | null;
  attributes?: Record<string, unknown> | null;
};

export type MatchComponentScore = {
  score: number;
  weight: number;
  contribution: number;
};

export type ScoredMatchItem = {
  id: number;
  lost_item_id?: number;
  found_item_id?: number;
  match_id?: number | null;
  status: string;
  item_name: string;
  category?: string | null;
  color?: string | null;
  brand?: string | null;
  campus?: string | null;
  lost_date?: string | null;
  found_date?: string | null;
  approximate_location?: string | null;
  found_location?: string | null;
  description?: string | null;
  distinctive_features?: string | null;
  image_reference?: string | null;
  finder_name?: string | null;
  found_by?: string | null;
  lost_item_name?: string | null;
  score: number;
  score_percent: number;
  classification: "STRONG_CANDIDATE" | "POSSIBLE_CANDIDATE" | "LOW_CONFIDENCE" | string;
  classification_label: string;
  reasons: string[];
  components?: Record<string, MatchComponentScore>;
  created_at: string;
};

export type MatchSearchResponse = {
  found_item_id?: number | null;
  lost_item_id?: number | null;
  matches: ScoredMatchItem[];
  total_matches: number;
  strong_matches_count: number;
  possible_matches_count: number;
  low_confidence_count: number;
  disclaimer: string;
};



/** Field-level validation messages returned by the backend (FastAPI 422). */
export type FieldErrors = Partial<Record<string, string>>;

/** Error carrying the backend's actual message plus optional field errors. */
export class ApiError extends Error {
  readonly status: number;
  readonly fieldErrors: FieldErrors;

  constructor(status: number, message: string, fieldErrors: FieldErrors = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

type BackendErrorDetail = {
  detail?: unknown;
};

function extractFieldErrors(detail: unknown): FieldErrors {
  if (!Array.isArray(detail)) {
    return {};
  }
  const fieldErrors: FieldErrors = {};
  for (const item of detail) {
    if (
      item &&
      typeof item === "object" &&
      "loc" in item &&
      "msg" in item &&
      Array.isArray((item as { loc: unknown }).loc)
    ) {
      const loc = (item as { loc: unknown[] }).loc;
      const field = loc.length > 0 ? String(loc[loc.length - 1]) : "";
      if (field && fieldErrors[field] === undefined) {
        fieldErrors[field] = String((item as { msg: unknown }).msg);
      }
    }
  }
  return fieldErrors;
}

async function readApiError(response: Response, fallback: string): Promise<ApiError> {
  let message = fallback;
  let fieldErrors: FieldErrors = {};
  try {
    const body = (await response.json()) as BackendErrorDetail;
    if (typeof body?.detail === "string" && body.detail.trim()) {
      message = body.detail;
    } else if (body?.detail !== undefined) {
      fieldErrors = extractFieldErrors(body.detail);
      if (Object.keys(fieldErrors).length > 0) {
        message = "Some fields need attention before saving.";
      }
    }
  } catch {
    // Keep the fallback message when the body is not readable JSON.
  }
  return new ApiError(response.status, message, fieldErrors);
}

function networkError(error: unknown, fallback: string): ApiError {
  if (error instanceof ApiError) {
    return error;
  }
  // fetch() rejects on network/CORS failures before any response exists.
  return new ApiError(
    0,
    "The server could not be reached. Check that the backend is running and try again.",
    {},
  );
}

export async function getCurrentIdentity(
  idToken: string,
): Promise<AuthenticatedIdentity> {
  const response = await fetch(`${apiBaseUrl}/api/auth/me`, {
    headers: {
      Authorization: `Bearer ${idToken}`,
    },
  });

  if (!response.ok) {
    throw await readApiError(
      response,
      "The backend could not verify your authentication.",
    );
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
    throw await readApiError(response, "The profile could not be loaded.");
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
    throw await readApiError(response, "The profile could not be saved.");
  }
  return response.json() as Promise<StudentProfile>;
}

export async function getMyLostItems(idToken: string): Promise<LostItem[]> {
  const response = await fetch(`${apiBaseUrl}/api/lost-items`, {
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw await readApiError(response, "Lost reports could not be loaded.");
  }
  return response.json() as Promise<LostItem[]>;
}

export async function getMyFoundItems(idToken: string): Promise<FoundItem[]> {
  const response = await fetch(`${apiBaseUrl}/api/found-items`, {
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw await readApiError(response, "Found reports could not be loaded.");
  }
  return response.json() as Promise<FoundItem[]>;
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
    throw await readApiError(response, "Lost report could not be saved.");
  }
  return response.json() as Promise<LostItem>;
}

export async function deleteLostItem(idToken: string, itemId: number): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/lost-items/${itemId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw await readApiError(response, "Lost report could not be deleted.");
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
    throw await readApiError(response, "Image could not be stored.");
  }
  return response.json() as Promise<LostItem>;
}

export async function analyzeItemImage(
  idToken: string,
  image: File,
): Promise<ImageAnalysisResult> {
  const formData = new FormData();
  formData.append("image", image);
  const response = await fetch(`${apiBaseUrl}/api/found-items/analyze-image`, {
    method: "POST",
    headers: { Authorization: `Bearer ${idToken}` },
    body: formData,
  });
  if (!response.ok) {
    throw await readApiError(response, "Image analysis could not be completed.");
  }
  return response.json() as Promise<ImageAnalysisResult>;
}

export async function createFoundItem(
  idToken: string,
  input: FoundItemInput | string,
  foundLocation?: string,
  campus?: string,
): Promise<FoundItem> {
  let bodyPayload: FoundItemInput;
  if (typeof input === "string") {
    bodyPayload = {
      found_date: input,
      found_location: foundLocation || null,
      campus: campus || null,
    };
  } else {
    bodyPayload = input;
  }
  const response = await fetch(`${apiBaseUrl}/api/found-items`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${idToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(bodyPayload),
  });
  if (!response.ok) {
    throw await readApiError(response, "Found item could not be reported.");
  }
  return response.json() as Promise<FoundItem>;
}

export async function updateFoundItem(
  idToken: string,
  itemId: number,
  input: Partial<FoundItemInput>,
): Promise<FoundItem> {
  const response = await fetch(`${apiBaseUrl}/api/found-items/${itemId}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${idToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw await readApiError(response, "Found item could not be updated.");
  }
  return response.json() as Promise<FoundItem>;
}

export async function deleteFoundItem(idToken: string, itemId: number): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/found-items/${itemId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw await readApiError(response, "Found report could not be deleted.");
  }
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
    throw await readApiError(response, "Found-item image could not be stored.");
  }
  return response.json() as Promise<FoundItem>;
}

export async function triggerFoundItemAnalysis(
  idToken: string,
  itemId: number,
): Promise<{ found_item: FoundItem; accepted: boolean; message: string; attributes?: Record<string, unknown> | null }> {
  const response = await fetch(`${apiBaseUrl}/api/found-items/${itemId}/analyze`, {
    method: "POST",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw await readApiError(response, "Found-item analysis could not be started.");
  }
  return response.json() as Promise<{
    found_item: FoundItem;
    accepted: boolean;
    message: string;
    attributes?: Record<string, unknown> | null;
  }>;
}


export async function getFoundItemMatches(
  idToken: string,
  foundItemId: number,
): Promise<MatchSearchResponse> {
  const response = await fetch(`${apiBaseUrl}/api/matches/found/${foundItemId}`, {
    method: "GET",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw await readApiError(response, "Match results could not be retrieved.");
  }
  return response.json() as Promise<MatchSearchResponse>;
}

export async function getLostItemMatches(
  idToken: string,
  lostItemId: number,
  refresh = false,
): Promise<MatchSearchResponse> {
  const query = refresh ? "?refresh=true" : "";
  const response = await fetch(`${apiBaseUrl}/api/matches/lost/${lostItemId}${query}`, {
    method: "GET",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw await readApiError(response, "Match results could not be retrieved.");
  }
  return response.json() as Promise<MatchSearchResponse>;
}

export async function evaluateMatches(
  idToken: string,
  foundItemId: number,
  filters?: {
    category?: string | null;
    campus?: string | null;
    location?: string | null;
    brand?: string | null;
    date_window_days?: number;
    max_results?: number;
  },
): Promise<MatchSearchResponse> {
  const response = await fetch(`${apiBaseUrl}/api/matches/evaluate`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${idToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      found_item_id: foundItemId,
      ...(filters || {}),
    }),
  });
  if (!response.ok) {
    throw await readApiError(response, "Matches could not be evaluated.");
  }
  return response.json() as Promise<MatchSearchResponse>;
}

export type ClaimSummary = {
  id: number;
  match_id: number;
  claimant_user_id: number;
  claimant_name?: string | null;
  status: string;
  verification_notes?: string | null;
  found_item_id: number;
  lost_item_id: number;
  item_name: string;
  found_item_name?: string | null;
  lost_item_name?: string | null;
  is_finder?: boolean | null;
  category?: string | null;
  score?: number | null;
  created_at: string;
  updated_at: string;
};

export type ClaimDetail = {
  id: number;
  match_id: number;
  claimant_user_id: number;
  claimant_name?: string | null;
  finder_name?: string | null;
  status: string;
  verification_notes?: string | null;
  user_role: "claimant" | "lost_owner" | "found_finder" | "admin" | string;
  can_approve: boolean;
  can_reject: boolean;
  can_escalate: boolean;
  can_return?: boolean;
  found_item: Record<string, unknown>;
  lost_item: Record<string, unknown>;
  match_score?: number | null;
  audit_history: Array<{
    id: number;
    actor_user_id?: number | null;
    action: string;
    details?: Record<string, unknown> | null;
    created_at: string;
  }>;
  created_at: string;
  updated_at: string;
};

export async function createClaim(
  idToken: string,
  matchId: number,
  verificationNotes?: string,
  claimExplanation?: string,
): Promise<{ id: number; match_id: number; status: string }> {
  const response = await fetch(`${apiBaseUrl}/api/claims`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${idToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      match_id: matchId,
      verification_notes: verificationNotes || null,
      claim_explanation: claimExplanation || null,
    }),
  });
  if (!response.ok) {
    throw await readApiError(response, "Claim could not be submitted.");
  }
  return response.json();
}

export async function getMyClaims(idToken: string): Promise<ClaimSummary[]> {
  const response = await fetch(`${apiBaseUrl}/api/claims/my-claims`, {
    method: "GET",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw await readApiError(response, "Claims could not be retrieved.");
  }
  return response.json() as Promise<ClaimSummary[]>;
}

export async function getClaimDetail(
  idToken: string,
  claimId: number,
): Promise<ClaimDetail> {
  const response = await fetch(`${apiBaseUrl}/api/claims/${claimId}`, {
    method: "GET",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw await readApiError(response, "Claim detail could not be retrieved.");
  }
  return response.json() as Promise<ClaimDetail>;
}

export async function submitClaimDecision(
  idToken: string,
  claimId: number,
  decision: "APPROVE" | "REJECT" | "ESCALATE",
  notes?: string,
): Promise<ClaimDetail> {
  const response = await fetch(`${apiBaseUrl}/api/claims/${claimId}/decision`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${idToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      decision,
      notes: notes || null,
    }),
  });
  if (!response.ok) {
    throw await readApiError(response, "Claim decision could not be processed.");
  }
  return response.json() as Promise<ClaimDetail>;
}

export async function processClaimReturn(
  idToken: string,
  claimId: number,
  handoverNotes?: string,
  handoverLocation?: string,
): Promise<ClaimDetail> {
  const response = await fetch(`${apiBaseUrl}/api/claims/${claimId}/return`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${idToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      handover_notes: handoverNotes || null,
      handover_location: handoverLocation || null,
    }),
  });
  if (!response.ok) {
    throw await readApiError(response, "Item return could not be processed.");
  }
  return response.json() as Promise<ClaimDetail>;
}

// ---------------------------------------------------------------------------
// Phase 15: Admin Dashboard & Moderation
// ---------------------------------------------------------------------------

export type AdminOverviewStats = {
  total_users: number;
  active_users: number;
  suspended_users: number;
  total_lost_items: number;
  active_lost_items: number;
  returned_lost_items: number;
  closed_lost_items: number;
  total_found_items: number;
  active_found_items: number;
  returned_found_items: number;
  closed_found_items: number;
  total_matches: number;
  suggested_matches: number;
  claimed_matches: number;
  total_claims: number;
  active_claims: number;
  disputed_claims: number;
  approved_claims: number;
  returned_claims: number;
  rejected_claims: number;
};

export type AdminUserSummary = {
  id: number;
  firebase_uid: string;
  status: string;
  role: string;
  email?: string | null;
  full_name?: string | null;
  roll_number?: string | null;
  campus?: string | null;
  phone_number?: string | null;
  lost_count: number;
  found_count: number;
  claim_count: number;
  created_at: string;
  updated_at: string;
};

export type AdminUserDetail = AdminUserSummary & {
  lost_items: LostItem[];
  found_items: FoundItem[];
  claims: Array<Record<string, unknown>>;
  audit_history: Array<Record<string, unknown>>;
};

export type AdminAuditLogEntry = {
  id: number;
  actor_user_id?: number | null;
  actor_email?: string | null;
  entity_type: string;
  entity_id: number;
  action: string;
  details?: Record<string, unknown> | null;
  created_at: string;
};

export async function verifyAdminStatus(idToken: string): Promise<{
  status: string;
  uid: string;
  email?: string;
  role: string;
  is_admin: boolean;
}> {
  const response = await fetch(`${apiBaseUrl}/api/admin/verify`, {
    method: "GET",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw await readApiError(response, "Admin access denied.");
  }
  return response.json();
}

export async function getAdminOverview(idToken: string): Promise<AdminOverviewStats> {
  const response = await fetch(`${apiBaseUrl}/api/admin/overview`, {
    method: "GET",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw await readApiError(response, "Admin overview could not be loaded.");
  }
  return response.json() as Promise<AdminOverviewStats>;
}

export async function getAdminUsers(
  idToken: string,
  params?: { status?: string; role?: string; search?: string },
): Promise<AdminUserSummary[]> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.role) query.set("role", params.role);
  if (params?.search) query.set("search", params.search);

  const url = `${apiBaseUrl}/api/admin/users${query.toString() ? `?${query.toString()}` : ""}`;
  const response = await fetch(url, {
    method: "GET",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw await readApiError(response, "Users list could not be loaded.");
  }
  return response.json() as Promise<AdminUserSummary[]>;
}

export async function updateAdminUserStatus(
  idToken: string,
  userId: number,
  status: string,
  reason?: string,
): Promise<AdminUserDetail> {
  const response = await fetch(`${apiBaseUrl}/api/admin/users/${userId}/status`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${idToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      status,
      reason: reason || null,
    }),
  });
  if (!response.ok) {
    throw await readApiError(response, "User status could not be updated.");
  }
  return response.json() as Promise<AdminUserDetail>;
}

export async function getAdminLostItems(
  idToken: string,
  params?: { status?: string; campus?: string; category?: string; search?: string },
): Promise<LostItem[]> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.campus) query.set("campus", params.campus);
  if (params?.category) query.set("category", params.category);
  if (params?.search) query.set("search", params.search);

  const url = `${apiBaseUrl}/api/admin/lost-items${query.toString() ? `?${query.toString()}` : ""}`;
  const response = await fetch(url, {
    method: "GET",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw await readApiError(response, "Lost reports could not be loaded.");
  }
  return response.json() as Promise<LostItem[]>;
}

export async function updateAdminLostItemStatus(
  idToken: string,
  itemId: number,
  status: string,
  reason?: string,
): Promise<LostItem> {
  const response = await fetch(`${apiBaseUrl}/api/admin/lost-items/${itemId}/status`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${idToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      status,
      reason: reason || null,
    }),
  });
  if (!response.ok) {
    throw await readApiError(response, "Lost report status could not be updated.");
  }
  return response.json() as Promise<LostItem>;
}

export async function getAdminFoundItems(
  idToken: string,
  params?: { status?: string; campus?: string; category?: string; search?: string },
): Promise<FoundItem[]> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.campus) query.set("campus", params.campus);
  if (params?.category) query.set("category", params.category);
  if (params?.search) query.set("search", params.search);

  const url = `${apiBaseUrl}/api/admin/found-items${query.toString() ? `?${query.toString()}` : ""}`;
  const response = await fetch(url, {
    method: "GET",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw await readApiError(response, "Found reports could not be loaded.");
  }
  return response.json() as Promise<FoundItem[]>;
}

export async function updateAdminFoundItemStatus(
  idToken: string,
  itemId: number,
  status: string,
  reason?: string,
): Promise<FoundItem> {
  const response = await fetch(`${apiBaseUrl}/api/admin/found-items/${itemId}/status`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${idToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      status,
      reason: reason || null,
    }),
  });
  if (!response.ok) {
    throw await readApiError(response, "Found report status could not be updated.");
  }
  return response.json() as Promise<FoundItem>;
}

export async function getAdminClaims(
  idToken: string,
  status?: string,
): Promise<Array<Record<string, unknown>>> {
  const url = status
    ? `${apiBaseUrl}/api/admin/claims?status=${encodeURIComponent(status)}`
    : `${apiBaseUrl}/api/admin/claims`;
  const response = await fetch(url, {
    method: "GET",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw await readApiError(response, "Claims could not be loaded.");
  }
  return response.json() as Promise<Array<Record<string, unknown>>>;
}

export async function getAdminDisputes(
  idToken: string,
): Promise<Array<Record<string, unknown>>> {
  const response = await fetch(`${apiBaseUrl}/api/admin/disputes`, {
    method: "GET",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw await readApiError(response, "Disputes could not be loaded.");
  }
  return response.json() as Promise<Array<Record<string, unknown>>>;
}

export async function overrideAdminClaim(
  idToken: string,
  claimId: number,
  newStatus: string,
  adminNotes?: string,
): Promise<ClaimDetail> {
  const response = await fetch(`${apiBaseUrl}/api/admin/claims/${claimId}/override`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${idToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      new_status: newStatus,
      admin_notes: adminNotes || null,
    }),
  });
  if (!response.ok) {
    throw await readApiError(response, "Claim status could not be overridden.");
  }
  return response.json() as Promise<ClaimDetail>;
}

export async function getAdminAuditLogs(
  idToken: string,
  params?: { entity_type?: string; action?: string; limit?: number | string; offset?: number | string },
): Promise<AdminAuditLogEntry[]> {
  const query = new URLSearchParams();
  if (params?.entity_type) query.set("entity_type", params.entity_type);
  if (params?.action) query.set("action", params.action);
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));

  const url = `${apiBaseUrl}/api/admin/audit-logs${query.toString() ? `?${query.toString()}` : ""}`;
  const response = await fetch(url, {
    method: "GET",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw await readApiError(response, "Audit logs could not be loaded.");
  }
  return response.json() as Promise<AdminAuditLogEntry[]>;
}

export type ManualSearchParams = {
  query?: string;
  category?: string;
  campus?: string;
  location?: string;
  color?: string;
  brand?: string;
  from_date?: string;
  to_date?: string;
  limit?: number;
  offset?: number;
};

export type PublicFoundItem = {
  id: number;
  status: string;
  found_date: string;
  found_location: string | null;
  campus: string | null;
  item_name: string | null;
  category: string | null;
  color: string | null;
  brand: string | null;
  description: string | null;
  distinctive_features: string | null;
  image_reference: string | null;
  created_at: string;
};

export type PublicLostItem = {
  id: number;
  status: string;
  lost_date: string;
  approximate_location: string | null;
  campus: string | null;
  item_name: string;
  category: string | null;
  color: string | null;
  brand: string | null;
  description: string | null;
  distinctive_features: string | null;
  image_reference: string | null;
  created_at: string;
};

export type ManualSearchResult<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
  filters_applied: Record<string, unknown>;
};

export type SearchSystemStatus = {
  ai_available: boolean;
  foundry_configured: boolean;
  ocr_configured: boolean;
  embeddings_configured: boolean;
  manual_search_available: boolean;
};

export async function getSearchSystemStatus(idToken: string): Promise<SearchSystemStatus> {
  const response = await fetch(`${apiBaseUrl}/api/search/status`, {
    method: "GET",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw await readApiError(response, "System status could not be loaded.");
  }
  return response.json() as Promise<SearchSystemStatus>;
}

export async function searchPublicFoundItems(
  idToken: string,
  params?: ManualSearchParams,
): Promise<ManualSearchResult<PublicFoundItem>> {
  const query = new URLSearchParams();
  if (params?.query) query.set("query", params.query);
  if (params?.category) query.set("category", params.category);
  if (params?.campus) query.set("campus", params.campus);
  if (params?.location) query.set("location", params.location);
  if (params?.color) query.set("color", params.color);
  if (params?.brand) query.set("brand", params.brand);
  if (params?.from_date) query.set("from_date", params.from_date);
  if (params?.to_date) query.set("to_date", params.to_date);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));

  const url = `${apiBaseUrl}/api/search/found-items${query.toString() ? `?${query.toString()}` : ""}`;
  const response = await fetch(url, {
    method: "GET",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw await readApiError(response, "Found items search failed.");
  }
  return response.json() as Promise<ManualSearchResult<PublicFoundItem>>;
}

export async function searchPublicLostItems(
  idToken: string,
  params?: ManualSearchParams,
): Promise<ManualSearchResult<PublicLostItem>> {
  const query = new URLSearchParams();
  if (params?.query) query.set("query", params.query);
  if (params?.category) query.set("category", params.category);
  if (params?.campus) query.set("campus", params.campus);
  if (params?.location) query.set("location", params.location);
  if (params?.color) query.set("color", params.color);
  if (params?.brand) query.set("brand", params.brand);
  if (params?.from_date) query.set("from_date", params.from_date);
  if (params?.to_date) query.set("to_date", params.to_date);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));

  const url = `${apiBaseUrl}/api/search/lost-items${query.toString() ? `?${query.toString()}` : ""}`;
  const response = await fetch(url, {
    method: "GET",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw await readApiError(response, "Lost items search failed.");
  }
  return response.json() as Promise<ManualSearchResult<PublicLostItem>>;
}

export type AppNotification = {
  id: number;
  user_id: number;
  type: string;
  title: string;
  message: string;
  entity_type?: string | null;
  entity_id?: number | null;
  is_read: boolean;
  created_at: string;
};

export type NotificationListResponse = {
  notifications: AppNotification[];
  unread_count: number;
  total: number;
};

export async function getNotifications(
  idToken: string,
  limit: number = 50,
  offset: number = 0,
): Promise<NotificationListResponse> {
  const response = await fetch(
    `${apiBaseUrl}/api/notifications?limit=${limit}&offset=${offset}`,
    {
      method: "GET",
      headers: { Authorization: `Bearer ${idToken}` },
    },
  );
  if (!response.ok) {
    throw await readApiError(response, "Notifications could not be loaded.");
  }
  return response.json() as Promise<NotificationListResponse>;
}

export async function markNotificationAsRead(
  idToken: string,
  notificationId: number,
): Promise<void> {
  const response = await fetch(
    `${apiBaseUrl}/api/notifications/${notificationId}/read`,
    {
      method: "PATCH",
      headers: { Authorization: `Bearer ${idToken}` },
    },
  );
  if (!response.ok) {
    throw await readApiError(response, "Could not update notification status.");
  }
}

export async function markAllNotificationsAsRead(idToken: string): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/notifications/read-all`, {
    method: "POST",
    headers: { Authorization: `Bearer ${idToken}` },
  });
  if (!response.ok) {
    throw await readApiError(response, "Could not mark all notifications as read.");
  }
}

export async function analyzeLostItemImage(
  idToken: string,
  imageFile: File,
): Promise<ImageAnalysisResult> {
  const formData = new FormData();
  formData.append("image", imageFile);

  const response = await fetch(`${apiBaseUrl}/api/lost-items/analyze-image`, {
    method: "POST",
    headers: { Authorization: `Bearer ${idToken}` },
    body: formData,
  });

  if (!response.ok) {
    throw await readApiError(response, "Lost item image analysis failed.");
  }

  return response.json() as Promise<ImageAnalysisResult>;
}

export { networkError };
