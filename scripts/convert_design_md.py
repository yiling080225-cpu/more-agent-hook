#!/usr/bin/env python3
"""Convert DESIGN.md files from awesome-design-md into compact YAML token files.

Usage: python scripts/convert_design_md.py <clone_path> <output_dir>
"""

import sys, os, yaml, json
from pathlib import Path

# Brand categorization for smart routing
# key: brand directory name -> {tags, keywords, use_cases}
BRAND_META = {
    # AI / Tech
    "claude":       {"tags": ["ai", "warm", "editorial", "humanist"],          "use_cases": ["ai-product", "docs", "landing"],       "industry": "ai"},
    "cursor":       {"tags": ["ai", "dark", "code-editor", "developer"],        "use_cases": ["ide", "developer-tool", "docs"],         "industry": "ai"},
    "opencode.ai":  {"tags": ["ai", "minimal", "code", "open-source"],          "use_cases": ["developer-tool", "docs", "landing"],    "industry": "ai"},
    "x.ai":         {"tags": ["ai", "dark", "futuristic", "bold"],              "use_cases": ["ai-product", "landing"],                 "industry": "ai"},
    "mistral.ai":   {"tags": ["ai", "european", "minimal", "tech"],             "use_cases": ["ai-product", "docs", "landing"],        "industry": "ai"},
    "together.ai":  {"tags": ["ai", "dark", "developer", "infrastructure"],     "use_cases": ["developer-tool", "docs"],                "industry": "ai"},
    "cohere":       {"tags": ["ai", "enterprise", "clean", "professional"],     "use_cases": ["ai-product", "enterprise", "docs"],     "industry": "ai"},
    "elevenlabs":   {"tags": ["ai", "audio", "creative", "dark"],               "use_cases": ["ai-product", "creative", "landing"],    "industry": "ai"},
    "ollama":       {"tags": ["ai", "open-source", "minimal", "developer"],     "use_cases": ["developer-tool", "docs"],                "industry": "ai"},
    "minimax":      {"tags": ["ai", "video", "creative", "tech"],               "use_cases": ["ai-product", "creative", "landing"],    "industry": "ai"},

    # SaaS / Developer
    "vercel":       {"tags": ["saas", "dark", "developer", "geometric"],        "use_cases": ["developer-tool", "dashboard", "landing"], "industry": "saas"},
    "stripe":       {"tags": ["saas", "fintech", "gradient", "editorial"],      "use_cases": ["fintech", "dashboard", "pricing"],        "industry": "fintech"},
    "linear.app":   {"tags": ["saas", "dark", "minimal", "keyboard-driven"],    "use_cases": ["dashboard", "app", "developer-tool"],     "industry": "saas"},
    "figma":        {"tags": ["saas", "design", "creative", "collaborative"],   "use_cases": ["design-tool", "dashboard", "landing"],    "industry": "saas"},
    "slack":        {"tags": ["saas", "colorful", "collaborative", "chat"],     "use_cases": ["app", "dashboard", "messaging"],          "industry": "saas"},
    "shopify":      {"tags": ["saas", "ecommerce", "green", "merchant"],        "use_cases": ["ecommerce", "dashboard", "landing"],      "industry": "ecommerce"},
    "notion":       {"tags": ["saas", "minimal", "productivity", "clean"],      "use_cases": ["docs", "app", "landing"],                 "industry": "saas"},
    "sentry":       {"tags": ["saas", "developer", "purple", "monitoring"],     "use_cases": ["developer-tool", "dashboard"],            "industry": "saas"},
    "posthog":      {"tags": ["saas", "analytics", "developer", "data"],        "use_cases": ["dashboard", "analytics", "developer-tool"], "industry": "saas"},
    "supabase":     {"tags": ["saas", "database", "green", "developer"],        "use_cases": ["developer-tool", "dashboard", "docs"],    "industry": "saas"},
    "raycast":      {"tags": ["saas", "mac", "developer", "productivity"],      "use_cases": ["developer-tool", "app"],                  "industry": "saas"},
    "resend":       {"tags": ["saas", "email", "developer", "minimal"],         "use_cases": ["developer-tool", "docs", "landing"],      "industry": "saas"},
    "replicate":    {"tags": ["saas", "ai", "developer", "api"],                "use_cases": ["developer-tool", "docs"],                 "industry": "saas"},
    "lovable":      {"tags": ["saas", "ai", "creative", "builder"],             "use_cases": ["ai-product", "landing", "creative"],     "industry": "saas"},
    "cal":          {"tags": ["saas", "scheduling", "minimal", "calendar"],     "use_cases": ["app", "landing"],                         "industry": "saas"},
    "zapier":       {"tags": ["saas", "automation", "orange", "workflow"],      "use_cases": ["app", "landing"],                         "industry": "saas"},
    "webflow":      {"tags": ["saas", "design", "nocode", "creative"],          "use_cases": ["design-tool", "landing"],                 "industry": "saas"},
    "intercom":     {"tags": ["saas", "support", "green", "messaging"],         "use_cases": ["app", "landing"],                         "industry": "saas"},
    "sanity":       {"tags": ["saas", "cms", "developer", "content"],           "use_cases": ["developer-tool", "docs"],                 "industry": "saas"},

    # Consumer / Brand
    "apple":        {"tags": ["consumer", "minimal", "photography", "premium"],  "use_cases": ["landing", "product-page", "creative"],  "industry": "consumer-electronics"},
    "nike":         {"tags": ["consumer", "bold", "athletic", "photography"],    "use_cases": ["ecommerce", "landing", "brand"],         "industry": "sportswear"},
    "tesla":        {"tags": ["consumer", "dark", "futuristic", "automotive"],   "use_cases": ["landing", "product-page"],               "industry": "automotive"},
    "spotify":      {"tags": ["consumer", "dark", "music", "vibrant"],           "use_cases": ["app", "landing", "creative"],            "industry": "music"},
    "starbucks":    {"tags": ["consumer", "green", "warm", "coffee"],            "use_cases": ["ecommerce", "brand", "landing"],         "industry": "food-beverage"},
    "playstation":  {"tags": ["consumer", "dark", "gaming", "immersive"],        "use_cases": ["landing", "product-page", "gaming"],     "industry": "gaming"},
    "airbnb":       {"tags": ["consumer", "warm", "photography", "travel"],      "use_cases": ["landing", "app", "ecommerce"],           "industry": "travel"},
    "uber":         {"tags": ["consumer", "dark", "mobility", "minimal"],        "use_cases": ["app", "landing"],                        "industry": "mobility"},
    "theverge":     {"tags": ["media", "editorial", "bold", "news"],             "use_cases": ["blog", "news", "content"],               "industry": "media"},
    "wired":        {"tags": ["media", "editorial", "magazine", "bold"],         "use_cases": ["blog", "news", "content"],               "industry": "media"},
    "pinterest":    {"tags": ["consumer", "visual", "masonry", "creative"],      "use_cases": ["app", "creative", "ecommerce"],          "industry": "social-media"},

    # Automotive
    "bmw":          {"tags": ["automotive", "premium", "dark", "precision"],     "use_cases": ["landing", "product-page", "brand"],      "industry": "automotive"},
    "bmw-m":        {"tags": ["automotive", "sport", "dark", "aggressive"],      "use_cases": ["landing", "product-page", "brand"],      "industry": "automotive"},
    "bugatti":      {"tags": ["automotive", "luxury", "dark", "exclusive"],      "use_cases": ["landing", "product-page", "brand"],      "industry": "automotive"},
    "ferrari":      {"tags": ["automotive", "luxury", "red", "racing"],          "use_cases": ["landing", "product-page", "brand"],      "industry": "automotive"},
    "lamborghini":  {"tags": ["automotive", "luxury", "yellow", "aggressive"],   "use_cases": ["landing", "product-page", "brand"],      "industry": "automotive"},
    "renault":      {"tags": ["automotive", "european", "clean", "modern"],      "use_cases": ["landing", "product-page", "brand"],      "industry": "automotive"},

    # Finance / Crypto
    "coinbase":     {"tags": ["fintech", "crypto", "blue", "trust"],              "use_cases": ["fintech", "app", "dashboard"],          "industry": "fintech"},
    "kraken":       {"tags": ["fintech", "crypto", "purple", "dark"],             "use_cases": ["fintech", "dashboard", "app"],          "industry": "fintech"},
    "revolut":      {"tags": ["fintech", "banking", "dark", "app"],               "use_cases": ["fintech", "app", "dashboard"],          "industry": "fintech"},
    "wise":         {"tags": ["fintech", "green", "minimal", "transfer"],         "use_cases": ["fintech", "app", "landing"],            "industry": "fintech"},
    "mastercard":   {"tags": ["fintech", "corporate", "orange", "payment"],       "use_cases": ["fintech", "brand", "landing"],          "industry": "fintech"},

    # Enterprise / Corporate
    "ibm":          {"tags": ["enterprise", "blue", "corporate", "technical"],    "use_cases": ["enterprise", "docs", "dashboard"],       "industry": "enterprise"},
    "hashicorp":    {"tags": ["enterprise", "infrastructure", "purple", "tech"],  "use_cases": ["developer-tool", "docs", "enterprise"],  "industry": "enterprise"},
    "mongodb":      {"tags": ["enterprise", "database", "green", "developer"],    "use_cases": ["developer-tool", "docs", "landing"],     "industry": "enterprise"},
    "nvidia":       {"tags": ["enterprise", "green", "gpu", "ai"],                "use_cases": ["enterprise", "landing", "developer-tool"], "industry": "enterprise"},
    "meta":         {"tags": ["enterprise", "blue", "social", "corporate"],       "use_cases": ["enterprise", "brand", "landing"],        "industry": "enterprise"},

    # Design / Creative
    "framer":       {"tags": ["design", "creative", "dark", "nocode"],           "use_cases": ["design-tool", "creative", "landing"],    "industry": "design"},
    "clay":         {"tags": ["design", "3d", "creative", "dark"],               "use_cases": ["creative", "brand", "landing"],          "industry": "design"},
    "miro":         {"tags": ["design", "whiteboard", "collaborative", "colorful"], "use_cases": ["design-tool", "app", "dashboard"],     "industry": "design"},
    "runwayml":     {"tags": ["ai", "video", "creative", "dark"],                "use_cases": ["ai-product", "creative", "landing"],    "industry": "ai"},

    # Crypto / Web3
    "binance":      {"tags": ["fintech", "crypto", "yellow", "exchange"],        "use_cases": ["fintech", "dashboard", "app"],          "industry": "fintech"},

    # Others
    "airtable":     {"tags": ["saas", "database", "colorful", "spreadsheet"],    "use_cases": ["dashboard", "app", "landing"],          "industry": "saas"},
    "clickhouse":   {"tags": ["saas", "database", "analytics", "fast"],          "use_cases": ["developer-tool", "dashboard", "docs"],   "industry": "saas"},
    "composio":     {"tags": ["saas", "ai", "integration", "developer"],         "use_cases": ["developer-tool", "docs"],                "industry": "saas"},
    "expo":         {"tags": ["saas", "mobile", "developer", "react-native"],    "use_cases": ["developer-tool", "docs", "landing"],     "industry": "saas"},
    "mintlify":     {"tags": ["saas", "docs", "developer", "clean"],             "use_cases": ["docs", "developer-tool"],                "industry": "saas"},
    "spacex":       {"tags": ["aerospace", "dark", "futuristic", "bold"],        "use_cases": ["landing", "brand", "product-page"],      "industry": "aerospace"},
    "superhuman":   {"tags": ["saas", "email", "premium", "keyboard-driven"],    "use_cases": ["app", "landing"],                        "industry": "saas"},
    "vodafone":     {"tags": ["telecom", "red", "corporate", "european"],        "use_cases": ["brand", "landing", "app"],              "industry": "telecom"},
    "warp":         {"tags": ["saas", "terminal", "dark", "developer"],          "use_cases": ["developer-tool", "app"],                 "industry": "saas"},
    "voltagent":    {"tags": ["saas", "agent", "ai", "dark"],                    "use_cases": ["ai-product", "landing"],                 "industry": "ai"},
    "ripple":       {"tags": ["fintech", "crypto", "blue", "payment"],           "use_cases": ["fintech", "landing"],                    "industry": "fintech"},
}


