# n8n Workflow Automation

## Overview

n8n is used to automate contract processing workflows in this project. It orchestrates webhook-triggered automation for contract analysis and external integration events so processing can run consistently with minimal manual intervention.

## Accessing n8n

Open n8n at:

- http://localhost:5678

## Available Workflows

1. Contract Analysis Workflow - triggers when a contract is uploaded via webhook.
2. DocuSign Webhook Workflow - handles DocuSign webhook events.

## Setup Instructions

1. Start the project services so n8n is running.
2. Open the n8n UI at http://localhost:5678.
3. Sign in with the configured n8n credentials.
4. In n8n, click Import from file.
5. Select the workflow JSON file from this directory.
6. Repeat for each workflow JSON file you want to enable.
7. Review node credentials and environment-specific values.
8. Save and activate each imported workflow.

## Webhook URLs

- Contract Analysis Workflow webhook: http://localhost:5678/webhook/contract-analysis
- DocuSign Webhook Workflow webhook: http://localhost:5678/webhook/docusign
