#!/usr/bin/env python3
"""Generate sat_about.html — About page for the SAT POI toolset."""

import datetime
import os

OUTPUT = os.path.join(os.path.dirname(__file__), "sat_about.html")
GENERATED_AT = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC")

HTML = f"""\
<!DOCTYPE html>
<html lang="sv">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title id="page-title-el">ℹ️ Om SAT POI-verktygen</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f1f5f9; color: #1e293b; line-height: 1.7; }}
    .header {{ background: linear-gradient(135deg,#2546a8,#1d2f6f); color:#fff; padding: 24px; }}
    .header h1 {{ margin: 0 0 6px; font-size: 1.6rem; }}
    .header-meta {{ margin-top: 10px; font-size: 0.8rem; opacity: 0.75; }}
    .header-meta a {{ color: #a8c4ff; text-decoration: none; }}
    .header-meta a:hover {{ text-decoration: underline; }}
    .lang-btn {{ background: rgba(255,255,255,.2); color: #fff; border: 1px solid rgba(255,255,255,.5);
                 border-radius: 6px; padding: 4px 12px; font-size: .75rem; font-weight: 600;
                 cursor: pointer; margin-left: 10px; vertical-align: middle; }}
    .lang-btn:hover {{ background: rgba(255,255,255,.35); }}
    main {{ max-width: 860px; margin: 32px auto; padding: 0 16px; }}
    section {{ background: #fff; border-radius: 12px; padding: 28px; margin-bottom: 24px;
               box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
    section h2 {{ font-size: 1.15rem; color: #2546a8; margin-bottom: 12px; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; }}
    section h3 {{ font-size: 1rem; color: #334155; margin: 16px 0 6px; }}
    p {{ margin-bottom: 10px; color: #374151; }}
    ul {{ padding-left: 20px; margin-bottom: 10px; color: #374151; }}
    ul li {{ margin-bottom: 5px; }}
    a {{ color: #2546a8; }}
    a:hover {{ text-decoration: underline; }}
    .card-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px,1fr)); gap: 14px; }}
    .tool-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; text-decoration: none; color: inherit; display: block; transition: box-shadow .2s; }}
    .tool-card:hover {{ box-shadow: 0 4px 12px rgba(0,0,0,.1); text-decoration: none; }}
    .tool-card .icon {{ font-size: 1.8rem; margin-bottom: 8px; }}
    .tool-card h3 {{ font-size: .95rem; color: #2546a8; margin: 0 0 4px; }}
    .tool-card p {{ font-size: .82rem; color: #64748b; margin: 0; }}
    .source-table {{ width: 100%; border-collapse: collapse; font-size: .88rem; }}
    .source-table th {{ background: #f1f5f9; text-align: left; padding: 8px 10px; border-bottom: 2px solid #e2e8f0; }}
    .source-table td {{ padding: 7px 10px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }}
    .badge {{ display: inline-block; background: #dbeafe; color: #1e40af; border-radius: 6px;
              padding: 2px 8px; font-size: .75rem; font-weight: 600; }}
    .footer {{ text-align: center; font-size: .8rem; color: #94a3b8; padding: 24px; }}
    @media(max-width:600px) {{ .header h1 {{ font-size: 1.2rem; }} main {{ padding: 0 10px; }} }}
  </style>
</head>
<body>

<div class="header">
  <h1 id="page-h1">ℹ️ Om SAT POI-verktygen</h1>
  <p id="page-subtitle">Dokumentation och bakgrund för Stockholm Archipelago Trail POI-verktyg</p>
  <div class="header-meta">
    <a href="sat_poi_dashboard.html" id="nav-dashboard">🧭 Dashboard</a> &nbsp;|&nbsp;
    <a href="sat_todo_map.html" id="nav-todo">🗺️ TODO-karta</a> &nbsp;|&nbsp;
    <a href="sat_todo_list.html" id="nav-todo-list">✅ TODO-lista</a> &nbsp;|&nbsp;
    <a href="sat_poi_quality_history.html" id="nav-quality">📈 Datakvalitet</a> &nbsp;|&nbsp;
    <a href="sat_osm_ref_report.html" id="nav-osm-report">📊 OSM-egenskaper</a> &nbsp;|&nbsp;
    <a href="sat_osm_trail_report.html" id="nav-trail-report">🥾 Ledegenskaper</a> &nbsp;|&nbsp;
    <a href="whats_new.html" id="nav-whatsnew">What's new</a> &nbsp;|&nbsp;
    <a href="https://github.com/salgo60/sat-sync" target="_blank">GitHub</a>
    <button class="lang-btn" id="lang-btn" onclick="toggleLang()">English</button>
  </div>
</div>

<main>

  <section>
    <h2 id="sec-latest-title">🆕 Senaste: OSM-egenskaper på leden (september 2026)</h2>
    <ul id="sec-latest-list">
      <li>Den nya <a href="sat_osm_trail_report.html"><strong>ledrapporten</strong></a> följer OSM:s hierarki från superrelationen till 20 etapprelationer.</li>
      <li>Den sammanställer egenskaper för 769 unika vägar och noder som leden följer.</li>
      <li>Välj en etapp för att se dess relationstaggar, ledobjekt, taggtäckning och vanligaste värden.</li>
      <li>En ny infografik förklarar relationerna mellan hela leden, etapper, geometri och platser.</li>
    </ul>
  </section>

  <!-- ── What is this? ─────────────────────────────────────────────────── -->
  <section>
    <h2 id="sec-what-title">🧭 Vad är det här?</h2>
    <p id="sec-what-p1">Det här är en uppsättning öppna webbaserade verktyg för att följa och förbättra datakvaliteten hos POI (Points of Interest) längs <strong>Stockholm Archipelago Trail (SAT)</strong> — en vandringsled med 21 etapper/öar i Stockholms skärgård.</p>
    <p id="sec-what-p2">Verktygen hämtar data från SAT:s officiella API, OpenStreetMap (OSM) och Wikidata, och visar hur väl kopplingarna mellan dessa tre datakällor stämmer överens — och vad som saknas.</p>
  </section>

  <!-- ── Tools ─────────────────────────────────────────────────────────── -->
  <section>
    <h2 id="sec-tools-title">🛠️ Verktyg</h2>
    <div class="card-grid">
      <a class="tool-card" href="sat_poi_dashboard.html">
        <div class="icon">🧭</div>
        <h3 id="card-dashboard-title">SAT POI Dashboard</h3>
        <p id="card-dashboard-desc">Översikt över 743 SAT-POI med OSM- och Wikidata-kopplingar, filtrerbar per etapp, kategori, kommun och språk.</p>
      </a>
      <a class="tool-card" href="sat_todo_map.html">
        <div class="icon">🗺️</div>
        <h3 id="card-todo-title">TODO-karta</h3>
        <p id="card-todo-desc">Interaktiv karta som visar vad som saknas: OSM-koppling, Wikidata, bild, wheelchair-tagg samt inkonsekvenser mellan källorna.</p>
      </a>
      <a class="tool-card" href="sat_todo_list.html">
        <div class="icon">✅</div>
        <h3 id="card-todo-list-title">TODO-lista</h3>
        <p id="card-todo-list-desc">Uppgiftslista för fältarbete med filter per ö och objekttyp, checkboxar och export (JSON/CSV/Markdown).</p>
      </a>
      <a class="tool-card" href="sat_poi_quality_history.html">
        <div class="icon">📈</div>
        <h3 id="card-quality-title">Datakvalitet över tid</h3>
        <p id="card-quality-desc">Historisk vy av datakvaliteten per snapshot av pois.geojson — täckning per fält, kategori och etapp.</p>
      </a>
      <a class="tool-card" href="sat_osm_ref_report.html">
        <div class="icon">📊</div>
        <h3 id="card-osm-report-title">OSM-egenskaper</h3>
        <p id="card-osm-report-desc">1 099 SAT-kopplade OSM-objekt grupperade per funktion med taggtäckning, vanligaste värden och direktlänkar.</p>
      </a>
      <a class="tool-card" href="sat_osm_trail_report.html">
        <div class="icon">🥾</div>
        <h3 id="card-trail-report-title">OSM-egenskaper på leden</h3>
        <p id="card-trail-report-desc">Superrelation, 20 etapprelationer och statistik för 769 unika vägar/noder som leden följer.</p>
      </a>
      <a class="tool-card" href="whats_new.html">
        <div class="icon">📋</div>
        <h3 id="card-whatsnew-title">What's new</h3>
        <p id="card-whatsnew-desc">Ändringslogg med alla PR:s och förbättringar i verktygen.</p>
      </a>
    </div>
  </section>

  <!-- ── Data sources ───────────────────────────────────────────────────── -->
  <section>
    <h2 id="sec-sources-title">📡 Datakällor</h2>
    <table class="source-table">
      <thead>
        <tr>
          <th id="th-source">Källa</th>
          <th id="th-what">Vad</th>
          <th id="th-url">URL</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><span class="badge">SAT API</span></td>
          <td id="src-sat">743 POI med namn, koordinater, kategori, etapp och SAT-specifika metadata</td>
          <td><a href="https://map.stockholmarchipelagotrail.com/data/geojson/pois.geojson" target="_blank">pois.geojson</a></td>
        </tr>
        <tr>
          <td><span class="badge">OSM</span></td>
          <td id="src-osm">1 099 SAT-kopplade objekt med kompletta OSM-taggar, hämtade globalt via Overpass API</td>
          <td><a href="https://overpass-api.de/" target="_blank">overpass-api.de</a></td>
        </tr>
        <tr>
          <td><span class="badge">Wikidata</span></td>
          <td id="src-wd">Entitetsdata (P14545 SAT-ID, P402 OSM-ID, bilder, …) hämtad via SPARQL + Wikidata REST API</td>
          <td><a href="https://query.wikidata.org/" target="_blank">query.wikidata.org</a></td>
        </tr>
        <tr>
          <td><span class="badge">SAT Trail</span></td>
          <td id="src-trail">Etappgeometri (trail.jsonld) och sektionsindex (sections-index.json) för karta och filter</td>
          <td><a href="https://map.stockholmarchipelagotrail.com/" target="_blank">stockholmarchipelagotrail.com</a></td>
        </tr>
        <tr>
          <td><span class="badge">SAT AED</span></td>
          <td id="src-aed">Hjärtstartare (AED) längs leden — 32 platser med adress, öppettider och ägare</td>
          <td><a href="https://map.stockholmarchipelagotrail.com/api/aed" target="_blank">api/aed</a></td>
        </tr>
        <tr>
          <td><span class="badge">SAT Piers</span></td>
          <td id="src-piers">Bryggor/pirar längs leden — 66 poster med SAT-ID, slug och GTFS-kopplingar</td>
          <td><a href="https://map.stockholmarchipelagotrail.com/data/piers-identity.json" target="_blank">piers-identity.json</a></td>
        </tr>
      </tbody>
    </table>
  </section>

  <!-- ── How it works ───────────────────────────────────────────────────── -->
  <section>
    <h2 id="sec-how-title">⚙️ Hur fungerar det?</h2>
    <p id="sec-how-p1">Verktygen är helt statiska HTML-sidor som genereras av Python-skript (<code>generate_*.py</code>) och publiceras via <strong>GitHub Pages</strong> i repot <a href="https://github.com/salgo60/sat-sync" target="_blank">salgo60/sat-sync</a>.</p>
    <ul>
      <li id="sec-how-li1"><strong>generate_poi_dashboard.py</strong> — hämtar pois.geojson, Wikidata SPARQL och bygger sat_poi_dashboard.html</li>
      <li id="sec-how-li2"><strong>generate_todo_map.py</strong> — bygger den interaktiva Leaflet-kartan sat_todo_map.html</li>
      <li id="sec-how-li3"><strong>generate_todo_list.py</strong> — bygger en filtrerbar TODO-lista med checkboxar och export i sat_todo_list.html</li>
      <li id="sec-how-li4"><strong>generate_poi_quality_history.py</strong> — sparar ett snapshot av datakvaliteten när pois.geojson uppdateras</li>
      <li id="sec-how-li5"><strong>generate_osm_ref_report.py</strong> — grupperar alla SAT-kopplade OSM-objekt och räknar taggtäckning per kategori</li>
      <li id="sec-how-li6"><strong>generate_osm_trail_report.py</strong> — följer OSM-hierarkin superroute → etapprelation → ledsegment och sammanställer ledegenskaper</li>
      <li id="sec-how-li7"><strong>generate_about.py</strong> — genererar den här sidan</li>
    </ul>
    <p id="sec-how-p2">Dashboarden har stöd för 20+ språk. Om-sidan och flera arbetsverktyg har sv/en-språkbyte, medan specialrapporter kan vara enspråkiga.</p>
  </section>

  <!-- ── Contribute ─────────────────────────────────────────────────────── -->
  <section>
    <h2 id="sec-contrib-title">🤝 Bidra</h2>
    <p id="sec-contrib-p1">Alla förbättringsförslag, buggrapporter och pull requests välkomnas på GitHub:</p>
    <ul>
      <li><a href="https://github.com/salgo60/sat-sync/issues/new?title=F%C3%B6rb%C3%A4ttringsf%C3%B6rslag&labels=enhancement" target="_blank" id="link-issue">💡 Skapa ett förbättringsförslag</a></li>
      <li><a href="https://github.com/salgo60/sat-sync/issues" target="_blank" id="link-issues">📋 Se alla öppna ärenden</a></li>
      <li><a href="https://github.com/salgo60/sat-sync/pulls" target="_blank" id="link-prs">🔀 Se alla pull requests</a></li>
    </ul>
    <p id="sec-contrib-p2">Vill du förbättra OSM-data? Använd <strong>TODO-kartan</strong> för att hitta objekt med saknade taggar och redigera direkt via iD editor.</p>
  </section>

  <!-- ── License ────────────────────────────────────────────────────────── -->
  <section>
    <h2 id="sec-license-title">📄 Licens</h2>
    <p id="sec-license-p">Koden är öppen källkod under <a href="https://github.com/salgo60/sat-sync/blob/main/LICENSE" target="_blank">MIT-licensen</a>. Data från OSM och Wikidata distribueras under deras respektive öppna licenser (ODbL resp. CC0).</p>
  </section>

</main>

<div class="footer">
  <span id="footer-gen">Genererad</span>: {GENERATED_AT} &nbsp;|&nbsp;
  <a href="https://github.com/salgo60/sat-sync" target="_blank">salgo60/sat-sync</a>
</div>

<script>
(function() {{
  const i18n = {{
    sv: {{
      pageTitle: 'ℹ️ Om SAT POI-verktygen',
      h1: 'ℹ️ Om SAT POI-verktygen',
      subtitle: 'Dokumentation och bakgrund för Stockholm Archipelago Trail POI-verktyg',
      navDashboard: '🧭 Dashboard', navTodo: '🗺️ TODO-karta', navTodoList: '✅ TODO-lista',
      navQuality: '📈 Datakvalitet', navOsmReport: '📊 OSM-egenskaper', navTrailReport: '🥾 Ledegenskaper', navWhatsnew: "What's new",
      langBtn: 'English',
      secLatestTitle: '🆕 Senaste: OSM-egenskaper på leden (september 2026)',
      secLatestList: '<li>Den nya <a href="sat_osm_trail_report.html"><strong>ledrapporten</strong></a> följer OSM:s hierarki från superrelationen till 20 etapprelationer.</li><li>Den sammanställer egenskaper för 769 unika vägar och noder som leden följer.</li><li>Välj en etapp för att se dess relationstaggar, ledobjekt, taggtäckning och vanligaste värden.</li><li>En ny infografik förklarar relationerna mellan hela leden, etapper, geometri och platser.</li>',
      secWhatTitle: '🧭 Vad är det här?',
      secWhatP1: 'Det här är en uppsättning öppna webbaserade verktyg för att följa och förbättra datakvaliteten hos POI (Points of Interest) längs <strong>Stockholm Archipelago Trail (SAT)</strong> — en vandringsled med 21 etapper/öar i Stockholms skärgård.',
      secWhatP2: 'Verktygen hämtar data från SAT:s officiella API, OpenStreetMap (OSM) och Wikidata, och visar hur väl kopplingarna mellan dessa tre datakällor stämmer överens — och vad som saknas.',
      secToolsTitle: '🛠️ Verktyg',
      cardDashboardTitle: 'SAT POI Dashboard',
      cardDashboardDesc: 'Översikt över 743 SAT-POI med OSM- och Wikidata-kopplingar, filtrerbar per etapp, kategori, kommun och språk.',
      cardTodoTitle: 'TODO-karta',
      cardTodoDesc: 'Interaktiv karta som visar vad som saknas: OSM-koppling, Wikidata, bild, wheelchair-tagg samt inkonsekvenser mellan källorna.',
      cardTodoListTitle: 'TODO-lista',
      cardTodoListDesc: 'Uppgiftslista för fältarbete med filter per ö och objekttyp, checkboxar, OSM Notes-uppgifter och export (JSON/CSV/Markdown).',
      cardQualityTitle: 'Datakvalitet över tid',
      cardQualityDesc: 'Historisk vy av datakvaliteten per snapshot av pois.geojson — täckning per fält, kategori och etapp.',
      cardOsmReportTitle: 'OSM-egenskaper',
      cardOsmReportDesc: '1 099 SAT-kopplade OSM-objekt grupperade per funktion med taggtäckning, vanligaste värden och direktlänkar.',
      cardTrailReportTitle: 'OSM-egenskaper på leden',
      cardTrailReportDesc: 'Superrelation, 20 etapprelationer och statistik för 769 unika vägar/noder som leden följer.',
      cardWhatsnewTitle: "What's new",
      cardWhatsnewDesc: 'Ändringslogg med alla PR:s och förbättringar i verktygen.',
      secSourcesTitle: '📡 Datakällor',
      thSource: 'Källa', thWhat: 'Vad', thUrl: 'URL',
      srcSat: '743 POI med namn, koordinater, kategori, etapp och SAT-specifika metadata',
      srcOsm: '1 099 SAT-kopplade objekt med kompletta OSM-taggar, hämtade globalt via Overpass API',
      srcWd: 'Entitetsdata (P14545 SAT-ID, P402 OSM-ID, bilder, …) hämtad via SPARQL + Wikidata REST API',
      srcTrail: 'Etappgeometri (trail.jsonld) och sektionsindex (sections-index.json) för karta och filter',
      srcAed: 'Hjärtstartare (AED) längs leden — 32 platser med adress, öppettider och ägare',
      srcPiers: 'Bryggor/pirar längs leden — 66 poster med SAT-ID, slug och GTFS-kopplingar',
      secHowP1: 'Verktygen är helt statiska HTML-sidor som genereras av Python-skript (<code>generate_*.py</code>) och publiceras via <strong>GitHub Pages</strong> i repot <a href="https://github.com/salgo60/sat-sync" target="_blank">salgo60/sat-sync</a>.',
      secHowLi1: '<strong>generate_poi_dashboard.py</strong> — hämtar pois.geojson, Wikidata SPARQL och bygger sat_poi_dashboard.html',
      secHowLi2: '<strong>generate_todo_map.py</strong> — bygger den interaktiva Leaflet-kartan sat_todo_map.html',
      secHowLi3: '<strong>generate_todo_list.py</strong> — bygger en filtrerbar TODO-lista med checkboxar och export i sat_todo_list.html',
      secHowLi4: '<strong>generate_poi_quality_history.py</strong> — sparar ett snapshot av datakvaliteten när pois.geojson uppdateras',
      secHowLi5: '<strong>generate_osm_ref_report.py</strong> — grupperar alla SAT-kopplade OSM-objekt och räknar taggtäckning per kategori',
      secHowLi6: '<strong>generate_osm_trail_report.py</strong> — följer OSM-hierarkin superroute → etapprelation → ledsegment och sammanställer ledegenskaper',
      secHowLi7: '<strong>generate_about.py</strong> — genererar den här sidan',
      secHowP2: 'Dashboarden har stöd för 20+ språk. Om-sidan och flera arbetsverktyg har sv/en-språkbyte, medan specialrapporter kan vara enspråkiga.',
      secContribTitle: '🤝 Bidra',
      secContribP1: 'Alla förbättringsförslag, buggrapporter och pull requests välkomnas på GitHub:',
      linkIssue: '💡 Skapa ett förbättringsförslag',
      linkIssues: '📋 Se alla öppna ärenden',
      linkPrs: '🔀 Se alla pull requests',
      secContribP2: 'Vill du förbättra OSM-data? Använd <strong>TODO-kartan</strong> för att hitta objekt med saknade taggar och redigera direkt via iD editor.',
      secLicenseTitle: '📄 Licens',
      secLicenseP: 'Koden är öppen källkod under <a href="https://github.com/salgo60/sat-sync/blob/main/LICENSE" target="_blank">MIT-licensen</a>. Data från OSM och Wikidata distribueras under deras respektive öppna licenser (ODbL resp. CC0).',
      footerGen: 'Genererad',
    }},
    en: {{
      pageTitle: 'ℹ️ About the SAT POI tools',
      h1: 'ℹ️ About the SAT POI tools',
      subtitle: 'Documentation and background for the Stockholm Archipelago Trail POI toolset',
      navDashboard: '🧭 Dashboard', navTodo: '🗺️ TODO map', navTodoList: '✅ TODO list',
      navQuality: '📈 Data quality', navOsmReport: '📊 OSM properties', navTrailReport: '🥾 Trail properties', navWhatsnew: "What's new",
      langBtn: 'Svenska',
      secLatestTitle: '🆕 Latest: OSM trail properties (September 2026)',
      secLatestList: '<li>The new <a href="sat_osm_trail_report.html"><strong>trail report</strong></a> follows the OSM hierarchy from the superroute to 20 section relations.</li><li>It summarizes properties for the 769 unique ways and nodes followed by the trail.</li><li>Select a section to see its relation tags, trail objects, tag coverage, and common values.</li><li>A new infographic explains the relationships between the complete trail, sections, geometry, and places.</li>',
      secWhatTitle: '🧭 What is this?',
      secWhatP1: 'This is a set of open web-based tools for tracking and improving the data quality of POIs (Points of Interest) along the <strong>Stockholm Archipelago Trail (SAT)</strong> — a hiking trail across 21 stages/islands in the Stockholm archipelago.',
      secWhatP2: 'The tools fetch data from the SAT official API, OpenStreetMap (OSM), and Wikidata, and show how well the links between these three data sources align — and what is missing.',
      secToolsTitle: '🛠️ Tools',
      cardDashboardTitle: 'SAT POI Dashboard',
      cardDashboardDesc: 'Overview of 743 SAT POIs with OSM and Wikidata links, filterable by stage, category, municipality, and language.',
      cardTodoTitle: 'TODO map',
      cardTodoDesc: 'Interactive map showing what is missing: OSM link, Wikidata, image, wheelchair tag, and inconsistencies between sources.',
      cardTodoListTitle: 'TODO list',
      cardTodoListDesc: 'Task list for field work with island/type filters, checkboxes, OSM Notes tasks, and export (JSON/CSV/Markdown).',
      cardQualityTitle: 'Data quality over time',
      cardQualityDesc: 'Historical view of data quality per pois.geojson snapshot — coverage per field, category and stage.',
      cardOsmReportTitle: 'OSM properties',
      cardOsmReportDesc: '1,099 SAT-linked OSM objects grouped by function with tag coverage, common values, and direct links.',
      cardTrailReportTitle: 'OSM properties along the trail',
      cardTrailReportDesc: 'The superroute, 20 section relations, and statistics for the 769 unique ways/nodes followed by the trail.',
      cardWhatsnewTitle: "What's new",
      cardWhatsnewDesc: 'Changelog with all PRs and improvements to the tools.',
      secSourcesTitle: '📡 Data sources',
      thSource: 'Source', thWhat: 'What', thUrl: 'URL',
      srcSat: '743 POIs with name, coordinates, category, stage and SAT-specific metadata',
      srcOsm: '1,099 SAT-linked objects with complete OSM tags, fetched globally via the Overpass API',
      srcWd: 'Entity data (P14545 SAT ID, P402 OSM ID, images, …) fetched via SPARQL + Wikidata REST API',
      srcTrail: 'Stage geometry (trail.jsonld) and section index (sections-index.json) for map and filters',
      srcAed: 'Defibrillators (AED) along the trail — 32 locations with address, opening hours and owner',
      srcPiers: 'Piers along the trail — 66 entries with SAT ID, slug and GTFS links',
      secHowP1: 'The tools are fully static HTML pages generated by Python scripts (<code>generate_*.py</code>) and published via <strong>GitHub Pages</strong> in the repo <a href="https://github.com/salgo60/sat-sync" target="_blank">salgo60/sat-sync</a>.',
      secHowLi1: '<strong>generate_poi_dashboard.py</strong> — fetches pois.geojson, Wikidata SPARQL and builds sat_poi_dashboard.html',
      secHowLi2: '<strong>generate_todo_map.py</strong> — builds the interactive Leaflet map sat_todo_map.html',
      secHowLi3: '<strong>generate_todo_list.py</strong> — builds a filterable TODO list with checkboxes and export in sat_todo_list.html',
      secHowLi4: '<strong>generate_poi_quality_history.py</strong> — saves a data quality snapshot when pois.geojson is updated',
      secHowLi5: '<strong>generate_osm_ref_report.py</strong> — groups all SAT-linked OSM objects and calculates tag coverage by category',
      secHowLi6: '<strong>generate_osm_trail_report.py</strong> — follows the OSM hierarchy from superroute to section relation to trail segment and summarizes trail properties',
      secHowLi7: '<strong>generate_about.py</strong> — generates this page',
      secHowP2: 'The dashboard supports 20+ languages. The About page and several working tools support Swedish/English switching, while specialist reports may be monolingual.',
      secContribTitle: '🤝 Contribute',
      secContribP1: 'All suggestions, bug reports and pull requests are welcome on GitHub:',
      linkIssue: '💡 Create a feature request',
      linkIssues: '📋 View all open issues',
      linkPrs: '🔀 View all pull requests',
      secContribP2: 'Want to improve OSM data? Use the <strong>TODO map</strong> to find objects with missing tags and edit directly via iD editor.',
      secLicenseTitle: '📄 License',
      secLicenseP: 'The code is open source under the <a href="https://github.com/salgo60/sat-sync/blob/main/LICENSE" target="_blank">MIT license</a>. Data from OSM and Wikidata is distributed under their respective open licenses (ODbL and CC0).',
      footerGen: 'Generated',
    }},
  }};

  let lang = 'sv';
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get('lang') === 'en') lang = 'en';

  const ids = [
    'page-h1','page-subtitle','nav-dashboard','nav-todo','nav-todo-list','nav-quality','nav-osm-report','nav-trail-report','nav-whatsnew','lang-btn',
    'sec-latest-title','sec-latest-list','sec-what-title','sec-what-p1','sec-what-p2','sec-tools-title',
    'card-dashboard-title','card-dashboard-desc','card-todo-title','card-todo-desc','card-todo-list-title','card-todo-list-desc',
    'card-quality-title','card-quality-desc','card-osm-report-title','card-osm-report-desc','card-trail-report-title','card-trail-report-desc','card-whatsnew-title','card-whatsnew-desc',
    'sec-sources-title','th-source','th-what','th-url',
    'src-sat','src-osm','src-wd','src-trail','src-aed','src-piers',
    'sec-how-title','sec-how-p1','sec-how-li1','sec-how-li2','sec-how-li3','sec-how-li4','sec-how-li5','sec-how-li6','sec-how-li7','sec-how-p2',
    'sec-contrib-title','sec-contrib-p1','link-issue','link-issues','link-prs','sec-contrib-p2',
    'sec-license-title','sec-license-p','footer-gen',
  ];

  const idToKey = {{
    'page-h1':'h1','page-subtitle':'subtitle',
    'nav-dashboard':'navDashboard','nav-todo':'navTodo','nav-todo-list':'navTodoList','nav-quality':'navQuality','nav-osm-report':'navOsmReport','nav-trail-report':'navTrailReport','nav-whatsnew':'navWhatsnew',
    'lang-btn':'langBtn',
    'sec-latest-title':'secLatestTitle','sec-latest-list':'secLatestList',
    'sec-what-title':'secWhatTitle','sec-what-p1':'secWhatP1','sec-what-p2':'secWhatP2',
    'sec-tools-title':'secToolsTitle',
    'card-dashboard-title':'cardDashboardTitle','card-dashboard-desc':'cardDashboardDesc',
    'card-todo-title':'cardTodoTitle','card-todo-desc':'cardTodoDesc',
    'card-todo-list-title':'cardTodoListTitle','card-todo-list-desc':'cardTodoListDesc',
    'card-quality-title':'cardQualityTitle','card-quality-desc':'cardQualityDesc',
    'card-osm-report-title':'cardOsmReportTitle','card-osm-report-desc':'cardOsmReportDesc',
    'card-trail-report-title':'cardTrailReportTitle','card-trail-report-desc':'cardTrailReportDesc',
    'card-whatsnew-title':'cardWhatsnewTitle','card-whatsnew-desc':'cardWhatsnewDesc',
    'sec-sources-title':'secSourcesTitle','th-source':'thSource','th-what':'thWhat','th-url':'thUrl',
    'src-sat':'srcSat','src-osm':'srcOsm','src-wd':'srcWd','src-trail':'srcTrail',
    'src-aed':'srcAed','src-piers':'srcPiers',
    'sec-how-title':'secHowTitle','sec-how-p1':'secHowP1',
    'sec-how-li1':'secHowLi1','sec-how-li2':'secHowLi2','sec-how-li3':'secHowLi3','sec-how-li4':'secHowLi4','sec-how-li5':'secHowLi5','sec-how-li6':'secHowLi6','sec-how-li7':'secHowLi7',
    'sec-how-p2':'secHowP2',
    'sec-contrib-title':'secContribTitle','sec-contrib-p1':'secContribP1',
    'link-issue':'linkIssue','link-issues':'linkIssues','link-prs':'linkPrs',
    'sec-contrib-p2':'secContribP2',
    'sec-license-title':'secLicenseTitle','sec-license-p':'secLicenseP',
    'footer-gen':'footerGen',
  }};

  function applyLanguage() {{
    const d = i18n[lang];
    document.documentElement.lang = lang;
    document.title = d.pageTitle;
    document.getElementById('page-title-el').textContent = d.pageTitle;
    ids.forEach(id => {{
      const el = document.getElementById(id);
      if (!el) return;
      const key = idToKey[id] || id;
      if (d[key] !== undefined) el.innerHTML = d[key];
    }});
    // Update nav href lang params
    [['nav-dashboard','sat_poi_dashboard.html'],['nav-todo','sat_todo_map.html'],['nav-todo-list','sat_todo_list.html'],
     ['nav-quality','sat_poi_quality_history.html'],['nav-osm-report','sat_osm_ref_report.html'],['nav-trail-report','sat_osm_trail_report.html'],['nav-whatsnew','whats_new.html']].forEach(([id, base]) => {{
      const el = document.getElementById(id);
      if (el && el.closest) {{
        const a = el.closest('a') || el;
        if (a.tagName === 'A') a.href = base + (lang !== 'sv' ? '?lang=' + lang : '');
      }}
    }});
  }}

  window.toggleLang = function() {{
    lang = lang === 'sv' ? 'en' : 'sv';
    const url = new URL(window.location.href);
    if (lang === 'en') url.searchParams.set('lang', 'en');
    else url.searchParams.delete('lang');
    window.history.replaceState({{}}, '', url.toString());
    applyLanguage();
  }};

  applyLanguage();
}})();
</script>
</body>
</html>
"""

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(HTML)
print(f"✅ {OUTPUT} sparad")
