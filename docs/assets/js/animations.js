// ============================================================================
// UHCR Documentation - Subtle Animations
// Smooth, professional, and performance-optimized
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
  // Only add subtle animations, no overwhelming effects
  initScrollReveal();
});

// ============================================================================
// SCROLL REVEAL - Subtle fade-in on scroll
// ============================================================================
function initScrollReveal() {
  // Check if user prefers reduced motion
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  
  if (prefersReducedMotion) {
    // Skip animations if user prefers reduced motion
    return;
  }
  
  const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
  };
  
  const observer = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('revealed');
        // Stop observing once revealed
        observer.unobserve(entry.target);
      }
    });
  }, observerOptions);
  
  // Observe major content sections (but not everything)
  const elements = document.querySelectorAll('.main-content > h2, .main-content > .highlight, .main-content > table');
  
  elements.forEach(function(el) {
    el.classList.add('reveal-element');
    observer.observe(el);
  });
}

// Add CSS for reveal animation
const style = document.createElement('style');
style.textContent = `
  /* Subtle reveal animation */
  .reveal-element {
    opacity: 0;
    transform: translateY(15px);
    transition: opacity 0.4s ease-out, transform 0.4s ease-out;
  }
  
  .reveal-element.revealed {
    opacity: 1;
    transform: translateY(0);
  }
  
  /* Respect user preferences */
  @media (prefers-reduced-motion: reduce) {
    .reveal-element {
      opacity: 1;
      transform: none;
      transition: none;
    }
  }
`;

document.head.appendChild(style);
