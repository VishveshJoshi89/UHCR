import { useState } from "react";
import { Outlet } from "react-router-dom";

import { Header } from "../../components/Header";
import { Sidebar } from "../../components/Sidebar";

import { navigation } from "../../utils/navigation";

import "./DocsLayout.css";

export function DocsLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const toggleSidebar = () => {
    setSidebarOpen((prev) => !prev);
  };

  const closeSidebar = () => {
    setSidebarOpen(false);
  };

  return (
    <div className="docs-layout">
      <Header onMenuClick={toggleSidebar} />

      <Sidebar
        navigation={navigation}
        isOpen={sidebarOpen}
        onClose={closeSidebar}
      />

      <main className="docs-main">
        <Outlet />
      </main>
    </div>
  );
}
