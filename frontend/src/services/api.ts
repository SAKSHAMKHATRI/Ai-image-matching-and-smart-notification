const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export type AuthenticatedIdentity = {
  uid: string;
  email: string | null;
  email_verified: boolean;
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