def extract_frontmatter(filepath):
    """Extract YAML frontmatter from a DESIGN.md file."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None

    try:
        data = yaml.safe_load(parts[1])
        return data
    except yaml.YAMLError:
        return None


def simplify_tokens(data):
    """Extract only the essential design tokens from a full DESIGN.md."""
    result = {}

    if "colors" in data:
        result["colors"] = data["colors"]

    if "typography" in data:
        result["typography"] = data["typography"]

    if "rounded" in data:
        result["rounded"] = data["rounded"]

    if "spacing" in data:
        result["spacing"] = data["spacing"]

    if "components" in data:
        result["components"] = data["components"]

    # Extract the markdown text after frontmatter for do/dont guidance
    return result


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/awesome-design-md")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".claude/skills/design-system/tokens")

    out.mkdir(parents=True, exist_ok=True)

    design_dir = src / "design-md"
    if not design_dir.exists():
        print(f"ERROR: {design_dir} not found")
        sys.exit(1)

    count = 0
    for brand_dir in sorted(design_dir.iterdir()):
        if not brand_dir.is_dir():
            continue

        md_file = brand_dir / "DESIGN.md"
        if not md_file.exists():
            continue

        data = extract_frontmatter(md_file)
        if not data:
            print(f"SKIP {brand_dir.name}: cannot parse frontmatter")
            continue

        brand_name = brand_dir.name
        tokens = simplify_tokens(data)

        # Add brand metadata
        tokens["name"] = data.get("name", brand_name)
        tokens["description"] = data.get("description", "")
        tokens["brand"] = brand_name

        # Attach routing metadata
        meta = BRAND_META.get(brand_name, {
            "tags": ["general"],
            "use_cases": ["landing"],
            "industry": "general"
        })
        tokens["meta"] = meta

        # Extract a brief color summary
        colors = tokens.get("colors", {})
        key_colors = {}
        for k in ["primary", "ink", "canvas", "background"]:
            if k in colors:
                key_colors[k] = colors[k]
        tokens["key_colors"] = key_colors

        out_file = out / f"{brand_name}.yaml"
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(yaml.dump(tokens, allow_unicode=True, default_flow_style=False, sort_keys=False))

        count += 1
        print(f"  -> {brand_name}.yaml")

    print(f"\nDone. {count} brand token files written to {out}")

    # Write brand index
    index_path = out / "index.json"
    index = {}
    for brand_dir in sorted(design_dir.iterdir()):
        if not brand_dir.is_dir():
            continue
        bn = brand_dir.name
        meta = BRAND_META.get(bn, {"tags": ["general"], "use_cases": ["landing"], "industry": "general"})
        index[bn] = meta

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"  -> index.json")


if __name__ == "__main__":
    main()
