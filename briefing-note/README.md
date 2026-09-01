# Briefing note

**`main.tex` is a reference example, not a submission.** The competition brief
states that AI tools may not be used to prepare the briefing note or the
presentation. This document exists so you can see how the required sections fit
together at the required length, and so you can write your own from a working
model rather than a blank page. Replace the prose.

## Files

| File | What it is |
|---|---|
| `main.tex` | The example note. Correct format: 11pt, double spaced, six pages, five required sections, references and appendices beyond the limit |
| `main.pdf` | Compiled output |
| `FACTS.md` | Every figure with its provenance tier, source and caveat. **This is the part to write from.** |

## Build

```bash
tectonic -X compile main.tex
```

`tectonic` fetches packages on first run and needs a network connection for it.

## The format the brief requires

- Maximum **6 pages**, double spaced, **11-point**, PDF
- Must contain: executive summary, recommendations, problem statement,
  methodology, analysis
- A reference list and appendices may be included **in addition** to the 6 pages
- Audience: "senior decision-makers" in transportation
- Scored **30%** of the competition; the presentation is the other 70%

Double spacing is expensive: six pages is roughly **1,800 words**. The example
runs five pages of body plus one of references and appendices, which leaves you
a page of headroom. Tables are set single-spaced so they buy space rather than
cost it.

## Before you submit

1. **Write your own prose.** Do not submit this file.
2. **Disclose the AI use.** The brief requires you to say where and how tools
   were used. See §12 of `FACTS.md`.
3. **Confirm two professional interviews.** A hard requirement, and only with
   industry stakeholders — not the public.
4. **Check the delay finding.** Operations removing 45.2% against the charge's
   39.4% reversed a previously published result on 2026-08-31. Any older draft
   claiming pricing beats operations is out of date.
