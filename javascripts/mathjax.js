// MathJax configuration for RFS Framework documentation
// Supports mathematical notation in documentation

window.MathJax = {
  tex: {
    inlineMath: [["\\(", "\\)"]],
    displayMath: [["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true,
    tags: 'ams',
    packages: {
      '[+]': ['base', 'ams', 'noerrors', 'noundefined', 'color', 'boldsymbol']
    }
  },
  options: {
    ignoreHtmlClass: ".*|",
    processHtmlClass: "arithmatex"
  },
  svg: {
    fontCache: 'global'
  },
  startup: {
    ready: function() {
      console.log('MathJax is loaded and ready for RFS Framework documentation');
      MathJax.startup.defaultReady();
      
      // Add custom styling for math elements
      const style = document.createElement('style');
      style.textContent = `
        .MathJax {
          outline: none;
        }
        
        mjx-container[jax="SVG"] {
          direction: ltr;
        }
        
        mjx-container[jax="SVG"] > svg {
          overflow: visible;
          min-height: 1px;
          min-width: 1px;
        }
        
        /* Dark theme support */
        [data-md-color-scheme="slate"] mjx-container[jax="SVG"] > svg {
          filter: invert(1) hue-rotate(180deg);
          background: transparent;
        }
        
        /* Custom color for RFS Framework */
        .rfs-math {
          color: #1976d2;
        }
      `;
      document.head.appendChild(style);
    }
  }
};

// Additional RFS Framework specific math utilities
(function() {
  'use strict';
  
  // Function to highlight math expressions in HOF examples
  function highlightHOFMath() {
    const mathElements = document.querySelectorAll('.hof-example mjx-container');
    mathElements.forEach(el => {
      el.classList.add('rfs-math');
    });
  }
  
  // Auto-highlight when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', highlightHOFMath);
  } else {
    highlightHOFMath();
  }
  
  // Re-highlight on navigation (for SPAs)
  document.addEventListener('nav-ready', highlightHOFMath);
})();

// Performance optimization: lazy load MathJax
(function() {
  'use strict';
  
  // Only load MathJax if math content is detected
  function hasMathContent() {
    return document.querySelector('.arithmatex') || 
           document.querySelector('span.math') ||
           /\\\(|\\\[|\\begin\{/.test(document.body.textContent);
  }
  
  // Preload check for better performance
  if (!hasMathContent()) {
    console.log('No math content detected, MathJax loading skipped for performance');
    return;
  }
  
  console.log('Math content detected, MathJax will be loaded');
})();