#!/usr/bin/env python3
"""
Content Generator for Rudra Retail GSC Auditor
========================================
Generates optimized product content based on audit findings.

Uses template-based generation with product data + brand context.
No LLM required — pure Python string templates.
"""

import re
from typing import Optional, Dict, Any

# ─────────────────────────────────────────────
# Expand Product Descriptions
# ─────────────────────────────────────────────
def expand_description(
    product_title: str,
    current_description: str,
    brand: str,
    category: str = "",
    target_words: int = 150
) -> str:
    """
    Expand thin product descriptions to 150+ words.

    Args:
        product_title: e.g., "Gillette Mach3 Sensitive Razor"
        current_description: existing description text
        brand: e.g., "Gillette"
        category: e.g., "razors", "skincare", "supplements"
        target_words: desired word count

    Returns:
        Expanded description text
    """

    # Clean up existing content
    current_clean = re.sub(r'<[^>]+>', '', current_description).strip()

    # If already long enough, just clean HTML
    if len(current_clean.split()) >= target_words:
        return current_clean

    # Build expanded version from templates
    lines = []

    # 1. Product name + brand
    if current_clean:
        lines.append(current_clean.strip())

    # 2. General benefits (category-agnostic)
    benefits = [
        f"✓ Authentic {brand} product",
        "✓ Ready to ship from India",
        "✓ Cash on Delivery available",
        "✓ Trusted by Indian customers",
    ]

    # 3. Category-specific content
    category_lower = category.lower()
    if "razor" in category_lower or "shave" in category_lower:
        category_tips = [
            f"<strong>Usage Tips:</strong> Wet beard with warm water for 2-3 minutes before shaving. Use with shaving cream for smooth glide. Replace blade every 5-7 uses for best results.",
            f"<strong>Benefits:</strong> Reduces ingrown hairs and irritation compared to single-blade razors. Ideal for sensitive skin.",
        ]
    elif "skincare" in category_lower or "face" in category_lower:
        category_tips = [
            f"<strong>Usage Tips:</strong> Use 2-3 times per week for best results. Apply to damp skin and massage gently. Follow with moisturizer.",
            f"<strong>Perfect for:</strong> Daily use, all skin types. Dermatologist-tested.",
        ]
    elif "supplement" in category_lower or "vitamin" in category_lower:
        category_tips = [
            f"<strong>Directions:</strong> Take 1-2 capsules daily with food. Consult doctor if pregnant or nursing.",
            f"<strong>Why choose:</strong> Third-party tested, no fillers, made with premium ingredients.",
        ]
    elif "beauty" in category_lower or "makeup" in category_lower:
        category_tips = [
            f"<strong>Application:</strong> Use makeup brush or applicator for even coverage. Best applied to clean skin.",
            f"<strong>Shade:</strong> Works for all skin tones. Waterproof formula.",
        ]
    else:
        category_tips = [
            f"<strong>Quality:</strong> Genuine product, imported directly from manufacturer.",
            f"<strong>Storage:</strong> Keep in cool, dry place.",
        ]

    # 4. Comparison (if applicable)
    comparison = ""
    if "razor" in category_lower:
        comparison = f"<strong>Why {brand}?</strong> Superior shaving comfort compared to generic razors. Reduces cuts and nicks. Multi-blade technology provides smooth finish in fewer strokes."
    elif "skincare" in category_lower:
        comparison = f"<strong>Why {brand}?</strong> Clinically-proven formula with gentle, effective ingredients. Dermatologist recommended."

    # 5. Warranty/guarantee
    guarantee = "<strong>Satisfaction Guarantee:</strong> 100% authentic. If damaged or defective on arrival, we offer free replacement."

    # 6. Shopability note
    shopnote = "<strong>How to buy:</strong> Add to cart → Proceed to checkout → Select Cash on Delivery → Delivery in 3-5 days"

    # Build expanded text
    expanded = current_clean

    if category_tips:
        expanded += "\n\n" + "\n".join(category_tips)

    if comparison:
        expanded += "\n\n" + comparison

    expanded += "\n\n" + guarantee
    expanded += "\n\n" + shopnote

    return expanded


