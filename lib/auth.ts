/**
 * Better Auth server-side configuration for Keycloak authentication.
 *
 * @module lib/auth
 */

import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import { genericOAuth, keycloak } from "better-auth/plugins";
import { db } from "@/db";

const keycloakIssuer = `${process.env.KEYCLOAK_URL}/realms/${process.env.KEYCLOAK_REALM}`;

export const auth = betterAuth({
  database: drizzleAdapter(db, {
    provider: "pg",
  }),
  baseURL: process.env.BETTER_AUTH_URL,
  secret: process.env.BETTER_AUTH_SECRET,
  trustedOrigins: process.env.BETTER_AUTH_URL ? [process.env.BETTER_AUTH_URL] : [],
  advanced: {
    // Required when behind a reverse proxy (Traefik/nginx) with HTTPS termination
    useSecureCookies: process.env.NODE_ENV === "production",
  },
  plugins: [
    genericOAuth({
      config: [
        keycloak({
          clientId: process.env.KEYCLOAK_CLIENT_ID!,
          clientSecret: process.env.KEYCLOAK_CLIENT_SECRET!,
          issuer: keycloakIssuer,
          pkce: true,
        }),
      ],
    }),
  ],
});
