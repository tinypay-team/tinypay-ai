from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Any
import os, uuid, logging

from services.crypto import execute_crypto_service
from services.news import execute_news_service
from services.image_gen import execute_image_generation
from services.pdf_gen import execute_pdf_generation
from services.generic import execute_generic_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Services Execution API", version="1.0.0")

# Serve generated files statically
os.makedirs("/app/generated_files", exist_ok=True)
app.mount("/files", StaticFiles(directory="/app/generated_files"), name="files")

BASE_URL = os.getenv("BASE_URL", "http://15.164.179.132:8001")


class ServiceItem(BaseModel):
    service_name: str
    service_type: str
    service_purpose: Optional[str] = ""
    estimated_cost: Optional[float] = 0
    currency: Optional[str] = "USDC"
    output_type: Optional[str] = "TEXT"


class PaymentResult(BaseModel):
    payment_id: int
    paid: bool
    total_paid_amount: float
    currency: str
    transaction_hash: Optional[str] = None
    payment_status: str


class ExecuteRequest(BaseModel):
    user_id: int
    chat_room_id: int
    session_id: Optional[str] = None
    original_prompt: str
    context: Optional[str] = ""
    payment_result: PaymentResult
    approved_services: List[ServiceItem]


AVAILABLE_SERVICES = [
    {
        "service_name": "CryptoPriceDataAPI",
        "service_type": "API",
        "description": "실시간 암호화폐 가격 데이터를 조회하는 API",
        "unit_cost": 0.03,
        "currency": "USDC",
        "output_type": "TEXT",
        "enabled": True,
    },
    {
        "service_name": "NewsDataAPI",
        "service_type": "API",
        "description": "최신 뉴스 데이터를 조회하는 API",
        "unit_cost": 0.02,
        "currency": "USDC",
        "output_type": "TEXT",
        "enabled": True,
    },
    {
        "service_name": "ImageGenerationAPI",
        "service_type": "API",
        "description": "사용자 프롬프트 기반 이미지를 생성하는 API",
        "unit_cost": 0.08,
        "currency": "USDC",
        "output_type": "IMAGE",
        "enabled": True,
    },
    {
        "service_name": "PDFGenerationService",
        "service_type": "FILE_GENERATOR",
        "description": "구조화된 내용을 PDF 파일로 생성하는 서비스",
        "unit_cost": 0.03,
        "currency": "USDC",
        "output_type": "PDF",
        "enabled": True,
    },
]


SERVICE_HANDLERS = {
    "CryptoPriceDataAPI": execute_crypto_service,
    "NewsDataAPI": execute_news_service,
    "ImageGenerationAPI": execute_image_generation,
    "PDFGenerationService": execute_pdf_generation,
    "DocumentStructuringAgent": execute_generic_service,
}


@app.post("/api/services/execute")
async def execute_services(request: ExecuteRequest):
    logger.info(f"Executing {len(request.approved_services)} services for user {request.user_id}")

    service_results = []
    generated_files = []
    final_output_type = "TEXT"

    for service in request.approved_services:
        try:
            handler = SERVICE_HANDLERS.get(service.service_name, execute_generic_service)
            result = await handler(
                service_name=service.service_name,
                service_type=service.service_type,
                original_prompt=request.original_prompt,
                context=request.context or "",
                base_url=BASE_URL,
            )

            service_results.append({
                "service_name": service.service_name,
                "service_type": service.service_type,
                "success": result.get("success", True),
                "result": result.get("data"),
                "error_message": result.get("error"),
            })

            if result.get("file_info"):
                generated_files.append(result["file_info"])
                final_output_type = service.output_type or "FILE"

        except Exception as e:
            logger.error(f"Service {service.service_name} failed: {e}")
            service_results.append({
                "service_name": service.service_name,
                "service_type": service.service_type,
                "success": False,
                "result": None,
                "error_message": str(e),
            })

    if not generated_files and final_output_type == "TEXT":
        pass  # keep TEXT

    return {
        "success": True,
        "output_type": final_output_type,
        "service_results": service_results,
        "generated_files": generated_files,
    }


class FileGenerateRequest(BaseModel):
    llm_output: str
    user_id: Optional[int] = None
    chat_room_id: Optional[int] = None
    approved_services: Optional[List[ServiceItem]] = None


@app.post("/api/files/generate")
async def generate_file(request: FileGenerateRequest):
    """Generate a file (PDF/etc.) from LLM-processed output."""
    # Determine output type from approved_services
    has_pdf = any(
        s.service_name in ("PDFGenerationService", "DocumentStructuringAgent")
        for s in (request.approved_services or [])
    )

    if has_pdf:
        result = await execute_pdf_generation(
            service_name="PDFGenerationService",
            service_type="FILE_GENERATION",
            original_prompt=request.llm_output,
            context="",
            base_url=BASE_URL,
        )
        file_info = result.get("file_info")
        return {
            "success": True,
            "output_type": "FILE",
            "file_info": file_info,
        }

    # Default: return as text (no file generated)
    return {
        "success": True,
        "output_type": "TEXT",
        "file_info": None,
        "text_output": request.llm_output,
    }


@app.get("/api/services")
def list_services():
    """Return the list of available services for Dify workflow."""
    return AVAILABLE_SERVICES


@app.get("/health")
def health():
    return {"status": "ok"}
