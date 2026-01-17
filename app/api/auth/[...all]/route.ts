/**
 * Better Auth API route handler.
 *
 * Handles all authentication-related requests including OAuth callbacks.
 */

import { auth } from "@/lib/auth";
import { toNextJsHandler } from "better-auth/next-js";

export const { POST, GET } = toNextJsHandler(auth);
