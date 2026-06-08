import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import type { NavItem } from '../../types';
import './Sidebar.css';

interface SidebarProps {
  navigation: NavItem[];
  isOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ navigation, isOpen, onClose }: SidebarProps) {
  const location = useLocation();
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['getting-started', 'guides', 'reference', 'architecture']));

  const toggleSection = (id: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const isActive = (path: string) => location.pathname === path;

  const renderNavItem = (item: NavItem, depth: number = 0) => {
    const hasChildren = item.children && item.children.length > 0;
    const isExpanded = expandedSections.has(item.id);
    const active = isActive(item.path);

    return (
      <li key={item.id} className="nav-item" style={{ '--depth': depth } as React.CSSProperties}>
        <div className="nav-item-content">
          {hasChildren && (
            <button
              className="expand-button"
              onClick={() => toggleSection(item.id)}
              aria-label={`${isExpanded ? 'Collapse' : 'Expand'} ${item.label}`}
              aria-expanded={isExpanded}
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                className={`expand-icon ${isExpanded ? 'expanded' : ''}`}
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 9l3 3 3-3" />
              </svg>
            </button>
          )}
          
          <Link
            to={item.path}
            className={`nav-link ${active ? 'active' : ''}`}
            onClick={onClose}
          >
            {item.label}
          </Link>
        </div>

        {hasChildren && isExpanded && (
          <ul className="nav-children">
            {item.children?.map((child) => renderNavItem(child, depth + 1))}
          </ul>
        )}
      </li>
    );
  };

  return (
    <>
      {isOpen && <div className="sidebar-overlay" onClick={onClose} />}
      
      <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
        <nav className="sidebar-nav" aria-label="Documentation navigation">
          <ul className="nav-list">
            {navigation.map((item) => renderNavItem(item))}
          </ul>
        </nav>
      </aside>
    </>
  );
}
