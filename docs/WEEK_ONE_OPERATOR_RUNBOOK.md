# Week-One Operator Runbook

This runbook explains how to launch and validate the first FinMAS alpha workflow end to end.

## Goal

Run one finance workflow from search to result, then:

- publish it to Notion
- deliver it to a business channel
- export it for NotebookLM

## Before You Start

- Use the merged integration branch that includes the five Codex thread outputs.
- Use a machine where local services and loopback ports are allowed.
- Have access to:
  - Notion
  - at least one delivery channel: Slack, Teams, or email
  - external MCP endpoints for web search and web fetch

## Step 1: Prepare Credentials

Collect these before you begin:

- Notion integration or MCP authorization
- web search MCP URL and authorization
- web fetch MCP URL and authorization
- Slack webhook or Slack app credentials
- Teams webhook or Teams app credentials
- SMTP or email credentials if email delivery will be used

## Step 2: Decide Your First Live Setup

Choose the simplest possible first setup:

- one Boss
- one manager
- one or two workers
- one Notion destination
- one delivery destination
- one NotebookLM mode

Recommended NotebookLM default:

- export-only

## Step 3: Configure The Environment

In the repo root, create or update `.env`.

Add your real values for:

- Notion auth
- MCP search and fetch endpoints
- delivery credentials
- persistent audit or database DSN if needed

Do not over-configure multiple destinations for the first run. Start with one.

## Step 4: Set Up Notion

1. Create or approve the Notion integration.
2. Share the target page or database with the integration.
3. Decide whether results should go to:
   - a single page
   - a database
4. Put the Notion auth value into `.env`.

## Step 5: Set Up Delivery

Choose one to start:

- Slack
- Teams
- email

Then:

1. Create one test destination.
2. Add that destination to the configured allowlist.
3. Put the credential or webhook into `.env`.

## Step 6: Start The Stack

1. Activate your virtual environment.
2. Install dependencies if needed.
3. Start the stack with the new bootstrap command.
4. If the wrapper script is still the preferred entry, use that.

Then verify:

- the startup output shows the expected services
- the Personal Agent UI URL is shown
- Plaza and teamwork services are reachable

## Step 7: Open The UI

1. Open the Personal Agent UI in your browser.
2. Confirm it loads the managed-work interface.
3. Confirm you can see:
   - works
   - jobs
   - assignments
   - results
   - destination status

## Step 8: Run A Manual Work Item

1. Create one managed work item manually.
2. Use a simple query such as `AAPL and NVDA daily desk briefing`.
3. Confirm:
   - BossPulser creates the work
   - a manager is assigned
   - a worker is assigned through the manager
   - work state changes from created to running

## Step 9: Validate Search And Consolidation

1. Confirm the workflow uses the configured MCP search and fetch sources.
2. Confirm sources appear in the result.
3. Confirm the finance briefing includes:
   - summary
   - facts
   - inferred takeaways
   - risks
   - catalysts
   - conflicting evidence
   - open questions
   - citations

## Step 10: Validate Notion Publishing

1. Publish the result to Notion.
2. Confirm the page or database entry appears.
3. Check that it includes:
   - title
   - summary
   - citations
   - sources
   - timestamp
   - original query

## Step 11: Validate Delivery

1. Send the same result to your chosen channel.
2. Confirm it arrives.
3. Confirm the delivery status is visible in Personal Agent.

## Step 12: Validate NotebookLM Export

1. Generate the NotebookLM-ready pack.
2. Confirm the exported files are present.
3. If using export-only mode, manually import them into NotebookLM.
4. If using beta assisted import, test it separately and treat it as experimental.

## Step 13: Create A Scheduled Workflow

1. Create `morning_desk_briefing`.
2. Set a concrete schedule.
3. Use a small watchlist such as:
   - `AAPL`
   - `NVDA`
4. Save the workflow.
5. Let it run on schedule or trigger the due-run path.
6. Confirm the full path works again:
   - BossPulser issues work
   - manager assigns worker
   - result is produced
   - Notion publish succeeds
   - delivery succeeds
   - NotebookLM export succeeds

## Step 14: Review Policy And Audit

1. Confirm destination and execution policies are active.
2. Confirm one allowed action succeeds.
3. Confirm one denied action fails clearly.
4. Confirm audit records are created.

## Step 15: Sign Off Week-One Alpha

You are done when all of these are true:

- one-command startup works
- managed work is visible in Personal Agent
- BossPulser controls the workflow
- teamwork manager and worker assignment is visible
- finance briefing generation works
- Notion publish works
- one business delivery channel works
- NotebookLM export works
- policy and audit are active

## Human Decisions Still Needed

- final Notion destination model: page-first or database-first
- which delivery channel is primary
- whether NotebookLM is export-only or beta import
- manager assignment policy
- who is allowed to publish to which destinations

## Suggested First Demo Scenario

1. Create a scheduled `morning_desk_briefing` for `AAPL` and `NVDA`.
2. Let BossPulser issue the work.
3. Confirm manager and worker assignment.
4. Confirm MCP search and fetch sources are attached.
5. Confirm the final finance briefing is produced.
6. Confirm Notion publishing succeeds.
7. Confirm Slack, Teams, or email delivery succeeds.
8. Confirm NotebookLM export succeeds.
9. Confirm the entire run is visible in Personal Agent.
