"""FastAPI app: the JSON API under /api, plus the built React dashboard in production."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api_models import AnalyzeResponse, ReplyRequest, ReplyResult
from app.cache import Cache
from app.config import PROJECT_ROOT, Settings, get_settings
from app.csv_cleaner import CsvFormatError, parse_reviews_csv
from app.llm_client import ChatClient, GroqClient, LLMConfigError, LLMError
from app.pipeline import run_analysis
from app.replies import ReplyNotNeededError, ReplyWriter, ReviewNotFoundError

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

app = FastAPI(title="ReviewLens", version="1.0.0")


def get_cache(settings: Annotated[Settings, Depends(get_settings)]) -> Cache:
    return Cache(settings.db_path)


def get_llm(settings: Annotated[Settings, Depends(get_settings)]) -> Iterator[ChatClient]:
    """A fresh client per request, so its call counters describe exactly one run."""
    if not settings.groq_api_key:
        raise HTTPException(503, "The AI is not configured: set GROQ_API_KEY on the server.")
    client = GroqClient(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        reasoning_effort=settings.groq_reasoning_effort,
        base_url=settings.groq_base_url,
        timeout=settings.groq_timeout_seconds,
        max_retries=settings.max_retries,
    )
    try:
        yield client
    finally:
        client.close()


SettingsDep = Annotated[Settings, Depends(get_settings)]
CacheDep = Annotated[Cache, Depends(get_cache)]
LLMDep = Annotated[ChatClient, Depends(get_llm)]


@app.get("/api/health")
def health(settings: SettingsDep) -> dict:
    return {"status": "ok", "model": settings.groq_model, "ai_configured": bool(settings.groq_api_key)}


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(file: UploadFile, settings: SettingsDep, cache: CacheDep, llm: LLMDep) -> AnalyzeResponse:
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"The file is too large (limit {settings.max_upload_bytes // 1_000_000} MB).")
    try:
        reviews = parse_reviews_csv(data)
    except CsvFormatError as exc:
        raise HTTPException(400, str(exc)) from exc
    try:
        return run_analysis(reviews, llm, cache, settings.batch_size)
    except LLMConfigError as exc:
        raise HTTPException(502, f"The AI service rejected the request. {exc}") from exc


@app.post("/api/reply", response_model=ReplyResult)
def suggest_reply(request: ReplyRequest, cache: CacheDep, llm: LLMDep) -> ReplyResult:
    try:
        reply, cached = ReplyWriter(llm, cache).suggest(request.text_hash)
    except ReviewNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ReplyNotNeededError as exc:
        raise HTTPException(400, str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(502, f"Could not write a reply right now. {exc}") from exc
    return ReplyResult(reply=reply, cached=cached)


if FRONTEND_DIST.is_dir():

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        """Serve the built React app. Unknown paths get index.html so client-side routes work."""
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        file = (FRONTEND_DIST / path).resolve()
        if path and file.is_file() and file.is_relative_to(FRONTEND_DIST.resolve()):
            return FileResponse(file)
        return FileResponse(FRONTEND_DIST / "index.html")
