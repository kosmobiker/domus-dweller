# Open Questions

These are the remaining decisions that materially affect implementation.

## Source And Access

1. Which source should be the very first implementation target: Otodom or OLX?
2. Do you want only public pages, or are you open to browser automation if a public source becomes difficult?
3. Is daily refresh enough, or do you want twice per day from the start?

## Geography

4. What should count as the center of the 30 km radius: Krakow city center or a custom point?
5. Should we keep a few named municipalities always included even if some listings have imperfect coordinates?

## Data Quality

6. Do you want cross-source deduplication postponed until after the first two sources are stable?
7. How aggressive should we be about dropping listings with missing area, rooms, or coordinates?

## Workflow

8. Are you fine with a Python-first repo layout for now, with the web app added later rather than scaffolded immediately?
9. Do you want the notebook layer to use plain SQL plus Pandas first, or do you want Polars from the beginning?
