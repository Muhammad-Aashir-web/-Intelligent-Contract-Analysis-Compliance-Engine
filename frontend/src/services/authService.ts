import apiClient from "./api"

export async function login(
	email: string,
	password: string,
): Promise<{ access_token: string }> {
	const response = await apiClient.post<{ access_token: string }>("/auth/login", {
		email,
		password,
	})

	if (response.data?.access_token) {
		localStorage.setItem("token", response.data.access_token)
	}

	return response.data
}

export async function register(
	email: string,
	password: string,
	fullName: string,
): Promise<any> {
	const response = await apiClient.post("/auth/register", {
		email,
		password,
		full_name: fullName,
	})

	return response.data
}

export function logout(): void {
	localStorage.removeItem("token")
	window.location.href = "/login"
}

export async function getCurrentUser(): Promise<any> {
	const response = await apiClient.get("/auth/me")
	return response.data
}

export function isAuthenticated(): boolean {
	return Boolean(localStorage.getItem("token"))
}
