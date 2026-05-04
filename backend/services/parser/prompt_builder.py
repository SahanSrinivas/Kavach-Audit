"""Build the structured XML prompt sent to Claude for PDF parsing.

The prompt is designed to be deterministic (temperature=0 in the API call)
and self-validating (Claude self-assesses confidence per <confidence_rules>).

Returned string is fed to Claude as the text block alongside the PDF
document content block. See pdf_parser.parse_policy_pdf().

Implementation note — substitution mechanism:
    We use plain str.replace() rather than str.format() so the template
    can contain literal JSON examples ({"type": "fixed_amount"}) without
    the doubled-brace escape ({{}}) that .format() requires. The single
    substitution placeholder {canonical_insurers} is the only thing
    .replace() touches; everything else in the template is preserved
    verbatim. See test_prompt_builder.py for the regression tests that
    enforce this contract.
"""
from __future__ import annotations

from services.parser.canonical_vocabulary import CANONICAL_INSURER_NAMES


def _canonical_insurers_block() -> str:
    """Render the canonical insurer name list with their common aliases.
    Generated from CANONICAL_INSURER_NAMES so the prompt is always in sync
    with the canonicalizer + the engine's CSR_TABLE.
    """
    # Aliases per insurer — kept here (not in canonical_vocabulary) because
    # they are prompt copywriting (helps Claude disambiguate), distinct from
    # the runtime substring map used by insurer_canonicalizer.
    aliases_for_prompt: dict[str, list[str]] = {
        # Health insurers
        "New India Assurance":   ["The New India Assurance Co.", "NIA"],
        "Go Digit Health":       ["Digit Insurance", "Go Digit General"],
        "Bajaj Allianz General": ["Bajaj Allianz", "Bajaj Allianz Health"],
        "HDFC ERGO General":     ["HDFC ERGO", "HDFC Ergo Optima",
                                  "HDFC Ergo Health Suraksha", "HDFC Ergo my:health Suraksha"],
        "Acko Health":           ["Acko General", "Acko"],
        "Niva Bupa":             ["Max Bupa", "Niva Bupa Health Insurance"],
        "Star Health":           ["Star Health and Allied Insurance", "Star Comprehensive"],
        "ICICI Lombard":         ["ICICI Lombard General", "ICICI Lombard Complete Health"],
        "Aditya Birla Health":   ["Aditya Birla Activ Health", "ABHI"],
        "Care Health":           ["Religare Health", "Care Health Insurance"],
        "Tata AIG General":      ["Tata AIG", "Tata AIG MediCare"],
        "ManipalCigna":          ["Manipal Cigna", "Cigna TTK"],
        "National Insurance":    ["National Insurance Co."],
        "Reliance General":      ["Reliance Health"],
        "IFFCO Tokio":           ["IFFCO Tokio General"],
        "Future Generali":       ["Generali Central", "Future Generali India"],
        "Universal Sompo":       ["Universal Sompo General"],
        "Shriram General":       ["Shriram General Insurance"],
        # Life insurers — note for Claude: distinguish from same-parent
        # health entities (e.g. "HDFC Life" ≠ "HDFC ERGO General",
        # "Tata AIA Life" ≠ "Tata AIG General").
        "LIC":                   ["LIC of India", "Life Insurance Corporation of India"],
        "HDFC Life":             ["HDFC Standard Life", "HDFC Life Insurance"],
        "ICICI Prudential Life": ["ICICI Pru", "ICICI Prudential Life Insurance"],
        "Max Life":              ["Max Life Insurance", "Max Financial Services"],
        "Tata AIA Life":         ["Tata AIA Life Insurance", "Tata AIA"],
        "SBI Life":              ["SBI Life Insurance", "State Bank Life"],
        "Bajaj Allianz Life":    ["Bajaj Allianz Life Insurance"],
        "Aditya Birla Sun Life": ["ABSLI", "Birla Sun Life", "Aditya Birla Sun Life Insurance"],
        "Kotak Life":            ["Kotak Mahindra Life", "Kotak Life Insurance"],
        "PNB MetLife":           ["MetLife India", "PNB MetLife India"],
        "Exide Life":            ["Exide Life Insurance"],   # legacy; merged into HDFC Life Jan 2023 but pre-merger policies retain branding
    }
    lines: list[str] = []
    for canonical in CANONICAL_INSURER_NAMES:
        aliases = aliases_for_prompt.get(canonical, [])
        if aliases:
            lines.append(f'- "{canonical}" — also matches: '
                         + ", ".join(f'"{a}"' for a in aliases))
        else:
            lines.append(f'- "{canonical}"')
    return "\n".join(lines)


