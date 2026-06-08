import { useState } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import './CodeBlock.css';

interface CodeBlockProps {
  children: string;
  className?: string;
  inline?: boolean;
}

export function CodeBlock({ children, className, inline }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const match = /language-(\w+)/.exec(className || '');
  const language = match ? match[1] : '';

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(children);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy code:', err);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleCopy();
    }
  };

  if (inline) {
    return <code className="inline-code">{children}</code>;
  }

  const theme = document.documentElement.getAttribute('data-theme') === 'dark' ? oneDark : oneLight;

  return (
    <div className="code-block-wrapper">
      <div className="code-block-header">
        {language && <span className="code-language">{language}</span>}
        <button
          className="copy-button"
          onClick={handleCopy}
          onKeyDown={handleKeyDown}
          aria-label="Copy code to clipboard"
          tabIndex={0}
        >
          {copied ? (
            <span className="copy-feedback">✓ Copied!</span>
          ) : (
            <span className="copy-icon">📋 Copy</span>
          )}
        </button>
      </div>
      <SyntaxHighlighter
        language={language || 'text'}
        style={theme}
        customStyle={{
          margin: 0,
          borderRadius: '0 0 8px 8px',
          fontSize: '0.9rem',
        }}
      >
        {children}
      </SyntaxHighlighter>
    </div>
  );
}
