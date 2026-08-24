import { HttpError } from "./http";

const encoder = new TextEncoder();
const decoder = new TextDecoder("utf-8", { fatal: true });

export function utf8(value: string): Uint8Array {
  return encoder.encode(value);
}

export function arrayBuffer(value: Uint8Array): ArrayBuffer {
  const copy = new Uint8Array(value.byteLength);
  copy.set(value);
  return copy.buffer;
}

export function decodeUtf8(value: Uint8Array): string {
  try {
    return decoder.decode(value);
  } catch {
    throw new HttpError(401, "invalid_session", "The session is invalid.");
  }
}

export function base64urlEncode(value: Uint8Array): string {
  return base64Encode(value)
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replace(/=+$/, "");
}

export function base64Encode(value: Uint8Array): string {
  let binary = "";
  for (let offset = 0; offset < value.length; offset += 8_192) {
    binary += String.fromCharCode(...value.subarray(offset, offset + 8_192));
  }
  return btoa(binary);
}

export function base64urlDecode(value: string): Uint8Array {
  if (!/^[A-Za-z0-9_-]*$/.test(value)) {
    throw new HttpError(401, "invalid_session", "The session is invalid.");
  }
  const padded =
    value.replaceAll("-", "+").replaceAll("_", "/") +
    "=".repeat((4 - (value.length % 4)) % 4);
  try {
    const binary = atob(padded);
    return Uint8Array.from(binary, (character) => character.charCodeAt(0));
  } catch {
    throw new HttpError(401, "invalid_session", "The session is invalid.");
  }
}

export function randomToken(bytes = 32): string {
  const value = new Uint8Array(bytes);
  crypto.getRandomValues(value);
  return base64urlEncode(value);
}

export async function sha256Base64url(value: string): Promise<string> {
  return base64urlEncode(
    new Uint8Array(
      await crypto.subtle.digest("SHA-256", arrayBuffer(utf8(value))),
    ),
  );
}

export function equalTokens(left: string, right: string): boolean {
  const length = Math.max(left.length, right.length);
  let difference = left.length ^ right.length;
  for (let index = 0; index < length; index += 1) {
    difference |=
      (left.charCodeAt(index) || 0) ^ (right.charCodeAt(index) || 0);
  }
  return difference === 0;
}
