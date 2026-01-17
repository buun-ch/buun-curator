import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { headers } from "next/headers";
import { auth } from "@/lib/auth";

/**
 * Proxy function to protect routes requiring authentication (Next.js 16+).
 *
 * Uses Better Auth's getSession API for proper session validation.
 * Redirects unauthenticated users to the login page.
 * Allows access with valid internal API token for service-to-service calls.
 * Authentication can be disabled via AUTH_ENABLED=false environment variable.
 */
export async function proxy(request: NextRequest) {
  // Skip authentication if disabled
  const authEnabled = process.env.AUTH_ENABLED !== "false";
  if (!authEnabled) {
    return NextResponse.next();
  }

  // Allow access to public routes
  const isPublicRoute =
    request.nextUrl.pathname.startsWith("/login") ||
    request.nextUrl.pathname.startsWith("/api/auth") ||
    request.nextUrl.pathname.startsWith("/healthz");

  if (isPublicRoute) {
    return NextResponse.next();
  }

  // Check for internal API token (for Worker and other services)
  const authHeader = request.headers.get("authorization");
  const internalToken = process.env.INTERNAL_API_TOKEN;
  if (
    internalToken &&
    authHeader === `Bearer ${internalToken}` &&
    request.nextUrl.pathname.startsWith("/api/")
  ) {
    return NextResponse.next();
  }

  // Validate session using Better Auth API
  const session = await auth.api.getSession({
    headers: await headers(),
  });

  if (!session) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - *.png (top-level PNG files: favicons, icons)
     * - favicon.ico, site.webmanifest
     */
    "/((?!_next/static|_next/image|[^/]+\\.png|favicon\\.ico|site\\.webmanifest).*)",
  ],
};
