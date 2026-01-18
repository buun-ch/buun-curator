import type { Metadata } from "next";
import {
  BIZ_UDPGothic,
  Inter,
  JetBrains_Mono,
  M_PLUS_1_Code,
} from "next/font/google";
import { QueryProvider } from "@/components/providers/query-provider";
import { AuthProvider } from "@/components/providers/auth-provider";
import { SSEProvider, WorkflowStatusPanel } from "@/components/status";
import { NextjsIndicatorFix } from "@/components/dev/nextjs-indicator-fix";
import { PublicEnv } from "@/lib/config";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin", "latin-ext"],
});

const bizUdpGothic = BIZ_UDPGothic({
  variable: "--font-biz-udp-gothic",
  subsets: ["latin"],
  weight: ["400", "700"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin", "latin-ext", "cyrillic"],
});

const mplus1Code = M_PLUS_1_Code({
  variable: "--font-mplus-1-code",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Buun Curator",
  description: "Multi-panel feed reader with AI assistant",
  icons: {
    icon: [
      { url: "/favicon-32x32.png", sizes: "32x32", type: "image/png" },
      { url: "/favicon-16x16.png", sizes: "16x16", type: "image/png" },
    ],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180" }],
  },
  manifest: "/site.webmanifest",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${inter.variable} ${bizUdpGothic.variable} ${jetbrainsMono.variable} ${mplus1Code.variable} antialiased`}
      >
        <PublicEnv />
        <QueryProvider>
          <AuthProvider>
            <SSEProvider>
              {children}
              <WorkflowStatusPanel />
              <NextjsIndicatorFix />
            </SSEProvider>
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
