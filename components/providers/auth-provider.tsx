"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, ReactNode, useContext, useEffect } from "react";

import { useSession as useBetterAuthSession } from "@/lib/auth-client";
import { isAuthEnabled } from "@/lib/config";

/** User object from Better Auth session. */
interface User {
  id: string;
  name: string;
  email: string;
  image?: string | null;
}

/** Authentication context value. */
interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

/** Routes that don't require authentication. */
const PUBLIC_ROUTES = ["/login", "/api/auth", "/healthz"];

/** Checks if a pathname is a public route. */
function isPublicRoute(pathname: string): boolean {
  return PUBLIC_ROUTES.some((route) => pathname.startsWith(route));
}

/**
 * Session hook that returns mock data when auth is disabled.
 * Avoids making Better Auth API calls when BETTER_AUTH_URL is not configured.
 */
function useSession() {
  // Always call the hook to satisfy React's rules of hooks
  const realSession = useBetterAuthSession();

  // Return mock data when auth is disabled
  if (!isAuthEnabled()) {
    return { data: null, isPending: false };
  }

  return realSession;
}

/** Provides authentication state to child components. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const { data: session, isPending } = useSession();
  const router = useRouter();
  const pathname = usePathname();

  // Redirect to login when session is invalid (cookie exists but session doesn't)
  // Skip redirect if auth is disabled
  useEffect(() => {
    if (
      isAuthEnabled() &&
      !isPending &&
      !session?.user &&
      !isPublicRoute(pathname)
    ) {
      router.replace("/login");
    }
  }, [isPending, session?.user, pathname, router]);

  return (
    <AuthContext.Provider
      value={{
        user: session?.user ?? null,
        isLoading: isPending,
        isAuthenticated: !!session?.user,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

/** Hook to access authentication state. */
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
