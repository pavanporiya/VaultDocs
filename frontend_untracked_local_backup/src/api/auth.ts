/**
 * Auth endpoints: POST /v1/auth/register, POST /v1/auth/login, GET /v1/auth/me.
 *
 * Login stores the returned access token via the token module; the backend has
 * no refresh/logout endpoints, so "logout" is purely client-side (clear token).
 */

import { request } from "./client";
import { setAccessToken } from "./token";
import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  User,
} from "./types";

/** Register a new user. Returns the public user (no token). */
export function registerUser(data: RegisterRequest): Promise<User> {
  return request<User>("POST", "/v1/auth/register", { json: data });
}

/** Authenticate and store the returned access token. */
export async function login(data: LoginRequest): Promise<TokenResponse> {
  const token = await request<TokenResponse>("POST", "/v1/auth/login", {
    json: data,
  });
  setAccessToken(token.access_token);
  return token;
}

/** Fetch the currently authenticated user (GET /v1/auth/me). */
export function getCurrentUser(): Promise<User> {
  return request<User>("GET", "/v1/auth/me");
}
