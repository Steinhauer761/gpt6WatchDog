import os
import sys
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .auth import auth_configured, create_session_token, require_session, validate_password
from .media import inspect_media_file
from .services import ask_openai, decode_vin, geocode, lookup_public_ip, network_probe, triage_text
from .web_probe import web_security_probe

WORKER_DIR = Path(__file__).resolve().parents[2] / "worker"
if WORKER_DIR.exists() and str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))

try:
    from public_osint import PublicSearchError, search_public_sources
except Exception:
    PublicSearchError = ValueError
    search_public_sources = None

try:
    from web_crawl import PublicUrlError, crawl_public_site
except Exception:
    PublicUrlError = ValueError
    crawl_public_site = None

try:
    from research_search import ResearchSearchError, search_research_sources
except Exception:
    ResearchSearchError = ValueError
    search_research_sources = None

try:
    from tor_research import TorResearchError, crawl_onion_site, fetch_onion_text
except Exception:
    TorResearchError = ValueError
    crawl_onion_site = None
    fetch_onion_text = None

try:
    from onion_discovery import discover_onion_addresses
except Exception:
    discover_onion_addresses = None

ALLOWED_ORIGINS = [value.strip() for value in os.environ.get("WATCHDOG_ALLOWED_ORIGINS", "http://localhost:3000").split(",") if value.strip()]

app = FastAPI(title="WatchDog API", version="1.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=512)


class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200_000)


class IpRequest(BaseModel):
    ip: str = Field(min_length=2, max_length=64)


class AssistantMessage(BaseModel):
    role: str
    content: str


class AssistantRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12_000)
    history: list[AssistantMessage] = Field(default_factory=list, max_length=8)


class PublicSearchRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)
    kind: str = Field(default="name", max_length=32)
    max_per_source: int = Field(default=6, ge=1, le=10)


class ResearchSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=320)
    scope: str = Field(default="both", max_length=8)
    max_results: int = Field(default=12, ge=1, le=20)


class OnionDiscoveryRequest(BaseModel):
    query: str = Field(default="", max_length=320)
    category: str = Field(default="all", max_length=32)
    max_results: int = Field(default=100, ge=1, le=100)


class CrawlRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    max_pages: int = Field(default=10, ge=1, le=25)
    max_depth: int = Field(default=1, ge=0, le=2)


class OnionRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class OnionCrawlRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    max_pages: int = Field(default=8, ge=1, le=12)
    max_depth: int = Field(default=1, ge=0, le=2)


class NetworkProbeRequest(BaseModel):
    target: str = Field(min_length=1, max_length=253)
    ports: list[int] = Field(default_factory=lambda: [22, 53, 80, 443, 445, 3389, 8080], min_length=1, max_length=20)
    authorization_confirmed: bool = False


class WebProbeRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    authorization_confirmed: bool = False


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "watchdog-api",
        "version": "1.3.0",
        "python_backend": True,
        "auth_configured": auth_configured(),
        "ai_enabled": os.environ.get("WATCHDOG_AI_ENABLED", "false").lower() == "true",
        "openai_key_configured": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
        "tor_proxy_configured": bool(os.environ.get("TOR_SOCKS_PROXY", "").strip()),
        "features": [
            "assistant",
            "triage",
            "media-inspection",
            "ip-intel",
            "vin-decode",
            "geocode",
            "public-osint",
            "research-search-web-tor-archive",
            "onion-address-discovery",
            "bounded-crawl",
            "bounded-onion-crawl",
            "onion-text-fetch",
            "authorized-network-probe",
            "authorized-web-security-probe",
        ],
    }


@app.post("/v1/auth/login")
def login(payload: LoginRequest):
    if not auth_configured():
        raise HTTPException(status_code=503, detail="Set WATCHDOG_ADMIN_PASSWORD and WATCHDOG_SESSION_SECRET first")
    if not validate_password(payload.password):
        raise HTTPException(status_code=401, detail="Incorrect password")
    token, expires_at = create_session_token()
    return {"token": token, "expires_at": expires_at}


@app.post("/v1/assistant", dependencies=[Depends(require_session)])
async def assistant(payload: AssistantRequest):
    return await ask_openai(payload.message, [item.model_dump() for item in payload.history])


