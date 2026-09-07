#!/usr/bin/env python3
"""Generate the bilingual SAT use-case assessment without network access."""

from collections import Counter
from html import escape
from pathlib import Path

from use_cases_data import BASELINE, CASES, PERSONAS, REFERENCE, REVIEWED_AT

ROOT = Path(__file__).resolve().parent
STATUS = {
    "available": ("Finns idag", "Available today"),
    "partial": ("Delvis stöd", "Partial support"),
    "planned": ("Vision – saknas här", "Vision – not implemented here"),
}
STAGES = {
    "before": ("Före turen", "Before hiking"),
    "during": ("Under turen", "During hiking"),
    "after": ("Efter turen", "After hiking"),
    "manage": ("Förvalta data", "Manage data"),
}
LABELS = {
    "need": ("Behov", "Need"),
    "current": ("Vad finns här idag?", "What exists here today?"),
    "gap": ("Vad saknas?", "What is missing?"),
    "done": ("Acceptanskriterium / nästa verifierbara steg", "Acceptance criterion / next verifiable step"),
    "owner": ("Föreslagna ansvariga och beroenden", "Proposed owners and dependencies"),
}


def bi(sv, en):
    return f'<span lang="sv">{escape(sv)}</span><span lang="en">{escape(en)}</span>'


def validate_cases(cases):
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate use-case IDs")
    covered = set()
    for case in cases:
        if case["status"] not in STATUS or case["stage"] not in STAGES:
            raise ValueError(f"Invalid status/stage: {case['id']}")
        if case["priority"] not in {"P0", "P1", "P2"}:
            raise ValueError(f"Invalid priority: {case['id']}")
        for field in ("title", *LABELS):
            if len(case[field]) != 2 or not all(case[field]):
                raise ValueError(f"Missing translation: {case['id']}/{field}")
        if not case["refs"] or not case["tools"] or not case["evidence"]:
            raise ValueError(f"Missing traceability: {case['id']}")
        covered.update(case["refs"])
        for path in (*case["tools"], *case["evidence"]):
            if not (ROOT / path).is_file():
                raise ValueError(f"Missing local source/tool: {path}")
    if covered != set(range(1, len(PERSONAS) + 1)):
        raise ValueError("Every original persona must be mapped, with no unknown references")


def render_case(case):
    fields = "".join(
        f"<dt>{bi(*label)}</dt><dd>{bi(*case[field])}</dd>"
        for field, label in LABELS.items()
    )
    refs = ", ".join(f'<a href="{REFERENCE}#UC-{ref}">UC-{ref}</a>' for ref in case["refs"])
    tools = " · ".join(f'<a data-local href="{path}">{path}</a>' for path in case["tools"])
    evidence = " · ".join(
        f'<a href="https://github.com/salgo60/sat-sync/blob/{BASELINE}/{path}">{path}</a>'
        for path in case["evidence"]
    )
    return f"""
    <article class="case" id="{case['id']}" data-stage="{case['stage']}"
             data-status="{case['status']}" data-priority="{case['priority']}">
      <div class="badges"><span class="badge">{case['priority']}</span>
        <span class="badge {case['status']}">{bi(*STATUS[case['status']])}</span>
        <span class="badge">{bi(*STAGES[case['stage']])}</span></div>
      <h3><a href="#{case['id']}">{case['id']}</a> · {bi(*case['title'])}</h3>
      <dl>{fields}</dl>
      <p><strong>{bi("Öppna befintliga verktyg", "Open existing tools")}:</strong> {tools}</p>
      <p><strong>{bi("Referensens målgrupper", "Reference personas")}:</strong> {refs}</p>
      <details><summary>{bi("Kodbelägg för bedömningen", "Code evidence for this assessment")}</summary>
        <p>{evidence}</p></details>
    </article>"""


def render_comparison(cases):
    rows = []
    for ref, title in enumerate(PERSONAS, 1):
        related = [case for case in cases if ref in case["refs"]]
        links = "<br>".join(
            f'<a href="#{case["id"]}">{case["id"]} · {bi(*case["title"])}</a>'
            f' — {bi(*STATUS[case["status"]])}'
            for case in related
        )
        rows.append(f'<tr id="UC-{ref}"><th scope="row"><a href="{REFERENCE}#UC-{ref}">'
                    f'UC-{ref}</a> {escape(title)}</th><td>{links}</td></tr>')
    return "\n".join(rows)


