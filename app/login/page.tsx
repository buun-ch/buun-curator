"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { authClient } from "@/lib/auth-client";
import { Button } from "@/components/ui/button";

export default function LoginPage() {
  const searchParams = useSearchParams();
  const error = searchParams.get("error");
  const [isLoading, setIsLoading] = useState(false);
  const [clientError, setClientError] = useState<string | null>(null);

  const handleLogin = async () => {
    setIsLoading(true);
    setClientError(null);
    try {
      const result = await authClient.signIn.oauth2({
        providerId: "keycloak",
        callbackURL: "/",
        errorCallbackURL: "/login?error=auth_failed",
      });
      if (result.error) {
        setClientError(result.error.message || "Unknown error");
      }
    } catch (err) {
      console.error("signIn.oauth2 error:", err);
      setClientError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4">
      <h1 className="text-2xl font-bold">Buun Curator</h1>
      {error && (
        <p className="text-destructive text-sm">
          Authentication failed. Please try again.
        </p>
      )}
      {clientError && (
        <p className="text-destructive text-sm">Error: {clientError}</p>
      )}
      <Button onClick={handleLogin} size="lg" disabled={isLoading}>
        {isLoading ? "Signing in..." : "Sign in with Keycloak"}
      </Button>
    </div>
  );
}
