# Collection Policy

## Purpose

This document defines the intended data-collection boundaries for the project.

The goal is to gather housing listing data in ways that are both practical and more defensible:

- public pages
- public embedded data
- officially documented APIs or export paths when legitimately available

## Default Rule

Use the least invasive viable method first.

Preferred order:

1. official API or export access you are authorized to use
2. public HTML pages and public structured data embedded in those pages
3. browser automation for public pages only when simple HTTP fetching is insufficient

## Out Of Scope Methods

Do not design the system around:

- login-gated collection
- private accounts or session sharing
- CAPTCHA solving services
- anti-bot bypassing
- hidden or undocumented endpoints as the primary ingestion contract

## Source Notes

### OLX

- OLX has a public developer portal: https://developer.olx.pl/en
- OLX `robots.txt` currently allows some API paths, including `/api/v1/offers/`, while disallowing many others
- inference: the official API should be investigated before building a heavier scraper

### Otodom

- Otodom exposes public listing pages
- Otodom rules for some professional users mention XML/API export for partners
- inference: if legitimate export access becomes available, prefer it over scraping

## Product Risk

Even for personal use, source rules can restrict aggregation and redistribution. If the project later becomes public, the compliance risk increases materially.

Because of that:

- keep the first use case personal and analytical
- avoid republishing source content more broadly than needed
- prefer aggregated analytics over mirroring full listing content

## Seller Classification Requirement

Every ingested listing should capture seller classification.

At minimum:

- `seller_segment`: `private`, `professional`, `unknown`
- `seller_type`: `private`, `agency`, `developer`, `unknown`

Keep the source evidence used for classification so ambiguous cases can be audited later.
