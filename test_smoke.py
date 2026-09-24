"""Quick smoke test — run with: uv run python test_smoke.py"""
from pipeline.utils.taxonomy_loader import parse_text_taxonomy, get_leaf_nodes
from pipeline.utils.node_rules import get_rules_for_node, format_rules_for_prompt
from pipeline.utils.html_parser import parse_structured_description, parse_claims_text

print("=" * 60)
print("SMOKE TEST")
print("=" * 60)

# ── 1. Taxonomy loader ────────────────────────────────────────
with open("data/Wissen.txt", encoding="utf-8") as f:
    text = f.read()

nodes = parse_text_taxonomy(text)
leaves = get_leaf_nodes(nodes)
print(f"\n[taxonomy_loader]")
print(f"  Total nodes : {len(nodes)}")
print(f"  Leaf nodes  : {len(leaves)}")
print("  First 8 leaves:")
for n in leaves[:8]:
    print(f"    [{n['level']}] {n['path']}")

# ── 2. Node rules ─────────────────────────────────────────────
print(f"\n[node_rules]")
test_names = ["Tensile Strength", "Melt Flow Index", "Haze", "Novel metallocene structures"]
for name in test_names:
    rules = get_rules_for_node(name)
    prompt_text = format_rules_for_prompt(rules)
    print(f"  {name!r:40s} -> {prompt_text}")

# ── 3. HTML parser ────────────────────────────────────────────
print(f"\n[html_parser]")
sample_html = """
<p>This invention relates to Example 1 preparation of metallocene catalysts.</p>
<table>
  <tr><th>Property</th><th>Value</th></tr>
  <tr><td>Tensile Strength</td><td>35 MPa</td></tr>
  <tr><td>Haze</td><td>2.1 %</td></tr>
</table>
<p>Example 2: The polymerization was conducted at 80°C.</p>
<figure><figcaption>Figure 1: Reactor setup diagram</figcaption></figure>
"""
chunks = parse_structured_description(sample_html, "US_TEST_001")
print(f"  Parsed {len(chunks)} chunks:")
for c in chunks:
    print(f"    [{c['section']:12s}] [{c['source_label']:20s}] priority={c['priority']}  len={len(c['text'])}")

# ── 4. Claims parser ──────────────────────────────────────────
print(f"\n[claims_parser]")
sample_claims = "1. A composition comprising metallocene. 2. The composition of claim 1 wherein density is 0.95."
claim_chunks = parse_claims_text(sample_claims, [], "US_TEST_001")
for c in claim_chunks:
    print(f"    [{c['source_label']}] {c['text'][:80]}")

print("\nOK All smoke tests passed!")
