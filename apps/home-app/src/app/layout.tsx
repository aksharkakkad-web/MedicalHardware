import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { HomeShell } from "@/components/home-shell/home-shell";
import { Providers } from "./providers";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = { title: "Adaptive Care Home", description: "A calm view of a loved one's monitoring." };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body className={`${geistSans.variable} ${geistMono.variable}`}><Providers><HomeShell>{children}</HomeShell></Providers></body></html>;
}
