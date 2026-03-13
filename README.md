# analyze-event-impact

`analyze-event-impact` is an AI skill for event-driven market analysis. It is designed to help users analyze how wars, policy changes, regulation, geopolitics, public opinion shocks, supply disruptions, earnings, and other events may affect asset prices, sector performance, and market expectation gaps.

Its core role is not to act as a knowledge base itself, but to turn event analysis into a reusable workflow:

- build a reference frame for the event
- identify market consensus and priced-in assumptions
- locate the expectation gap
- map transmission channels across supply, demand, policy, sentiment, and liquidity
- produce scenario trees, validation signals, and structured conclusions

For advanced users, the skill can incorporate private research, internal notes, historical analogs, and house views. For ordinary users without a private knowledge base, it can still produce a first-pass analysis from a few core assumptions.

The output is designed to be highly visual and shareable. It prefers tables, scenario trees, structured summaries, and can export the final report as a PDF.

## What This Skill Does

- Guides event-driven analysis with a structured reasoning framework
- Separates facts, inference, and unknowns
- Focuses on expectation gaps instead of generic summaries
- Supports both professional users with proprietary context and ordinary users with only a rough hypothesis
- Produces client-friendly outputs with tables, scenario comparisons, and monitoring checklists
- Exports Markdown reports to PDF

## What This Skill Does Not Do

- It is not a substitute for a private knowledge base
- It does not magically inject domain expertise without context
- It does not replace real-time data verification for recent events

## Folder Structure

```text
analyze-event-impact/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   ├── event-impact-framework.md
│   ├── intake-template.md
│   └── private-context-template.md
└── scripts/
    └── render_report_pdf.py
```

## Key Files

- `SKILL.md`
  The main workflow and reasoning rules for the skill.

- `references/intake-template.md`
  Low-friction intake template for users. Includes both English and Chinese versions.

- `references/private-context-template.md`
  Template for loading proprietary research, internal notes, analog libraries, and house views.

- `references/event-impact-framework.md`
  Reusable event-impact reasoning skeleton.

- `scripts/render_report_pdf.py`
  Converts markdown-style reports into PDF. Prefers a styled ReportLab renderer and falls back to a plain-text macOS renderer when necessary.

## Usage Pattern

Typical workflow:

1. Collect the event and user hypothesis
2. Build the reference frame
3. Identify what the market may already believe
4. Test for expectation gaps
5. Map impact channels across assets and time horizons
6. Produce a structured answer
7. Export the report to PDF if needed

## PDF Export

To render a markdown report into PDF:

```bash
python3 scripts/render_report_pdf.py /path/to/report.md /path/to/report.pdf --preview-png
```

For prettier output, install:

```bash
python3 -m pip install reportlab
```

Without `reportlab`, the script falls back to a simpler macOS built-in renderer.

## Recommended Positioning

This skill works best when positioned as:

**A reasoning framework for event-driven analysis, not a replacement for domain knowledge.**

Its value comes from making the analysis process more structured, more repeatable, more visual, and easier to share.
