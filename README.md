# construction-ai

AI Door Specification Copilot — ingests architectural blueprint packages, uses computer vision and AI to extract door schedules, connects related drawings, and generates draft hardware sets for human review.

## Stack

- **Frontend:** Next.js + React + TypeScript (dashboard, document viewer, upload, review, exports)
- **Backend:** Python + FastAPI (REST APIs, document processing, AI orchestration)
- **AI/CV:** OpenCV, PyMuPDF, PaddleOCR or Azure Document Intelligence, object detection (e.g. YOLO), vision-language models
- **Infra:** PostgreSQL (+ pgvector later), Redis + Celery, S3-compatible storage, Docker

## Layout

```
frontend/           Next.js app (app/, components/, dashboard/, document-viewer/)
backend/            FastAPI service (app/api, projects, documents, processing, database)
ai-engine/          CV/AI pipeline packages (pdf_processor, sheet_classifier, ocr,
                    door_detection, schedule_extraction, drawing_matching, hardware_engine)
dataset/            sample_drawings, annotations, evaluation
infrastructure/docker
```

## Run backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Principles

- Benchmark existing models before training our own.
- Every extracted attribute must be traceable to a drawing region (source references).
- Human review is a first-class part of the workflow.
- Vector PDF extraction, OCR, object detection and multimodal AI solve different problems — don't use one tool for everything.