def render_html(cases=CASES):
    validate_cases(cases)
    counts = Counter(case["status"] for case in cases)
    stats = "".join(
        f'<div class="stat"><strong>{counts[status]}</strong>{bi(*label)}</div>'
        for status, label in STATUS.items()
    )
    options = lambda values: "".join(
        f'<option value="{key}" data-sv="{escape(label[0], quote=True)}" '
        f'data-en="{escape(label[1], quote=True)}">{escape(label[0])}</option>'
        for key, label in values.items()
    )
    content = f"""
<a class="skip" href="#main">{bi("Hoppa till innehållet", "Skip to content")}</a>
<header id="top">
  <h1>{bi("Användningsfall för Stockholm Archipelago Trail", "Use cases for hiking Stockholm Archipelago Trail")}</h1>
  <p>{bi("Från målgrupper och flyers till konkreta behov, belägg och nästa steg.",
         "From personas and flyers to concrete needs, evidence and next steps.")}</p>
  <nav aria-label="Navigation">
    <a data-local href="sat_poi_dashboard.html">Dashboard</a>
    <a data-local href="sat_about.html">{bi("Om verktygen", "About the tools")}</a>
    <a href="#assessment">{bi("Kritisk bedömning", "Critical assessment")}</a>
    <a href="#cases">{bi("Användningsfall", "Use cases")}</a>
    <a href="#comparison">{bi("Jämför 43 målgrupper", "Compare 43 personas")}</a>
    <button id="language" type="button" hidden>English</button>
  </nav>
</header>
<main id="main">
  <section class="notice">
    <h2>{bi("Inventering – inte ett löfte om livefunktioner", "An assessment – not a promise of live features")}</h2>
    <p>{bi("Den här sidan bedömer sat-sync, inte hela SAT-ekosystemet. Befintliga kartor, rapporter och länkar kan hjälpa en vandrare men är främst verktyg för datavård. Flyernas livebåtar, lediga rum, fungerande toaletter och prenumerationer är inte implementerade tjänster här.",
           "This page assesses sat-sync, not the entire SAT ecosystem. Existing maps, reports and links can help a hiker but are primarily data-maintenance tools. Live boats, room availability, working toilets and subscriptions in the flyers are not implemented services here.")}</p>
    <p>{bi("Bedömd", "Assessed")}: <time datetime="{REVIEWED_AT}">{REVIEWED_AT}</time>.
      {bi("Kodbas", "Code baseline")}: <a href="https://github.com/salgo60/sat-sync/tree/{BASELINE}">{BASELINE}</a>.
      {bi("Prioriteringar och ansvariga är förslag, inte beslut eller partneråtaganden.",
          "Priorities and owners are proposals, not decisions or partner commitments.")}</p>
  </section>
  <section aria-labelledby="infographic-title">
    <h2 id="infographic-title">{bi("Användningsfallen i bild", "Use cases at a glance")}</h2>
    <figure class="use-cases-infographic">
      <a href="assets/sat-use-cases-infographic.jpg" target="_blank" rel="noopener">
        <img src="assets/sat-use-cases-infographic.jpg"
             alt="Stockholm Archipelago Trail: 16 användningsfall / 16 use cases"
             width="1024" height="1536" loading="lazy" aria-describedby="infographic-caption">
      </a>
      <figcaption id="infographic-caption">
        <p>{bi("Konceptöversikt över resan före, under och efter vandringen samt aktörer och öppna data. Bildens numrering, prioriteringar och exempel skiljer sig från sidans SAT-ID:n. Korten nedan är den aktuella bedömningen; bilden är inte en interaktiv karta eller ett löfte om tillgängliga tjänster.",
               "Concept overview of the journey before, during and after hiking, stakeholders and open data. The image's numbering, priorities and examples differ from this page's SAT IDs. The cards below are the current assessment; the image is not an interactive map or a promise of available services.")}</p>
        <p>{bi("Klicka på bilden för full storlek. Texten i bilden är på svenska.",
               "Click the image to open it full size. The text in the image is in Swedish.")}</p>
      </figcaption>
    </figure>
  </section>
  <section id="assessment">
    <h2>{bi("Kritik: vad saknas i helheten?", "Critique: what is missing overall?")}</h2>
    <div class="assessment-grid">
      <div><h3>{bi("1. Målgrupp är inte ett användningsfall", "1. A persona is not a use case")}</h3>
      <p>{bi("Referensens 43 målgrupper är ett bra breddtest, men blandar vandrare, företag, myndigheter och utvecklare. Här grupperas överlappande behov i 16 uppgifter med ett tydligt resultat. Alla UC-ID:n behålls i jämförelsen.",
             "The reference's 43 personas provide a useful breadth check, but mix hikers, businesses, agencies and developers. Here overlapping needs become 16 tasks with explicit outcomes. All original UC IDs remain in the comparison.")}</p></div>
      <div><h3>{bi("2. Hela resan, inte bara kartpunkter", "2. The whole journey, not just map points")}</h3>
      <p>{bi("Återresa, sista båt, gångtidsmarginal, reservplan och säsong måste hänga ihop. Saknad information får inte tolkas som att en plats är säker, öppen eller tillgänglig.",
             "Return travel, the last boat, walking-time margins, fallback plans and seasons must connect. Missing information must not be interpreted as safe, open or accessible.")}</p></div>
      <div><h3>{bi("3. Färsk data behöver ansvar och giltighet", "3. Fresh data needs ownership and validity")}</h3>
      <p>{bi("Tidpunkten då en sida byggdes är inte tidpunkten då en toalett kontrollerades. Varje status behöver observationstid, giltighet, källa, ansvarig och ett sätt att hantera konflikter. Uppkopplade ID:n gör inte källorna automatiskt överens.",
             "A page build time is not the time a toilet was inspected. Each status needs observation time, validity, source, ownership and conflict handling. Linked IDs do not automatically reconcile sources.")}</p></div>
      <div><h3>{bi("4. Inkludering måste kunna provas", "4. Inclusion must be testable")}</h3>
      <p>{bi("Tillgänglighet gäller hela reskedjan, språkstödet måste omfatta kritiska texter och turen behöver fungera utan mobilnät. Börja med användartester, inte etiketter som familjevänlig eller seniorvänlig.",
             "Accessibility covers the whole travel chain, languages must include critical text, and a trip needs to work without mobile coverage. Start with user testing, not labels such as family-friendly or senior-friendly.")}</p></div>
      <div><h3>{bi("5. Bidrag måste tas om hand", "5. Contributions need a response process")}</h3>
      <p>{bi("Felrapportering utan mottagare, kvittens och åtgärdsstatus är inte ett underhållsflöde. Delade turer och notiser kräver dessutom licenser, moderering, integritet, samtycke och radering.",
             "Reporting without a recipient, acknowledgement and resolution status is not a maintenance workflow. Shared trips and notifications also require licensing, moderation, privacy, consent and deletion.")}</p></div>
      <div><h3>{bi("6. Prioritera nytta före fler funktioner", "6. Prioritize outcomes over more features")}</h3>
      <p>{bi("Denna kodbaserade bedömning behöver kompletteras med intervjuer och mätning av hur väl verkliga vandrare löser uppgifterna. Validera först en dagstur med hemresa och verifierad service. Bygg därefter bokning/notiser och sist ett större communityflöde.",
             "This code-based assessment needs interviews and measurement of real hikers completing tasks. First validate a day trip with return transport and verified services. Then add booking/notifications, and only later a larger community workflow.")}</p></div>
    </div>
  </section>
  <section id="roadmap">
    <h2>{bi("Föreslagen ordning", "Proposed sequence")}</h2>
    <p><strong>P0</strong> — {bi("Grundläggande tillit och turens genomförbarhet: återresa, regler, service, tillgänglighet, offline/reservplan, felkedja och datakontrakt.",
                                               "Foundational trust and trip feasibility: return travel, rules, services, accessibility, offline/fallback, issue resolution and data contracts.")}</p>
    <p><strong>P1</strong> — {bi("Språk, bokningslänkar/integrationer, gruppplanering och ett avgränsat notisflöde efter att källansvar är klart.",
                                               "Languages, booking links/integrations, group planning and a scoped notification flow once source ownership is agreed.")}</p>
    <p><strong>P2</strong> — {bi("Kuraterade upplevelser, delade turer och samhällsanalys med tydligt avgränsade pilotprojekt.",
                                               "Curated experiences, shared hikes and public-value analysis through clearly scoped pilots.")}</p>
    <p>{bi("Pilotförslag: en ö, en dagstur, en transportkälla och en serviceförvaltare. Mät genomförd planering, andel uppgifter med giltig källa, synliga okända värden och tid till kvitterad felrapport. Sätt målnivåer tillsammans med användare innan pilotstart.",
           "Pilot proposal: one island, one day hike, one transport source and one service manager. Measure planning completion, records with valid sources, visible unknowns and time to acknowledge reports. Agree targets with users before the pilot.")}</p>
  </section>
  <section id="cases">
    <h2>{bi("16 konkreta användningsfall", "16 actionable use cases")}</h2>
    <div class="stats">{stats}</div>
    <p>{bi("Finns idag gäller endast den beskrivna uppgiften. Delvis stöd betyder byggstenar, inte ett färdigt flöde. Vision betyder att tjänsten inte är implementerad i sat-sync. Inget av detta certifierar ledens säkerhet eller datans fullständighet.",
           "Available today applies only to the described task. Partial means building blocks, not an end-to-end workflow. Vision means the service is not implemented in sat-sync. None certifies trail safety or data completeness.")}</p>
    <form id="filters" hidden role="search">
      <label>{bi("Sök behov, målgrupp eller UC-ID", "Search needs, personas or UC IDs")}
        <input id="search" type="search" name="q"></label>
      <label>{bi("När?", "When?")}<select id="stage" name="stage">
        <option value="" data-sv="Alla steg" data-en="All stages">Alla steg</option>{options(STAGES)}</select></label>
      <label>Status<select id="status" name="status">
        <option value="" data-sv="Alla statusar" data-en="All statuses">Alla statusar</option>{options(STATUS)}</select></label>
      <label>{bi("Prioritet", "Priority")}<select id="priority" name="priority">
        <option value="" data-sv="Alla prioriteter" data-en="All priorities">Alla prioriteter</option>
        <option>P0</option><option>P1</option><option>P2</option></select></label>
      <button type="reset">{bi("Rensa filter", "Clear filters")}</button>
    </form>
    <p id="result-count" role="status" aria-live="polite"></p>
    <p id="empty" hidden>{bi("Inga användningsfall matchar. Rensa eller ändra filtren.",
                            "No matching use cases. Clear or change the filters.")}</p>
    <div class="case-grid">{"".join(render_case(case) for case in cases)}</div>
  </section>
  <section id="comparison">
    <h2>{bi("Jämförelse med referensens 43 målgrupper", "Comparison with the reference's 43 personas")}</h2>
    <p><a href="{REFERENCE}#UC-1">{bi("Öppna ursprunglig User Cases-dashboard", "Open the original User Cases dashboard")}</a>
      · {bi("läst", "accessed")} {REVIEWED_AT}.</p>
    <p>{bi("Originalrubriker och UC-ID:n behålls. Länkarna nedan visar relaterade uppgifter, inte att målgruppens alla behov är uppfyllda. Referensens historiska ”Idag”-påståenden återges inte som verifierade fakta; vår bedömning gäller kodbasen ovan. Tabellen påverkas inte av kortfiltren.",
           "Original titles and UC IDs are retained. Links below identify related tasks, not full fulfillment of a persona's needs. Historical 'Today' claims in the reference are not repeated as verified facts; this assessment concerns the code baseline above. Card filters do not filter this table.")}</p>
    <div class="table-scroll" tabindex="0" role="region" aria-label="UC comparison">
      <table><caption>{bi("Alla ursprungliga målgrupper och deras relaterade SAT-uppgifter", "All original personas and their related SAT tasks")}</caption>
      <thead><tr><th scope="col">{bi("Referens: målgrupp", "Reference: persona")}</th>
      <th scope="col">{bi("Motsvarande uppgifter och stöd här", "Related tasks and support here")}</th></tr></thead>
      <tbody>{render_comparison(cases)}</tbody></table>
    </div>
  </section>
  <section>
    <h2>{bi("Källor, avgränsning och återkoppling", "Sources, scope and feedback")}</h2>
    <p>{bi("Bedömningen bygger på generatorerna som länkas från varje kort, README och referensens målgruppslista. Saknade tjänster betyder inte att andra SAT-projekt eller externa operatörer saknar dem. Detta är en redaktionell gap-analys, inte användarforskning, ett säkerhetsintyg eller en aktuell driftstatus.",
           "The assessment uses the generators linked from each card, the README and the reference persona list. Missing services here do not imply their absence in other SAT projects or external operators. This is an editorial gap analysis, not user research, a safety certification or live operational status.")}</p>
    <p><a href="https://github.com/salgo60/Stockholm_Archipelago_Trail/issues/151">Share Your Hike — salgo60/Stockholm_Archipelago_Trail#151</a>
      · <a href="https://github.com/salgo60/sat-sync/issues/new">{bi("Föreslå förbättring med SAT-/UC-ID", "Suggest an improvement with a SAT/UC ID")}</a>
      · <a href="use_cases_data.py">{bi("Bedömningsdata", "Assessment data")}</a></p>
  </section>
</main>
<footer><a href="#top">{bi("Till toppen", "Back to top")}</a> ·
  <a href="https://github.com/salgo60/sat-sync">salgo60/sat-sync</a></footer>
"""
    return TEMPLATE.replace("__CONTENT__", content)


