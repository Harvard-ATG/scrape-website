"""Chunking simulation for the served .md and our extraction of the same page. Needs tiktoken (stdlib otherwise).
Assumption: ingest uploads the file body to an OpenAI vector store with the default 'auto' chunking
(max 800 tokens per chunk, 400 overlap), which `apo-mcp-server/ingest.py` does not override. Tokenizer: o200k_base.
  python evidence_pack_chunks.py samples/typed19 samples/typed19_chunks.json"""
import json, re, sys
from pathlib import Path
import tiktoken

enc = tiktoken.get_encoding("o200k_base")
MAX, OVERLAP = 800, 400
root = Path(sys.argv[1])


def chunks(tokens):
    step = MAX - OVERLAP
    out, i = [], 0
    while True:
        out.append(tokens[i:i + MAX])
        if i + MAX >= len(tokens):
            break
        i += step
    return out


def words(t):
    return set(w for w in re.findall(r"[a-z0-9]+", t.lower()) if len(w) >= 3)


def analyse(text, other, title, date):
    toks = enc.encode(text)
    ws = sum(1 for t in toks if not enc.decode([t]).strip())
    link_img = len(enc.encode("".join(re.findall(r"\]\([^)]*\)", text))))
    cs = chunks(toks) if toks else []
    ow = words(other)
    texts = [enc.decode(c) for c in cs]
    unique = 0
    for ct in texts:
        w = words(ct)
        if w and len(w & ow) / len(w) < 0.5:
            unique += 1
    both = None
    if date:
        both = any(date in ct and title.lower() in ct.lower() for ct in texts) if title else None
    return {"tokens": len(toks), "whitespace_tokens": ws, "whitespace_share": round(ws / len(toks), 3) if toks else None,
            "link_and_image_target_tokens": link_img, "chunks": len(cs), "chunks_mostly_not_in_other": unique,
            "title_and_date_in_one_chunk": both}


rows = []
for d in sorted(root.glob("*/*")):
    m = json.load(open(d / "meta.json"))
    if not (d / "ours.md").exists():
        continue
    md = (d / "page.md").read_text(errors="replace") if m["page.md"].get("status") == 200 else ""
    ours = re.sub(r"\A---.*?---\n", "", (d / "ours.md").read_text(errors="replace"), flags=re.S).strip()
    title = (re.search(r"^\s*#+\s*(.+?)\s*$", md, re.M) or re.search(r"^#+\s*(.+?)\s*$", ours, re.M) or [None, ""])[1]
    dm = re.search(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, (?:19|20)\d{2}\b", md)
    date = dm.group(0) if dm else None
    rows.append({"dir": str(d.relative_to(root)), "type": m.get("type", "sample20"), "title": title[:80], "date_in_md": date,
                 "served_md": analyse(md, ours, title, date) if md else None,
                 "ours": analyse(ours, md, title, date)})
json.dump(rows, open(sys.argv[2], "w"), indent=1)
print(len(rows))
