import { Link } from 'react-router-dom';
import { CodeBlock } from '../CodeBlock';
import logo from '../../assets/logo.png';
import './Hero.css';

export function Hero() {
  const codeExample = `import uhcr

@uhcr.jit(eager=True)
def compute(a, b):
    return (a + b) * 2

result = compute(10, 11)
print(result)  # 42`;

  return (
    <div className="hero">
      <div className="hero-content">
        <div className="hero-main">
          <img src={logo} alt="UHCR" className="hero-logo" />
          
          <h1 className="hero-title">
            Universal Hardware-Aware Compute Runtime
          </h1>
          
          <p className="hero-subtitle">
            High-performance Python JIT runtime for modern hardware. Ship faster compute with JIT compilation, hardware-aware dispatch, and powerful plugin extensibility.
          </p>

          <div className="hero-actions">
            <Link to="/docs/quickstart" className="btn btn-primary">
              Get Started
            </Link>
            <Link to="/plugin-builder" className="btn btn-secondary">
              🔌 Build a Plugin
            </Link>
            <Link to="/docs/guides" className="btn btn-secondary">
              Explore Docs
            </Link>
          </div>
        </div>

        <div className="hero-code">
          <CodeBlock className="language-python">
            {codeExample}
          </CodeBlock>
        </div>
      </div>

      <div className="hero-features">
        <div className="feature-card">
          <div className="feature-icon">⚡</div>
          <h3>Hardware-Aware Performance</h3>
          <p>Automatic backend selection and IR optimizations for CPUs, GPUs, and multiple ISAs</p>
        </div>

        <div className="feature-card">
          <div className="feature-icon">🚀</div>
          <h3>Dynamic JIT Compilation</h3>
          <p>Trace Python functions and compile them to native machine code with backend-specific optimization</p>
        </div>

        <div className="feature-card">
          <div className="feature-icon">🔌</div>
          <h3>Plugin Architecture</h3>
          <p>Extend UHCR with custom backends, kernels, and passes via TOML manifests</p>
        </div>

        <div className="feature-card">
          <div className="feature-icon">📊</div>
          <h3>Built-in Benchmarks</h3>
          <p>Performance measurement suite for comparing execution paths and optimizing workloads</p>
        </div>
      </div>
    </div>
  );
}
