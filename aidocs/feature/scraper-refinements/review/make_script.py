"""Write script.yaml from the deck's speaker notes (the deck is the source of truth).
Cues name targets; each target is the visible text capture.mjs should find on that slide."""
import json, re, html, sys
root, out = sys.argv[1], sys.argv[2]
CUES = {
 "cover": [(0,"title","Scraper refinements,"),(14,"scraper","37bce63 → ffe35d6"),(24,"server","v1.0.1 → v1.1.0-rc14")],
 "use": [(4,"deck","This deck"),(9,"tour","Code tour"),(20,"rehearsal","Rehearsal guide"),(26,"short","15 min"),(32,"long","40 min")],
 "map": [(2,"launch","Launch · apo-mcp-server"),(12,"crawl","Crawl · scrape-website"),(30,"ingest","Ingest · apo-mcp-server")],
 "revisions": [(10,"rc2","rc2–4"),(20,"rc10","rc10"),(24,"rc11","rc11"),(28,"rc12","rc12"),(33,"rc5","rc5–7")],
 "tiers": [(3,"t1","Tier 1"),(8,"t2","Tier 2"),(15,"t3","Tier 3"),(30,"read","What to read"),(45,"ask","Ask the room")],
 "sticky": [(2,"code","self._tier1_blocks_in_a_row += 1"),(22,"why","Why"),(38,"ask","Ask the room")],
 "ratelimit": [(5,"history","Three revisions"),(28,"code","fetch_with_retry"),(46,"result","WordPress sites: up to 45% denied → 0"),(50,"ask","Ask the room:")],
 "excludes": [(8,"media","6fafc93"),(14,"facets","9e963ed"),(20,"bibcite","bec9247"),(28,"r7","4ae59f9"),(40,"ask","Ask the room:")],
 "r7": [(4,"history","How the keep list settled"),(30,"code","# crawl(), sitemap seeding (names shortened)"),(44,"ask","Ask the room:")],
 "sitemap": [(6,"robots","robots.txt"),(12,"tiers","through the tiers"),(20,"lastmod","(loc, lastmod)"),(34,"log","scrape.log, one line per host"),(48,"ask","Ask the room:")],
 "notpages": [(8,"offsite","Off-host redirect."),(26,"media","Media by content type."),(32,"error","Error page."),(46,"ask","Ask the room:")],
 "concurrency": [(6,"slot","async with self.semaphore:"),(16,"flag","--concurrency 3"),(34,"formula","# pages per second, roughly:"),(40,"measured","seas, measured")],
 "sets": [(10,"big","Four largest sites"),(22,"akamai","Akamai Drupal, 44 hosts"),(30,"pantheon","Pantheon, 9 hosts"),(34,"wordpress","WordPress (openresty), 16 hosts"),(42,"rules","Two hard rules"),(56,"ask","Ask the room")],
 "retire": [(8,"code","def _retire_file_fast(record):"),(22,"why","Why every key is sent"),(48,"ask","Ask the room:")],
 "trace": [(5,"s1","crawl()"),(12,"s2","_should_fetch"),(16,"s3","process_url"),(22,"s4","fetch_with_retry"),(34,"s5","_parse_and_extract"),(40,"s6","save_text"),(46,"s7","run()"),(50,"s8","ingest.py --fresh"),(58,"before","Before rc12")],
 "tests": [(4,"rate","test_rate_limit.py"),(30,"counts","80 · 198 · 34"),(46,"gaps","Not covered by tests")],
 "questions": [(4,"q1","Q1"),(14,"q2","Q2"),(20,"q3","Q3"),(28,"q4","Q4"),(36,"q5","Q5")],
 "notbuilt": [(4,"next","Next feature"),(30,"gaps","Known gaps from the refresh")],
 "runit": [(2,"commands","git fetch origin &amp;&amp; git checkout ffe35d6"),(20,"start","Start with"),(26,"then","Then"),(30,"comments","Leave comments")],
}
SAY = {"PR":"P-R","CLI":"C-L-I","vCPU":"V-C-P-U","ECS":"E-C-S","WAF":"waff","TLS":"T-L-S","lastmod":"last mod","rc":"R-C"}
d = json.load(open(f"{root}/deck.json"))
lines = ["# Generated from the deck's speaker notes by make_script.py. Edit the notes, then regenerate.",
         "# targets: name -> visible text on the slide (capture.mjs finds boxes by this text, never by pixels).",
         "# cue times are estimates at 150 words a minute; adjust after voicing.", "frames:"]
for n, sid in enumerate(d["order"], 1):
    s = open(f"{root}/slides/{sid}.html").read()
    note = html.unescape(re.search(r"<aside>(.*?)</aside>", s, re.S).group(1)).strip()
    tag = re.search(r">((?:Core|25 min|40 min)) · Tour \d+<", s)
    lines += [f"  - frame: s{n}-{sid}", f"    track: {json.dumps(tag.group(1) if tag else 'Core')}",
              f"    narration: {json.dumps(note, ensure_ascii=False)}", "    targets:"]
    for _, name, text in CUES[sid]:
        lines.append(f"      {name}: {json.dumps(html.unescape(text), ensure_ascii=False)}")
    lines.append("    cues:")
    for at, name, _ in CUES[sid]:
        lines.append(f"      - {{at: {at}, target: {name}}}")
    words = len(note.split())
    lines.append(f"      - {{at: {round(words / 150 * 60) - 2}, target: none}}")
    if n == len(d["order"]):
        lines.append("    hold: 5")
lines += ["# Respellings for the voice only (pronunciations.yaml in the reference pipeline). Captions keep the real text.",
          "pronunciations:"] + [f"  {k}: {json.dumps(v)}" for k, v in SAY.items()]
open(out, "w").write("\n".join(lines) + "\n")
print("frames:", len(d["order"]))
