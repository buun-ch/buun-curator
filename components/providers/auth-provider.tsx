"use client";

import { createContext, useContext, useEffect, ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useSession } from "@/lib/auth-client";

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

/** Provides authentication state to child components. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const { data: session, isPending } = useSession();
  const router = useRouter();
  const pathname = usePathname();

  // Redirect to login when session is invalid (cookie exists but session doesn't)
  useEffect(() => {
    if (!isPending && !session?.user && !isPublicRoute(pathname)) {
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
