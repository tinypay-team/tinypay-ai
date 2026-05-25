async def execute_generic_service(service_name: str, service_type: str,
                                   original_prompt: str, context: str, base_url: str) -> dict:
    return {
        "success": True,
        "data": {
            "service": service_name,
            "type": service_type,
            "message": f"{service_name} executed successfully",
            "prompt_received": original_prompt[:100],
        }
    }
