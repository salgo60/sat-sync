#!/usr/bin/env python3
"""Patch HTML to handle unknown POIs rendering."""
import re
from pathlib import Path

html_file = Path("sat_poi_dashboard.html")
html = html_file.read_text(encoding="utf-8")

# Find the renderMap function and update marker creation for unknown POIs
old_pattern = r'function renderMap\(.*?\{[\s\S]*?L\.marker\(\[poi\.lat, poi\.lon\], \{icon: createPoiIcon\(poi\.category\)\}\)'

# Create new pattern that checks for isUnknown
new_code = '''function renderMap(sec, org, cat) {
      if (map) {
        map.eachLayer((layer) => {
          if (layer instanceof L.Marker) map.removeLayer(layer);
        });
      }

      const filtered = filteredPois(sec, org, cat);
      
      filtered.forEach((poi) => {
        if (!poi.lat || !poi.lon) return;
        
        // Create marker - gray for unknown POIs
        const markerOptions = poi.isUnknown ? {
          icon: L.divIcon({
            className: 'poi-icon',
            html: '?',
            iconSize: [24, 24],
            title: 'Okänd POI (ej i SAT)'
          })
        } : {
          icon: createPoiIcon(poi.category)
        };
        
        const marker = L.marker([poi.lat, poi.lon], markerOptions);
        
        // Create popup content
        let popupContent;
        if (poi.isUnknown) {
          popupContent = `<div style="text-align:center;padding:8px;min-width:200px;">
            <strong>${poi.name || 'Okänd'}</strong><br/>
            <small style="color:#888;">Okänd POI (ej i SAT)</small><br/>
            <a href="${poi.satMapUrl}" target="_blank" style="color:#1d4ed8;text-decoration:none;font-weight:bold;">
              🗺️ Se på interaktiv karta
            </a>
          </div>`;
        } else {
          // Regular popup for known POIs
          popupContent = `<div style="font-weight:bold">${poi.name || 'Ingen namn'}</div>...`;
        }
        
        marker.bindPopup(popupContent);
        marker.addTo(map);
      });
    }'''

# This is complex - let's take a simpler approach and add handlers to existing code
# Find where markers are created and modify the pattern
marker_pattern = r'L\.marker\(\[poi\.lat, poi\.lon\], \{icon: createPoiIcon\(poi\.category\)\}\)\.bindPopup\(popupContent\)'
marker_replacement = '''L.marker([poi.lat, poi.lon], {
        icon: poi.isUnknown ? 
          L.divIcon({className: 'poi-icon', html: '?', iconSize: [24, 24]}) :
          createPoiIcon(poi.category)
      })
      .bindPopup(poi.isUnknown ? 
        `<div style="text-align:center;padding:8px;min-width:200px;">
          <strong>${poi.name}</strong><br/>
          <small style="color:#888;">Okänd POI (ej i SAT)</small><br/>
          <a href="${poi.satMapUrl}" target="_blank" style="color:#1d4ed8;text-decoration:none;font-weight:bold;">
            🗺️ Se på interaktiv karta
          </a>
        </div>` : 
        popupContent)'''

if re.search(marker_pattern, html):
    html = re.sub(marker_pattern, marker_replacement, html)
    print("✅ Updated marker creation for unknown POIs")
else:
    print("⚠️  Could not find exact marker pattern, searching for partial match...")
    # Try to find just the marker creation
    if 'L.marker([poi.lat, poi.lon]' in html:
        print("✅ Found marker creation code - needs manual review")

html_file.write_text(html, encoding="utf-8")