TEMPLATE = """<!DOCTYPE html>
<html lang="sv">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Användningsfall – Stockholm Archipelago Trail</title>
  <style>
    * { box-sizing:border-box; }
    body { margin:0; font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:#1e293b; background:#f1f5f9; }
    html[lang="sv"] [lang="en"], html[lang="en"] [lang="sv"], [hidden] { display:none !important; }
    header { padding:28px max(20px,calc((100% - 1160px)/2)); background:#1d367b; color:white; }
    header h1 { line-height:1.2; font-size:clamp(1.6rem,4vw,2.4rem); }
    nav { display:flex; gap:14px; align-items:center; flex-wrap:wrap; }
    header a { color:#fff; }
    main { max-width:1200px; padding:20px; margin:auto; }
    section { background:white; border-radius:12px; padding:24px; margin-bottom:24px; }
    h2 { margin-top:0; color:#2546a8; }
    h3 { line-height:1.4; }
    a { color:#1d4ed8; text-underline-offset:3px; overflow-wrap:anywhere; }
    a:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible, summary:focus-visible, .table-scroll:focus-visible { outline:3px solid #c2410c; outline-offset:3px; }
    .skip { position:absolute; left:12px; top:-100px; background:white; padding:10px; z-index:10; }
    .skip:focus { top:10px; }
    .notice { border-left:5px solid #d97706; background:#fffbeb; }
    .use-cases-infographic { margin:0; }
    .use-cases-infographic img { display:block; width:100%; max-width:800px; height:auto; margin:0 auto; border-radius:8px; }
    .use-cases-infographic figcaption { color:#475569; font-size:.95rem; }
    .assessment-grid, .case-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:20px; }
    .stats { display:flex; gap:14px; flex-wrap:wrap; }
    .stat { background:#f1f5f9; padding:12px 20px; border-radius:8px; }
    .stat strong { display:block; font-size:1.8rem; color:#1d367b; }
    #filters { display:flex; flex-wrap:wrap; gap:12px; align-items:end; padding:16px; background:#f8fafc; }
    label { display:block; }
    input, select { display:block; width:100%; }
    input, select, button { font:inherit; border:1px solid #94a3b8; border-radius:6px; padding:8px; background:#fff; color:#1e293b; }
    button { cursor:pointer; min-height:44px; }
    .case { border:1px solid #cbd5e1; border-radius:10px; padding:20px; min-width:0; }
    .case h3 { margin:14px 0; }
    .badges { display:flex; gap:6px; flex-wrap:wrap; }
    .badge { background:#e2e8f0; border-radius:6px; padding:3px 9px; font-size:.8rem; }
    .available { background:#dcfce7; color:#14532d; }
    .partial { background:#fef3c7; color:#78350f; }
    .planned { background:#ede9fe; color:#4c1d95; }
    dt { font-weight:700; margin-top:12px; }
    dd { margin:3px 0 0; }
    .case p, details { font-size:.9rem; }
    summary { cursor:pointer; }
    .table-scroll { overflow-x:auto; }
    table { width:100%; border-collapse:collapse; text-align:left; }
    caption { text-align:left; margin:8px 0; }
    th, td { padding:12px; border-bottom:1px solid #cbd5e1; vertical-align:top; }
    thead { background:#e2e8f0; }
    tbody th { width:35%; }
    :target { scroll-margin-top:16px; outline:3px solid #2563eb; }
    footer { text-align:center; padding:24px; }
    @media(max-width:700px) {
      main { padding:12px; } section { padding:16px; }
      .assessment-grid, .case-grid { grid-template-columns:1fr; }
      #filters label { width:100%; } th, td { padding:8px; }
    }
  </style>
</head>
<body>
__CONTENT__
<script>
(() => {
  const cards = [...document.querySelectorAll('.case')];
  const form = document.getElementById('filters');
  const fields = ['search', 'stage', 'status', 'priority'];
  const keys = ['q', 'stage', 'status', 'priority'];
  const inputs = fields.map(id => document.getElementById(id));
  const language = document.getElementById('language');
  let lang = 'sv';
  // Include original persona titles in search without duplicating them on each card.
  const personas = [...document.querySelectorAll('#comparison tbody tr')];
  const searchText = new Map(cards.map(card => [card, (
    card.textContent + ' ' + personas.filter(row =>
      row.querySelector(`a[href="#${card.id}"]`)).map(row => row.querySelector('th').textContent).join(' ')
  ).toLocaleLowerCase()]));

  function setLanguage() {
    document.documentElement.lang = lang;
    document.title = lang === 'sv' ? 'Användningsfall – Stockholm Archipelago Trail' : 'Use cases – Stockholm Archipelago Trail';
    language.textContent = lang === 'sv' ? 'English' : 'Svenska';
    document.querySelectorAll('option[data-sv]').forEach(option => {
      option.textContent = option.dataset[lang];
    });
    document.querySelectorAll('a[data-local]').forEach(link => {
      const url = new URL(link.href);
      url.searchParams.set('lang', lang);
      link.href = url.toString();
    });
  }
  function filter() {
    const [query, stage, status, priority] = inputs.map(el => el.value.trim());
    const terms = query.toLocaleLowerCase().split(/\\s+/).filter(Boolean);
    let count = 0;
    cards.forEach(card => {
      card.hidden = !(terms.every(term => searchText.get(card).includes(term))
        && (!stage || card.dataset.stage === stage)
        && (!status || card.dataset.status === status)
        && (!priority || card.dataset.priority === priority));
      if (!card.hidden) count++;
    });
    document.getElementById('result-count').textContent = lang === 'sv'
      ? `${count} av ${cards.length} användningsfall` : `${count} of ${cards.length} use cases`;
    document.getElementById('empty').hidden = count !== 0;
  }
  function saveURL() {
    const url = new URL(location.href);
    url.searchParams.set('lang', lang);
    inputs.forEach((el, i) => {
      if (el.value) url.searchParams.set(keys[i], el.value);
      else url.searchParams.delete(keys[i]);
    });
    history.replaceState({}, '', url);
  }
  function revealHash() {
    const target = document.getElementById(location.hash.slice(1));
    if (target && target.classList.contains('case') && target.hidden) {
      inputs.forEach(el => { el.value = ''; });
      filter();
      saveURL();
    }
    if (target) target.scrollIntoView({block:'start'});
  }
  function restore() {
    const params = new URLSearchParams(location.search);
    lang = params.get('lang') === 'en' ? 'en' : 'sv';
    inputs.forEach((el, i) => { el.value = params.get(keys[i]) || ''; });
    setLanguage();
    filter();
    revealHash();
  }
  form.hidden = false;
  language.hidden = false;
  form.addEventListener('submit', event => event.preventDefault());
  form.addEventListener('input', () => { filter(); saveURL(); });
  form.addEventListener('reset', event => {
    event.preventDefault();
    inputs.forEach(el => { el.value = ''; });
    filter(); saveURL();
  });
  language.addEventListener('click', () => {
    lang = lang === 'sv' ? 'en' : 'sv';
    setLanguage(); filter(); saveURL();
  });
  document.querySelectorAll('a[href^="#SAT-"]').forEach(link => {
    link.addEventListener('click', () => {
      const target = document.getElementById(link.hash.slice(1));
      if (target.hidden) {
        inputs.forEach(el => { el.value = ''; });
        filter(); saveURL();
      }
    });
  });
  window.addEventListener('hashchange', revealHash);
  window.addEventListener('popstate', restore);
  restore();
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    output = ROOT / "sat_use_cases.html"
    output.write_text(render_html(), encoding="utf-8")
    print(f"Generated {output.name}: {len(CASES)} use cases, {len(PERSONAS)} reference personas")