# IMPORTANT: this template is interpolated via .replace(), NOT .format().
# Literal JSON braces are written single ({"key": "value"}) and pass
# through verbatim. The only substitution token is {canonical_insurers}.
_PROMPT_TEMPLATE = """\
You are an expert Indian health insurance policy analyst. Your job is to extract structured data from a policy PDF document with extreme accuracy. You will be given a PDF and must return a JSON object matching a strict schema. Indian insurance policies vary in structure across 19+ insurers, but the data points we need are consistent across all of them.

<output_schema>
{
  "insurer_name": "string — canonical insurer name (see <canonical_insurer_names> below)",
  "insurer_name_raw": "string — exact text as written in policy",
  "policy_type": "enum — one of: health_individual, health_family_floater, health_senior, term_life, endowment, ulip, motor_private_car, motor_two_wheeler, personal_accident, travel_international, travel_domestic, home, critical_illness, super_topup",
  "policy_number": "string or null",
  "plan_name": "string or null — canonical short product name (see <plan_name_extraction>)",
  "plan_name_raw": "string or null — verbatim product name from cover page",
  "sum_insured": "integer in INR (e.g., 1500000 for 15 Lakhs)",
  "premium_annual": "integer in INR",
  "premium_frequency": "enum — annual, semi_annual, quarterly, monthly",
  "policy_start_date": "ISO date YYYY-MM-DD or null",
  "policy_end_date": "ISO date YYYY-MM-DD or null",
  "covered_members": [
    {
      "name": "string or null",
      "relationship": "enum — self, spouse, son, daughter, father, mother, other",
      "age": "integer or null",
      "gender": "enum — male, female, other or null"
    }
  ],
  "is_employer_group": "boolean — true if this is corporate/employer-provided cover",
  "parsed_fields": {
    "room_rent_cap": {
      "type": "enum — fixed_amount, percentage_of_si, no_cap, single_private_room",
      "value": "integer (rupees if fixed_amount; basis-points-of-100 if percentage_of_si — e.g., 100 = 1%)",
      "raw_text": "exact policy quote"
    },
    "icu_cap": {
      "type": "enum — fixed_amount, percentage_of_si, no_cap",
      "value": "integer",
      "raw_text": "string"
    },
    "copay_percent": "integer 0-100",
    "copay_applies_to": "enum — all_claims, senior_citizens_only, specific_diseases, none",
    "ped_waiting_months": "integer",
    "specific_disease_waiting": [
      { "category": "string — e.g., cataract, hernia, ENT", "months": "integer" }
    ],
    "initial_waiting_period_days": "integer — typically 30",
    "permanent_exclusions": ["array of strings — each exclusion exactly as written in the document"],
    "network_hospital_count": "integer or null",
    "restoration_benefit": {
      "available": "boolean",
      "type": "enum — once_per_year, unlimited, none",
      "applies_to": "enum — same_illness, different_illness, both"
    },
    "ncb_structure": {
      "max_percent": "integer — e.g., 100 for 100% bonus",
      "increment_per_year": "integer"
    },
    "sub_limits": [
      {
        "category": "string — e.g., cataract, knee_replacement, maternity",
        "limit_amount": "integer or null",
        "limit_percent_of_si": "integer or null",
        "raw_text": "string"
      }
    ],
    "ambulance_cap": "integer or null",
    "day_care_procedures_count": "integer or null"
  },
  "confidence": {
    "overall": "enum — high, medium, low",
    "fields_with_low_confidence": ["array of field names where extraction was uncertain"],
    "warnings": ["array of human-readable warnings about ambiguities"]
  }
}
</output_schema>

<canonical_insurer_names>
Map any variation of an insurer's name to exactly one of these canonical names:

{canonical_insurers}

If you cannot match to one of these, set insurer_name to "_UNKNOWN" and put the actual name in insurer_name_raw.
</canonical_insurer_names>

<extraction_rules>
1. Room rent caps appear in multiple formats. Examples:
   - "Rs. 5,000 per day" -> type=fixed_amount, value=5000
   - "1% of Sum Insured per day" -> type=percentage_of_si, value=100 (basis points)
   - "Up to single private AC room" -> type=single_private_room, value=null
   - No mention or "Actuals" -> type=no_cap, value=null

2. Sum insured can be written as "Rs. 5 Lakhs", "Rs. 5,00,000", "5L", or "Rs. 500000". Always convert to integer rupees. 5L = 500000.

3. Co-pay applies to specific situations. Read carefully:
   - "10% co-payment on all claims" -> copay_percent=10, copay_applies_to=all_claims
   - "20% co-payment for insured aged 61+" -> copay_percent=20, copay_applies_to=senior_citizens_only
   - "10% on PED claims only" -> copay_applies_to=specific_diseases
   If multiple co-pay clauses exist, return the one that applies to the primary insured.

4. PED waiting period is in MONTHS, not years. Convert "3 years" -> 36, "4 years" -> 48.

5. Permanent exclusions are typically listed in a section titled "Exclusions" or "What is not covered". Extract the bullet list verbatim. Do NOT include standard waiting periods (those are temporal, not permanent).

6. Network hospital count: look for phrases like "10,000+ network hospitals", "12,500 cashless network hospitals". If only stated as "extensive network" with no number, set to null.

7. Restoration benefit: also called "Recharge", "Refill", "Reset", "Reinstatement". Look for these terms.

8. NCB (No Claim Bonus): also called "Cumulative Bonus", "Wellness Bonus". Standard increment is 25% per year, max 100% — but premium plans go up to 200% or even 500%.

9. Sub-limits often appear in a table titled "Sub-limits" or "Capping". Common sub-limits: cataract, hernia, maternity, knee replacement, day care procedures.

10. If a field is genuinely not findable in the document, set it to null. Do NOT guess. Do NOT infer.

11. For employer/group policies, the policy schedule will mention the company name as the master policy holder. Set is_employer_group=true.

12. covered_members: extract from the policy schedule, not from proposal form attachments. If only the primary insured is named, return a single-element array.

13. Null handling for nested objects (room_rent_cap, icu_cap, restoration_benefit, ncb_structure):
    - PREFERRED: if the entire clause is absent from the document, return the WHOLE object as null:
        "room_rent_cap": null
    - ACCEPTABLE: if you found the clause but couldn't extract some leaves, set those leaves null individually:
        "room_rent_cap": {"type": "fixed_amount", "value": 5000, "raw_text": null}
    - DO NOT return an object with all fields null:
        "room_rent_cap": {"type": null, "value": null, "raw_text": null}    ← bad; use null instead
    Same rule for icu_cap, restoration_benefit, ncb_structure, and any sub_limit array entries (a sub_limit without a `category` is unusable; omit it from the array entirely rather than including it with category=null).

14. policy_type is REQUIRED — never null. If you can't determine the type confidently, infer the closest match from the canonical enum and add "policy_type" to confidence.fields_with_low_confidence with a warning. The audit engine cannot route a policy without a type.

15. sum_insured and premium_annual are nullable. If the document is a policy WORDING (terms-and-conditions document) or a brochure rather than a policy SCHEDULE (the document with the user's specific amounts), set both to null and set confidence.overall to "low" with a warning naming the document type. Do NOT guess or substitute typical values.

16. permanent_exclusions: extract the bullet list verbatim. Each entry is the exclusion text exactly as it appears in the document (e.g., "Sterility and Infertility", "Cosmetic or plastic Surgery", "War or similar situations"). Do NOT canonicalize, abbreviate, or categorize — the engine canonicalizes server-side using a maintained vocabulary. Do NOT add entries that are not in the document; do NOT invent categories.

17. plan_name and plan_name_raw — extract the marketing/product name. This is the join key for our wordings database (we look up policy rules by this name when a user uploads only a schedule).

    plan_name_raw: the full verbatim text exactly as printed on the schedule's cover page (or the wording document's title for wording-only PDFs). Include all qualifiers verbatim. Examples:
      - "HDFC ERGO Optima Restore Family Floater Plan"
      - "ReAssure 2.0 Individual"
      - "Star Comprehensive Insurance Policy"
      - "Niva Bupa Health Companion Variant 2"

    plan_name: the canonical short product name with insurer prefix and variant suffixes ("Individual", "Family Floater", "Senior", "Plan", "Policy", "Variant N", etc.) stripped. Use the most commonly-known short form — the name a customer would search for online. Examples for the above:
      - "Optima Restore"
      - "ReAssure 2.0"
      - "Star Comprehensive"
      - "Health Companion"

    Both fields are nullable. Set to null only if you genuinely cannot find a product name in the document. Renewal certificates and benefit illustrations almost always have the product name on page 1 — extract it. Wording documents have it in the title.

    Do NOT invent a product name. If the document only has a generic label (e.g., "Group Health Insurance Policy" with no product brand), set plan_name to null and put the generic label in plan_name_raw.
</extraction_rules>

<confidence_rules>
Set confidence.overall based on these rules:
- "high" if all of: insurer matched canonically, sum_insured extracted, premium extracted, room_rent_cap and copay_percent both successfully parsed, policy_end_date found
- "medium" if 1-2 of those are missing or low-confidence
- "low" if 3+ are missing, OR if the document appears truncated, OR if the insurer is "_UNKNOWN"

For each field where you had to make a judgment call (e.g., resolving conflicting clauses, choosing between two co-pay percentages, inferring policy_type from product name), add the field name to fields_with_low_confidence.

Add a human-readable warning to warnings[] for any of:
- "Multiple co-pay clauses found; returned the one applying to all claims"
- "Sum insured stated in lakhs format; converted to rupees"
- "Restoration benefit terminology unclear; defaulted to once_per_year"
- "Document appears to be a renewal certificate, not full policy schedule; some fields may be incomplete"
</confidence_rules>

<critical_rules>
- NEVER hallucinate values. If a field is not in the document, return null.
- NEVER round sum_insured or premium. Extract the exact integer.
- NEVER assume a value based on what's "typical". A user with a non-standard policy needs the actual values.
- NEVER include personal data (names, phone numbers, addresses) in confidence.warnings or any other field except covered_members.name. The audit must respect privacy.
- If the document is not an Indian insurance policy (e.g., uploaded by mistake), return: {"error": "not_an_indian_insurance_policy", "details": "brief description of what was uploaded"}
- If the document is unreadable (corrupted PDF, scanned image with no OCR layer), return: {"error": "document_unreadable", "details": "specific issue"}
- Return ONLY valid JSON. No markdown code fences. No prose explanation. The first character of your response must be '{'.
</critical_rules>
"""

# Sanity: catch any future drift to .format() syntax. If the template ever
# contains the doubled-brace escapes, we're back in fragile territory.
_TEMPLATE_DOUBLED_BRACE_COUNT = _PROMPT_TEMPLATE.count("{{") + _PROMPT_TEMPLATE.count("}}")
assert _TEMPLATE_DOUBLED_BRACE_COUNT == 0, (
    f"prompt template contains {_TEMPLATE_DOUBLED_BRACE_COUNT} doubled braces — "
    f"these are .format() escape artifacts. Use single braces; .replace() handles substitution."
)


def build_parsing_prompt() -> str:
    """Returns the full text prompt sent alongside the PDF document block.

    Uses str.replace() (not str.format()) so literal JSON examples in the
    template stay readable as single-brace JSON. The only substitution
    token is {canonical_insurers}.
    """
    return _PROMPT_TEMPLATE.replace(
        "{canonical_insurers}",
        _canonical_insurers_block(),
    )
