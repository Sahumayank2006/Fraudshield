import React, { useState, useEffect } from "react";
import { Header } from "./Header";
import { LeftRail, ScreenId } from "./LeftRail";

interface LayoutProps {
  activeScreen: ScreenId;
  onSelectScreen: (id: ScreenId) => void;
  openCasesCount?: number;
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({
  activeScreen,
  onSelectScreen,
  openCasesCount = 0,
  children,
}) => {
  const [theme, setTheme] = useState<"light" | "dark">("light");

  // Load saved theme from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("fraudshield_theme");
    if (saved === "dark" || saved === "light") {
      setTheme(saved);
      document.documentElement.setAttribute("data-theme", saved);
    }
  }, []);

  const handleToggleTheme = () => {
    const nextTheme = theme === "light" ? "dark" : "light";
    setTheme(nextTheme);
    localStorage.setItem("fraudshield_theme", nextTheme);
    document.documentElement.setAttribute("data-theme", nextTheme);
  };

  const handleEnterPresentMode = () => {
    // Will be fully wired in Present Mode phase
    window.dispatchEvent(new CustomEvent("enter_present_mode"));
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      {/* Top Operations Header */}
      <Header
        theme={theme}
        onToggleTheme={handleToggleTheme}
        onEnterPresentMode={handleEnterPresentMode}
      />

      {/* Main Split: Left Rail + Workspace */}
      <div style={{ display: "flex", flex: 1, minHeight: "calc(100vh - var(--header-height))" }}>
        <LeftRail
          activeScreen={activeScreen}
          onSelectScreen={onSelectScreen}
          openCasesCount={openCasesCount}
        />

        {/* Asymmetric 12-Column Main Workspace */}
        <main
          style={{
            flex: 1,
            backgroundColor: "var(--paper)",
            padding: "var(--space-6) var(--space-8)",
            overflowY: "auto",
            maxWidth: "var(--max-content-width)",
          }}
        >
          {children}
        </main>
      </div>
    </div>
  );
};