@app.post("/v1/triage/text", dependencies=[Depends(require_session)])
def triage(payload: TextRequest):
    return triage_text(payload.text)


@app.post("/v1/media/inspect", dependencies=[Depends(require_session)])
async def media_inspect(file: UploadFile = File(...)):
    return await inspect_media_file(file)


@app.post("/v1/intel/ip", dependencies=[Depends(require_session)])
async def ip_intel(payload: IpRequest):
    return await lookup_public_ip(payload.ip)


@app.get("/v1/vehicle/vin/{vin}", dependencies=[Depends(require_session)])
async def vin(vin: str):
    return await decode_vin(vin)


@app.get("/v1/maps/geocode", dependencies=[Depends(require_session)])
async def maps_geocode(q: str = Query(min_length=1, max_length=180)):
    return await geocode(q)


@app.post("/v1/osint/search", dependencies=[Depends(require_session)])
async def osint_search(payload: PublicSearchRequest):
    if search_public_sources is None:
        raise HTTPException(status_code=503, detail="OSINT service modules are unavailable")
    try:
        return await search_public_sources(payload.identifier, payload.kind, payload.max_per_source)
    except PublicSearchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Public-source search failed: {type(exc).__name__}") from exc


@app.post("/v1/research/search", dependencies=[Depends(require_session)])
async def research_search(payload: ResearchSearchRequest):
    if search_research_sources is None:
        raise HTTPException(status_code=503, detail="Research search modules are unavailable")
    try:
        return await search_research_sources(payload.query, payload.scope, payload.max_results)
    except ResearchSearchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Research search failed: {type(exc).__name__}") from exc


@app.post("/v1/research/onion/discover", dependencies=[Depends(require_session)])
async def onion_discover(payload: OnionDiscoveryRequest):
    if discover_onion_addresses is None:
        raise HTTPException(status_code=503, detail="Onion discovery module is unavailable")
    try:
        return await discover_onion_addresses(payload.query, payload.category, payload.max_results)
    except TorResearchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Onion discovery failed: {type(exc).__name__}") from exc


@app.post("/v1/crawl/site", dependencies=[Depends(require_session)])
async def crawl(payload: CrawlRequest):
    if crawl_public_site is None:
        raise HTTPException(status_code=503, detail="Crawler service module is unavailable")
    try:
        return await crawl_public_site(payload.url, max_pages=payload.max_pages, max_depth=payload.max_depth)
    except PublicUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Site crawl failed: {type(exc).__name__}") from exc


@app.post("/v1/research/onion/fetch", dependencies=[Depends(require_session)])
async def onion_fetch(payload: OnionRequest):
    if fetch_onion_text is None:
        raise HTTPException(status_code=503, detail="Tor research module is unavailable")
    try:
        return await fetch_onion_text(payload.url)
    except TorResearchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Onion fetch failed: {type(exc).__name__}") from exc


@app.post("/v1/research/onion/crawl", dependencies=[Depends(require_session)])
async def onion_crawl(payload: OnionCrawlRequest):
    if crawl_onion_site is None:
        raise HTTPException(status_code=503, detail="Tor crawler module is unavailable")
    try:
        return await crawl_onion_site(payload.url, max_pages=payload.max_pages, max_depth=payload.max_depth)
    except TorResearchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Onion crawl failed: {type(exc).__name__}") from exc


@app.post("/v1/probe/network", dependencies=[Depends(require_session)])
async def probe_network(payload: NetworkProbeRequest):
    if not payload.authorization_confirmed:
        raise HTTPException(status_code=400, detail="Explicit authorization confirmation is required")
    result = await network_probe(payload.target, payload.ports)
    result["authorization_confirmed"] = True
    return result


@app.post("/v1/probe/web-security", dependencies=[Depends(require_session)])
async def probe_web(payload: WebProbeRequest):
    if not payload.authorization_confirmed:
        raise HTTPException(status_code=400, detail="Explicit authorization confirmation is required")
    result = await web_security_probe(payload.url)
    result["authorization_confirmed"] = True
    return result
