
<section class="hero-panel">
  <div class="hero-copy">
    <p class="eyebrow">High-performance Python JIT runtime for modern hardware</p>
    <h1>UHCR</h1>
    <p class="hero-lead">Universal Hardware-Aware Compute Runtime for Python developers. Ship faster compute with JIT compilation, hardware-aware dispatch, and powerful plugin extensibility.</p>
    <div class="hero-actions">
      <a class="btn btn-primary" href="#quick-start">Get Started</a>
      <a class="btn" href="{{ '/quickstart/' | relative_url }}">Explore the docs</a>
    </div>
  </div>

  <div class="hero-panel-card">
    <div class="hero-panel-card-inner">
      <h2>Ship production-ready compute on every device</h2>
      <ul class="hero-feature-list">
        <li><strong>Hardware-aware performance</strong> for CPUs, GPUs, and multiple ISAs</li>
        <li><strong>Dynamic JIT compilation</strong> with backend-specific optimization</li>
        <li><strong>Plugin architecture</strong> for custom kernels and passes</li>
        <li><strong>Polished documentation</strong> with fast search and offline support</li>
      </ul>
    </div>
  </div>
</section>

<section class="section-surface">
  <div class="section-grid">
    <article class="section-card">
      <h2>What is UHCR?</h2>
      <p>UHCR compiles a custom intermediate representation (IR) to native machine code at runtime while selecting the optimal backend for your hardware.</p>
      <ul>
        <li><strong>JIT Compilation</strong> — trace Python functions and compile them to native instructions</li>
        <li><strong>Hardware Detection</strong> — automatic CPUID, GPU discovery, and cache-aware execution</li>
        <li><strong>Backend Flexibility</strong> — CUDA, AVX2, AVX512, and generic CPU support</li>
      </ul>
    </article>

    <article class="section-card">
      <h2>Quick Start</h2>
      <p>Install UHCR and run a compiled function in seconds.</p>
      <div class="code-panel">
        <pre><code class="language-bash">pip install uhcr</code></pre>
      </div>
      <div class="code-panel">
        <pre><code class="language-python">import uhcr

@uhcr.jit(eager=True)
def compute(a, b):
    return (a + b) * 2

result = compute(10, 11)
print(result)  # 42</code></pre>
      </div>
    </article>
  </div>

  <div class="docs-grid">
    <a class="card-link" href="{{ '/quickstart/' | relative_url }}">
      <h3>Quick Start</h3>
      <p>Get up and running with installation and first examples.</p>
    </a>
    <a class="card-link" href="{{ '/jit-guide/' | relative_url }}">
      <h3>JIT Guide</h3>
      <p>Learn how to trace and compile Python functions with UHCR.</p>
    </a>
    <a class="card-link" href="{{ '/api-reference/' | relative_url }}">
      <h3>API Reference</h3>
      <p>Browse every module, class, and supported backend API.</p>
    </a>
    <a class="card-link" href="{{ '/architecture/' | relative_url }}">
      <h3>Architecture</h3>
      <p>Explore UHCR's runtime, compiler, and storage design.</p>
    </a>
  </div>
</section>

<section class="section-surface alternate" id="quick-start">
  <h2>Built for developers and hardware teams</h2>
  <div class="feature-grid">
    <div class="feature-block">
      <strong>Performance-first</strong>
      <p>Automatic backend selection and IR optimizations tuned for real workloads.</p>
    </div>
    <div class="feature-block">
      <strong>Extensible</strong>
      <p>Custom plugin support lets you extend UHCR with new backends and passes.</p>
    </div>
    <div class="feature-block">
      <strong>Modern docs</strong>
      <p>Responsive guides, search, and offline-ready content for every device.</p>
    </div>
    <div class="feature-block">
      <strong>Hardware aware</strong>
      <p>Detects CPU, GPU, and platform details to choose the best execution path.</p>
    </div>
  </div>
</section>

<section class="section-surface footer-summary">
  <h2>Documentation at a glance</h2>
  <p>Browse comprehensive guides, reference material, and hardware documentation that help you build fast, reliable applications with UHCR.</p>
  <div class="hero-actions">
    <a class="btn btn-primary" href="{{ '/features/' | relative_url }}">Explore features</a>
    <a class="btn" href="{{ '/plugins/' | relative_url }}">Explore plugins</a>
  </div>
</section>
