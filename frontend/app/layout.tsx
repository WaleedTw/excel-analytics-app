import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "بيّنة | تحليلات Excel واضحة",
  description: "منصة عربية آمنة لتحويل ملفات Excel إلى رؤى ولوحات معلومات تفاعلية.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ar" dir="rtl"><body>{children}</body></html>;
}

