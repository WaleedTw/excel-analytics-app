"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useSyncExternalStore } from "react";

export type Locale = "ar" | "en";

type LanguageContextValue = {
  locale: Locale;
  direction: "rtl" | "ltr";
  setLocale: (locale: Locale) => void;
  toggleLocale: () => void;
  t: (arabic: string, english: string) => string;
};

const LanguageContext = createContext<LanguageContextValue | null>(null);
const STORAGE_KEY = "bayyinah-locale";
const LOCALE_EVENT = "bayyinah-locale-change";

const subscribeToLocale = (notify: () => void) => {
  window.addEventListener("storage", notify);
  window.addEventListener(LOCALE_EVENT, notify);
  return () => {
    window.removeEventListener("storage", notify);
    window.removeEventListener(LOCALE_EVENT, notify);
  };
};

const readLocale = (): Locale => {
  const saved = window.localStorage.getItem(STORAGE_KEY);
  return saved === "en" ? "en" : "ar";
};

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const locale = useSyncExternalStore<Locale>(subscribeToLocale, readLocale, () => "ar");

  const setLocale = useCallback((next: Locale) => {
    window.localStorage.setItem(STORAGE_KEY, next);
    window.dispatchEvent(new Event(LOCALE_EVENT));
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    root.lang = locale;
    root.dir = locale === "ar" ? "rtl" : "ltr";
    root.dataset.locale = locale;
    document.title = locale === "ar" ? "بيّنة | تحليلات Excel واضحة" : "Bayyinah | Clear Excel Analytics";
    const description = document.querySelector<HTMLMetaElement>('meta[name="description"]');
    if (description) {
      description.content = locale === "ar"
        ? "منصة عربية آمنة لتحويل ملفات Excel إلى رؤى ولوحات معلومات تفاعلية."
        : "A secure platform that turns Excel files into verified insights and interactive dashboards.";
    }
  }, [locale]);

  const value = useMemo<LanguageContextValue>(() => ({
    locale,
    direction: locale === "ar" ? "rtl" : "ltr",
    setLocale,
    toggleLocale: () => setLocale(locale === "ar" ? "en" : "ar"),
    t: (arabic, english) => locale === "ar" ? arabic : english,
  }), [locale, setLocale]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) throw new Error("useLanguage must be used inside LanguageProvider");
  return context;
}

export const hasArabic = (value: string) => /[\u0600-\u06ff]/.test(value);