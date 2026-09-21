from fastapi import FastAPI

app = FastAPI(
    title="AI Business Intelligence Platform",
    description="AI-powered Business Intelligence and Automation Platform",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "message": "AI BI Platform is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }

@app.get("/about")
def about():
    return {
        "name": "AI Business Intelligence Platform",
        "purpose": "Business analytics, AI insights and automation",
        "version": "1.0.0"
    }