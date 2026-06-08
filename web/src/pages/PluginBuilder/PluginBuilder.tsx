import { useState } from 'react';
import { CodeBlock } from '../../components/CodeBlock';
import './PluginBuilder.css';

interface PluginConfig {
  name: string;
  version: string;
  description: string;
  author: string;
  entryPoint: string;
  dependencies: string[];
}

export function PluginBuilder() {
  const [config, setConfig] = useState<PluginConfig>({
    name: 'my-plugin',
    version: '1.0.0',
    description: 'My custom UHCR plugin',
    author: '',
    entryPoint: 'main.py',
    dependencies: [],
  });

  const [newDependency, setNewDependency] = useState('');

  const addDependency = () => {
    if (newDependency && !config.dependencies.includes(newDependency)) {
      setConfig({
        ...config,
        dependencies: [...config.dependencies, newDependency],
      });
      setNewDependency('');
    }
  };

  const removeDependency = (dep: string) => {
    setConfig({
      ...config,
      dependencies: config.dependencies.filter((d) => d !== dep),
    });
  };

  const generateToml = () => {
    return `[plugin]
name = "${config.name}"
version = "${config.version}"
description = "${config.description}"
author = "${config.author}"
entry_point = "${config.entryPoint}"

[dependencies]
${config.dependencies.map((dep) => `"${dep}"`).join('\n')}`;
  };

  const generatePythonTemplate = () => {
    return `"""
${config.description}
Author: ${config.author}
"""

from uhcr.plugin import PluginBase

class ${config.name.split('-').map(s => s.charAt(0).toUpperCase() + s.slice(1)).join('')}(PluginBase):
    """Custom UHCR plugin implementation."""
    
    def __init__(self):
        super().__init__()
        self.name = "${config.name}"
        self.version = "${config.version}"
    
    def initialize(self):
        """Initialize the plugin."""
        print(f"Initializing {self.name} v{self.version}")
        # Add your initialization code here
    
    def execute(self, *args, **kwargs):
        """Main plugin execution logic."""
        # Add your plugin logic here
        pass
    
    def cleanup(self):
        """Cleanup resources."""
        # Add cleanup code here
        pass

def register():
    """Register the plugin with UHCR."""
    return ${config.name.split('-').map(s => s.charAt(0).toUpperCase() + s.slice(1)).join('')}()`;
  };

  const downloadFile = (content: string, filename: string) => {
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="plugin-builder-page">
      <div className="plugin-builder-container">
        <header className="builder-header">
          <h1>🔌 UHCR Plugin Builder</h1>
          <p>Build and configure custom plugins for UHCR with this interactive tool</p>
        </header>

        <div className="builder-content">
          <div className="builder-form">
            <section className="form-section">
              <h2>Plugin Information</h2>
              
              <div className="form-group">
                <label htmlFor="plugin-name">Plugin Name</label>
                <input
                  id="plugin-name"
                  type="text"
                  value={config.name}
                  onChange={(e) => setConfig({ ...config, name: e.target.value })}
                  placeholder="my-custom-plugin"
                />
              </div>

              <div className="form-group">
                <label htmlFor="plugin-version">Version</label>
                <input
                  id="plugin-version"
                  type="text"
                  value={config.version}
                  onChange={(e) => setConfig({ ...config, version: e.target.value })}
                  placeholder="1.0.0"
                />
              </div>

              <div className="form-group">
                <label htmlFor="plugin-description">Description</label>
                <textarea
                  id="plugin-description"
                  value={config.description}
                  onChange={(e) => setConfig({ ...config, description: e.target.value })}
                  placeholder="Describe what your plugin does..."
                  rows={3}
                />
              </div>

              <div className="form-group">
                <label htmlFor="plugin-author">Author</label>
                <input
                  id="plugin-author"
                  type="text"
                  value={config.author}
                  onChange={(e) => setConfig({ ...config, author: e.target.value })}
                  placeholder="Your Name"
                />
              </div>

              <div className="form-group">
                <label htmlFor="plugin-entry">Entry Point</label>
                <input
                  id="plugin-entry"
                  type="text"
                  value={config.entryPoint}
                  onChange={(e) => setConfig({ ...config, entryPoint: e.target.value })}
                  placeholder="main.py"
                />
              </div>
            </section>

            <section className="form-section">
              <h2>Dependencies</h2>
              
              <div className="dependency-input">
                <input
                  type="text"
                  value={newDependency}
                  onChange={(e) => setNewDependency(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && addDependency()}
                  placeholder="Add dependency (e.g., numpy>=1.20.0)"
                />
                <button onClick={addDependency} className="btn btn-primary">
                  Add
                </button>
              </div>

              <ul className="dependency-list">
                {config.dependencies.map((dep) => (
                  <li key={dep} className="dependency-item">
                    <span>{dep}</span>
                    <button
                      onClick={() => removeDependency(dep)}
                      className="remove-btn"
                      aria-label={`Remove ${dep}`}
                    >
                      ×
                    </button>
                  </li>
                ))}
                {config.dependencies.length === 0 && (
                  <li className="no-dependencies">No dependencies added</li>
                )}
              </ul>
            </section>
          </div>

          <div className="builder-output">
            <section className="output-section">
              <div className="output-header">
                <h2>plugin.toml</h2>
                <button
                  onClick={() => downloadFile(generateToml(), 'plugin.toml')}
                  className="btn btn-secondary"
                >
                  Download
                </button>
              </div>
              <CodeBlock className="language-toml">{generateToml()}</CodeBlock>
            </section>

            <section className="output-section">
              <div className="output-header">
                <h2>{config.entryPoint}</h2>
                <button
                  onClick={() => downloadFile(generatePythonTemplate(), config.entryPoint)}
                  className="btn btn-secondary"
                >
                  Download
                </button>
              </div>
              <CodeBlock className="language-python">{generatePythonTemplate()}</CodeBlock>
            </section>

            <section className="installation-section">
              <h2>Installation Instructions</h2>
              <ol className="installation-steps">
                <li>
                  Create a new directory for your plugin:
                  <CodeBlock className="language-bash">
                    {`mkdir ${config.name}\ncd ${config.name}`}
                  </CodeBlock>
                </li>
                <li>
                  Download the generated files and place them in the plugin directory
                </li>
                <li>
                  Install your plugin:
                  <CodeBlock className="language-bash">
                    {`# Copy plugin to UHCR plugins directory\ncp -r ${config.name} ~/.uhcr/plugins/\n\n# Or install in development mode\npip install -e .`}
                  </CodeBlock>
                </li>
                <li>
                  Test your plugin:
                  <CodeBlock className="language-python">
                    {`import uhcr\nfrom uhcr.plugin import load_plugin\n\nplugin = load_plugin("${config.name}")\nplugin.initialize()\nplugin.execute()`}
                  </CodeBlock>
                </li>
              </ol>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
