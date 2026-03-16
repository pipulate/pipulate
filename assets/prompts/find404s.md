============================================================================
PROMPT FU: SEMANTIC ROUTER (STRICT EXTRACTION MODE)
============================================================================
System Directive: Deterministic Lookup Table (CSV Output ONLY)

Your task is to map the dead URLs in LIST A to the exact, verbatim living URLs found in the INTERLEAVED SEMANTIC MAP (LIST B).

CRITICAL RULES - FAILURE IS NOT AN OPTION:
1. NO HALLUCINATIONS: Every single URL in Column 2 MUST exist exactly as written in the INTERLEAVED SEMANTIC MAP. You may not invent, shorten, or alter the destination URLs in any way.
2. VERIFICATION STEP: Before outputting a row, silently verify: "Does the URL in Column 2 exist in the provided semantic map?" If no, find a different match.
3. MATCHING LOGIC: Analyze the keywords, sub-topics, and summaries in the semantic map to find the best conceptual fit for the 404 path in LIST A.
4. STRICT FORMAT: Output ONLY a two-column CSV format.
5. Column 1: The dead URL from List A.
6. Column 2: The exact matched living URL from the semantic map.
7. DO NOT include headers, markdown formatting (no ```csv blocks), or explanations.
8. IMMUTABLE SOURCE: You must take the URLs in LIST A exactly as provided. You are strictly forbidden from creating, inventing, or predicting "potential" dead URLs based on the semantic map.
9. ONLY MAP OBSERVED DATA: If a URL does not appear in the provided LIST A, it must not appear in your output.
10. FILTER NOISE: Ignore any items in LIST A that contain spaces, semicolons, or begin with regex characters (e.g., `~^`). Treat them as invisible and DO NOT include them in your final CSV output.
11. RAW TEXT ONLY: You are strictly forbidden from converting URLs into clickable links. Do not use Markdown link syntax `[text](url)`, do not add asterisks, and do not generate search queries. Output the raw, unformatted text strings exactly as they exist in the source data.

Example Output:
/2012/07/old-article/,/futureproof/actual-living-url/
============================================================================
