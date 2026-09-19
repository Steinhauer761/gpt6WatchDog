import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "WatchDog Security Console",
  description: "Defensive research, evidence and authorized security tools",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