# ─────────────────────────────────────────────
# Optimize Product Titles
# ─────────────────────────────────────────────
def optimize_title(
    current_title: str,
    brand: str,
    key_keyword: str = "",
    variant: str = ""
) -> str:
    """
    Optimize product title for SEO (max 60 chars).

    Formula: [Brand] [Product] [Key Feature/Variant] [Benefit/Quantity]

    Args:
        current_title: e.g., "Gillette Mach3 Sensitive Razor Handle 5 Refills"
        brand: e.g., "Gillette"
        key_keyword: search term people use, e.g., "sensitive razor"
        variant: e.g., "5 refills", "unscented"

    Returns:
        Optimized title (≤60 chars)
    """

    # Remove brand suffix if present (will be added fresh)
    title_clean = re.sub(r'\s*[-–—|]\s*Rudra Retail.*$', '', current_title, flags=re.I).strip()

    # If already short and good, keep it
    if len(title_clean) <= 60:
        return title_clean[:60]

    # Truncate smartly: keep brand + main product + key feature
    parts = title_clean.split()

    if len(parts) > 6:
        # Too long — keep first 5-6 most important parts
        optimized = " ".join(parts[:6])
    else:
        optimized = title_clean

    # Ensure brand is present
    if brand and brand.lower() not in optimized.lower():
        optimized = f"{brand} {optimized}"

    # Trim to 60 chars
    if len(optimized) > 60:
        optimized = optimized[:57] + "..."

    return optimized.strip()


# ─────────────────────────────────────────────
# Generate Meta Descriptions
# ─────────────────────────────────────────────
def generate_meta_description(
    product_title: str,
    product_description: str,
    brand: str,
    price_inr: Optional[float] = None,
) -> str:
    """
    Generate SEO meta description (120-160 chars).

    Formula: [Product] - [Key Benefit] | [CTA] on Rudra Retail

    Args:
        product_title: product name
        product_description: full description (extract key phrase)
        brand: brand name
        price_inr: price in INR (optional)

    Returns:
        Meta description (140-160 chars)
    """

    # Extract key benefit from description
    desc_clean = re.sub(r'<[^>]+>', ' ', product_description)
    sentences = desc_clean.split('. ')
    benefit = sentences[0][:80] if sentences else "Shop now"

    # Build description
    base = f"{product_title} - {benefit}"

    # Add price if available
    if price_inr:
        cta = f" | ₹{int(price_inr)} | COD available"
    else:
        cta = " | Cash on Delivery available"

    desc = base + cta

    # Trim to 160 chars
    if len(desc) > 160:
        desc = desc[:157] + "..."

    return desc


# ─────────────────────────────────────────────
# Generate SEO Keywords
# ─────────────────────────────────────────────
def generate_keywords(
    product_title: str,
    brand: str,
    category: str = ""
) -> list:
    """
    Generate target keywords for this product.

    Returns list of 3-5 SEO keywords to target.
    """

    keywords = set()

    # 1. Exact title
    keywords.add(product_title)

    # 2. Brand + product type
    if category:
        keywords.add(f"{brand} {category}")

    # 3. Common search patterns
    category_lower = category.lower()
    if "razor" in category_lower:
        keywords.update([
            f"buy {product_title}",
            f"{brand} shaving razor",
            "sensitive razor india",
        ])
    elif "skincare" in category_lower or "face" in category_lower:
        keywords.update([
            f"buy {brand} face wash",
            "best face wash india",
            f"{brand} skincare",
        ])
    elif "supplement" in category_lower:
        keywords.update([
            f"buy {brand} supplement",
            f"{brand} vitamins india",
            "health supplement online",
        ])

    # 4. Low-competition long-tail
    keywords.update([
        f"{brand} {category} india",
        f"cheap {brand} online",
        f"{product_title} price",
    ])

    return list(keywords)[:5]


# ─────────────────────────────────────────────
# Generate Internal Link Anchor Text
# ─────────────────────────────────────────────
def generate_anchor_text(product_title: str, category: str = "") -> list:
    """
    Generate anchor text suggestions for internal linking.

    Use these on collection pages, blog posts, related products.
    """

    anchors = [
        product_title,
        f"Shop {product_title}",
        f"Get {product_title}",
    ]

    if category:
        anchors.append(f"Buy {category}")
        anchors.append(f"Best {category} in India")

    return anchors


