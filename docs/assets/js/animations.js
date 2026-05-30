// Advanced animations for UHCR documentation

document.addEventListener('DOMContentLoaded', function() {
  
  // Animated gradient background for hero section
  createAnimatedBackground();
  
  // Typing animation for code examples
  animateCodeExamples();
  
  // Scroll reveal animations
  initScrollReveal();
  
  // Particle effect for hero
  initParticles();
});

// Create animated gradient background
function createAnimatedBackground() {
  const hero = document.querySelector('.fs-9');
  if (!hero) return;
  
  const canvas = document.createElement('canvas');
  canvas.className = 'hero-canvas';
  canvas.style.position = 'fixed';
  canvas.style.top = '0';
  canvas.style.left = '0';
  canvas.style.width = '100%';
  canvas.style.height = '100%';
  canvas.style.zIndex = '-1';
  canvas.style.opacity = '0.1';
  canvas.style.pointerEvents = 'none';
  
  document.body.insertBefore(canvas, document.body.firstChild);
  
  const ctx = canvas.getContext('2d');
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  
  let time = 0;
  
  function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Create flowing gradient waves
    const gradient = ctx.createLinearGradient(
      0, 0,
      canvas.width * Math.cos(time * 0.001),
      canvas.height * Math.sin(time * 0.001)
    );
    
    gradient.addColorStop(0, 'rgba(102, 126, 234, 0.3)');
    gradient.addColorStop(0.5, 'rgba(118, 75, 162, 0.3)');
    gradient.addColorStop(1, 'rgba(102, 126, 234, 0.3)');
    
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    time++;
    requestAnimationFrame(animate);
  }
  
  animate();
  
  window.addEventListener('resize', function() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  });
}

// Animate code examples with typing effect
function animateCodeExamples() {
  const codeBlocks = document.querySelectorAll('.highlight code');
  
  codeBlocks.forEach(function(block, index) {
    // Only animate the first code block on the page
    if (index === 0 && block.textContent.length < 200) {
      const originalText = block.textContent;
      block.textContent = '';
      
      let charIndex = 0;
      const typingSpeed = 20;
      
      function typeChar() {
        if (charIndex < originalText.length) {
          block.textContent += originalText.charAt(charIndex);
          charIndex++;
          setTimeout(typeChar, typingSpeed);
        }
      }
      
      // Start typing after a short delay
      setTimeout(typeChar, 500);
    }
  });
}

// Scroll reveal animations
function initScrollReveal() {
  const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -100px 0px'
  };
  
  const observer = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('revealed');
        observer.unobserve(entry.target);
      }
    });
  }, observerOptions);
  
  // Observe all major content sections
  const elements = document.querySelectorAll('h2, h3, .highlight, table, blockquote');
  elements.forEach(function(el) {
    el.classList.add('reveal-element');
    observer.observe(el);
  });
}

// Particle effect for hero section
function initParticles() {
  const hero = document.querySelector('.fs-9');
  if (!hero) return;
  
  const particleContainer = document.createElement('div');
  particleContainer.className = 'particle-container';
  particleContainer.style.position = 'fixed';
  particleContainer.style.top = '0';
  particleContainer.style.left = '0';
  particleContainer.style.width = '100%';
  particleContainer.style.height = '100%';
  particleContainer.style.zIndex = '-1';
  particleContainer.style.pointerEvents = 'none';
  particleContainer.style.overflow = 'hidden';
  
  document.body.insertBefore(particleContainer, document.body.firstChild);
  
  // Create particles
  for (let i = 0; i < 50; i++) {
    createParticle(particleContainer);
  }
}

function createParticle(container) {
  const particle = document.createElement('div');
  particle.className = 'particle';
  
  const size = Math.random() * 4 + 2;
  const startX = Math.random() * window.innerWidth;
  const startY = Math.random() * window.innerHeight;
  const duration = Math.random() * 20 + 10;
  const delay = Math.random() * 5;
  
  particle.style.position = 'absolute';
  particle.style.width = size + 'px';
  particle.style.height = size + 'px';
  particle.style.borderRadius = '50%';
  particle.style.background = 'rgba(99, 102, 241, 0.5)';
  particle.style.left = startX + 'px';
  particle.style.top = startY + 'px';
  particle.style.animation = `float ${duration}s ${delay}s infinite ease-in-out`;
  
  container.appendChild(particle);
}

// Add CSS for animations
const style = document.createElement('style');
style.textContent = `
  @keyframes float {
    0%, 100% {
      transform: translate(0, 0) scale(1);
      opacity: 0;
    }
    10% {
      opacity: 0.5;
    }
    50% {
      transform: translate(${Math.random() * 200 - 100}px, ${Math.random() * 200 - 100}px) scale(1.5);
      opacity: 0.8;
    }
    90% {
      opacity: 0.5;
    }
  }
  
  .reveal-element {
    opacity: 0;
    transform: translateY(30px);
    transition: opacity 0.6s ease, transform 0.6s ease;
  }
  
  .reveal-element.revealed {
    opacity: 1;
    transform: translateY(0);
  }
  
  .particle-container {
    filter: blur(1px);
  }
`;

document.head.appendChild(style);

// Add performance monitoring
let lastScrollTime = Date.now();
let scrollCount = 0;

window.addEventListener('scroll', function() {
  const now = Date.now();
  if (now - lastScrollTime < 100) {
    scrollCount++;
  } else {
    scrollCount = 0;
  }
  lastScrollTime = now;
  
  // Disable animations if scrolling too fast (performance optimization)
  if (scrollCount > 5) {
    document.body.classList.add('fast-scroll');
  } else {
    document.body.classList.remove('fast-scroll');
  }
});
