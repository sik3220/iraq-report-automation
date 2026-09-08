import { createHmac, timingSafeEqual } from "node:crypto";

export const SESSION_COOKIE = "iraq_dashboard_session";
const SESSION_TTL_SECONDS = 8 * 60 * 60;

function environment(): Record<string, string | undefined> {
  return typeof process === "undefined" ? {} : process.env;
}

function configuredPassword() {
  return environment().DASHBOARD_PASSWORD || "";
}

function configuredSecret() {
  return environment().AUTH_SECRET || configuredPassword();
}

function signature(value: string) {
  return createHmac("sha256", configuredSecret()).update(value).digest("base64url");
}

export function authenticationEnabled() {
  return Boolean(configuredPassword());
}

export function isAuthenticated(request: Request) {
  if (!authenticationEnabled()) {
    return environment().NODE_ENV !== "production";
  }
  const cookie = request.headers.get("cookie") || "";
  const match = cookie.match(new RegExp(`(?:^|;\\s*)${SESSION_COOKIE}=([^;]+)`));
  if (!match) return false;
  const [expires, provided] = decodeURIComponent(match[1]).split(".");
  if (!expires || !provided || !/^\\d+$/.test(expires) || Number(expires) <= Math.floor(Date.now() / 1000)) return false;
  const expected = signature(expires);
  try {
    return timingSafeEqual(Buffer.from(provided), Buffer.from(expected));
  } catch {
    return false;
  }
}

export function passwordMatches(password: unknown) {
  if (typeof password !== "string" || !authenticationEnabled()) return false;
  const expected = Buffer.from(configuredPassword());
  const actual = Buffer.from(password);
  return expected.length === actual.length && timingSafeEqual(actual, expected);
}

export function sessionCookie(secure: boolean) {
  const expires = Math.floor(Date.now() / 1000) + SESSION_TTL_SECONDS;
  const value = encodeURIComponent(`${expires}.${signature(String(expires))}`);
  return `${SESSION_COOKIE}=${value}; Path=/; HttpOnly; SameSite=Strict; Max-Age=${SESSION_TTL_SECONDS}${secure ? "; Secure" : ""}`;
}

export function expiredSessionCookie(secure: boolean) {
  return `${SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0${secure ? "; Secure" : ""}`;
}