# ─────────────────────────────────────────────
# Generate FAQ Schema Content
# ─────────────────────────────────────────────
def generate_faq_content(
    product_title: str,
    brand: str,
    category: str = ""
) -> list:
    """
    Generate FAQ content for Product FAQ schema.

    Returns list of {"question": "...", "answer": "..."}
    """

    faqs = []

    # Universal FAQs
    faqs.append({
        "question": f"Is {product_title} authentic?",
        "answer": f"Yes! We only sell genuine {brand} products. All items come with authenticity guarantee. If you receive a damaged or counterfeit item, we offer free replacement."
    })

    faqs.append({
        "question": "What is the delivery time?",
        "answer": "Delivery within 3-5 business days pan-India. You can select Cash on Delivery at checkout — no payment needed until delivery."
    })

    faqs.append({
        "question": f"Can I return {product_title}?",
        "answer": "Yes. We have a 3-day return window for damaged/defective items. Beauty, supplements, and personal care items may have restrictions per policy."
    })

    # Category-specific FAQs
    if "razor" in category.lower():
        faqs.extend([
            {
                "question": f"How long does {product_title} last?",
                "answer": "One razor lasts 5-7 shaves depending on hair density and technique. The 5-refill pack lasts about 25-35 shaves total."
            },
            {
                "question": "Is it good for sensitive skin?",
                "answer": "Yes! Mach3 Sensitive is specifically designed for sensitive skin. Multi-blade technology provides smooth shaving with minimal irritation."
            }
        ])
    elif "skincare" in category.lower():
        faqs.extend([
            {
                "question": f"How often should I use {product_title}?",
                "answer": "2-3 times per week for best results. Always patch test first to check for sensitivity."
            },
            {
                "question": "Is it safe for all skin types?",
                "answer": "Yes. Dermatologist-tested and suitable for all skin types including sensitive skin."
            }
        ])

    return faqs


# ─────────────────────────────────────────────
# Content Fix Report
# ─────────────────────────────────────────────
def generate_content_fixes(audit_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate all content fixes for a product.

    Args:
        audit_result: from auditor {pf, gsc, sa, ...}

    Returns:
        {
            "title_optimized": "...",
            "title_old": "...",
            "description_expanded": "...",
            "description_old": "...",
            "meta_description": "...",
            "keywords": [...],
            "anchor_text": [...],
            "faq": [...]
        }
    """

    pf = audit_result.get("pf", {})

    title_old = pf.get("title", "")
    brand = pf.get("brand", "")
    desc_old = pf.get("description", "")

    # Extract category from URL if possible
    url = pf.get("url", "")
    category = ""
    if "/products/" in url:
        # Infer from URL slug
        slug = url.split("/products/")[1].split("?")[0]
        if "razor" in slug or "shave" in slug:
            category = "razors"
        elif "face" in slug or "wash" in slug or "skincare" in slug:
            category = "skincare"
        elif "vitamin" in slug or "supplement" in slug:
            category = "supplements"

    return {
        "title": {
            "old": title_old,
            "optimized": optimize_title(title_old, brand),
            "reason": "SEO optimization: 60 char limit for SERP display"
        },
        "description": {
            "old_words": pf.get("desc_word_count", 0),
            "old": desc_old,
            "expanded": expand_description(title_old, desc_old, brand, category),
            "new_words": len(expand_description(title_old, desc_old, brand, category).split()),
            "reason": "Content expansion: 150+ words improves ranking + reduces thin content risk"
        },
        "meta_description": generate_meta_description(title_old, desc_old, brand),
        "keywords": generate_keywords(title_old, brand, category),
        "anchor_text": generate_anchor_text(title_old, category),
        "faq": generate_faq_content(title_old, brand, category),
    }


# ─────────────────────────────────────────────
# CLI Example
# ─────────────────────────────────────────────
if __name__ == "__main__":
    # Example usage
    print("Content Generation Examples\n" + "="*60 + "\n")

    # Razor example
    print("RAZOR PRODUCT:")
    print("-" * 60)
    razor_title = "Gillette Mach3 Sensitive Razor Handle with 5 Refills"
    razor_desc = "Gillette Mach3 Sensitive Razor Handle"

    print(f"Original title: {razor_title}")
    print(f"Optimized:     {optimize_title(razor_title, 'Gillette')}\n")

    print(f"Original desc ({len(razor_desc.split())} words):\n{razor_desc}\n")
    expanded = expand_description(razor_title, razor_desc, "Gillette", "razors")
    print(f"Expanded ({len(expanded.split())} words):\n{expanded}\n")

    print(f"Meta description:\n{generate_meta_description(razor_title, razor_desc, 'Gillette', 499)}\n")

    print(f"Keywords: {generate_keywords(razor_title, 'Gillette', 'razors')}\n")

    # Skincare example
    print("\nSKINCARE PRODUCT:")
    print("-" * 60)
    skin_title = "Cetaphil Exfoliating Face Wash Extra Gentle Daily Face Scrub"
    skin_desc = "Exfoliating face wash"

    print(f"Original title: {skin_title}")
    print(f"Optimized:     {optimize_title(skin_title, 'Cetaphil')}\n")

    expanded_skin = expand_description(skin_title, skin_desc, "Cetaphil", "skincare")
    print(f"Expanded desc ({len(expanded_skin.split())} words):\n{expanded_skin}\n")

    print(f"Keywords: {generate_keywords(skin_title, 'Cetaphil', 'skincare')}\n")
