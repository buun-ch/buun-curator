/**
 * Better Auth API route handler.
 *
 * Handles all authentication-related requests including OAuth callbacks.
 */

import { toNextJsHandler } from "better-auth/next-js";

import { auth } from "@/lib/auth";

export const { POST, GET } = toNextJsHandler(auth);
