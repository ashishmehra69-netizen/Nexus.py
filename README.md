---
title: NEXUS Backend API
emoji: 🧠
colorFrom: purple
colorTo: green
sdk: docker
pinned: false
---

# 🧠 NEXUS Learning Generator - Backend API

REST API backend for NEXUS Learning Generator.

## API Endpoints

- `GET /` - API documentation
- `GET /api/health` - Health check
- `POST /api/research/topic` - Research a topic
- `POST /api/research/company` - Research a company
- `POST /api/generate` - Generate training content
- `POST /api/unlock/<session_id>` - Unlock content
- `POST /api/feedback` - Submit feedback
- `GET /api/feedback/stats` - Get feedback statistics

## Usage

This is a REST API. Use curl, Postman, or any HTTP client.

### Example: Health Check
```bash