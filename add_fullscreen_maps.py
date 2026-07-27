#!/usr/bin/env python3
"""Add fullscreen functionality to all HTML maps."""
import re
from pathlib import Path

FULLSCREEN_CSS = """
    .fullscreen-toggle {
      position: absolute;
      top: 10px;
      right: 10px;
      z-index: 1000;
      background: white;
      border: 2px solid #ccc;
      border-radius: 4px;
      padding: 8px;
      cursor: pointer;
      font-size: 14px;
      font-weight: bold;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .fullscreen-toggle:hover {
      background: #f5f5f5;
      border-color: #999;
    }
    .map-wrap {
      position: relative;
    }
    .map-wrap.fullscreen {
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      z-index: 10000;
      border-radius: 0;
      border: none;
    }
    .map-wrap.fullscreen #poiMap,
    .map-wrap.fullscreen #todoMap {
      height: 100vh !important;
      border-radius: 0;
    }
    body.map-fullscreen {
      overflow: hidden;
    }
"""

FULLSCREEN_JS = """
    function initFullscreenToggle() {
      const mapWraps = document.querySelectorAll('.map-wrap');
      mapWraps.forEach((wrap, idx) => {
        const mapId = wrap.querySelector('[id$="Map"]')?.id;
        if (!mapId) return;
        
        // Create toggle button
        const btn = document.createElement('button');
        btn.className = 'fullscreen-toggle';
        btn.innerHTML = '⛶ Helskärm';
        btn.title = 'Visa kartan i helskärm';
        
        btn.addEventListener('click', () => {
          wrap.classList.toggle('fullscreen');
          document.body.classList.toggle('map-fullscreen');
          btn.innerHTML = wrap.classList.contains('fullscreen') ? '⛶ Normal' : '⛶ Helskärm';
          
          // Invalidate map size after transition
          setTimeout(() => {
            const map = window[mapId.replace('Map', 'Map')];
            if (map?.invalidateSize) {
              map.invalidateSize();
            }
          }, 10);
          
          // ESC to exit
          const handleEsc = (e) => {
            if (e.key === 'Escape' && wrap.classList.contains('fullscreen')) {
              wrap.classList.remove('fullscreen');
              document.body.classList.remove('map-fullscreen');
              btn.innerHTML = '⛶ Helskärm';
              document.removeEventListener('keydown', handleEsc);
            }
          };
          document.addEventListener('keydown', handleEsc);
        });
        
        wrap.insertBefore(btn, wrap.firstChild);
      });
    }
"""

files_to_update = [
    Path("sat_poi_dashboard.html"),
    Path("sat_todo_map.html"),
]

for file_path in files_to_update:
    if not file_path.exists():
        print(f"⚠️  {file_path} not found")
        continue
    
    content = file_path.read_text(encoding="utf-8")
    
    # Add CSS to <style> tag
    if FULLSCREEN_CSS.strip() not in content:
        content = re.sub(
            r'(</style>)',
            FULLSCREEN_CSS + r'\1',
            content
        )
        print(f"✅ Added CSS to {file_path.name}")
    
    # Add JS initialization after page load
    if 'initFullscreenToggle' not in content:
        # Find the end of the main script
        init_call = f"    initFullscreenToggle();"
        content = re.sub(
            r'(applyFilters\(\);|displayResults\(\);)\s*(\n\s*\}\}\);)',
            r'\1\n' + init_call + r'\2',
            content
        )
        
        # Add function definition before closing script tag
        content = re.sub(
            r'(</script>)',
            FULLSCREEN_JS + r'\1',
            content
        )
        print(f"✅ Added fullscreen JS to {file_path.name}")
    
    file_path.write_text(content, encoding="utf-8")

print("\n✅ Fullscreen maps configured!")
