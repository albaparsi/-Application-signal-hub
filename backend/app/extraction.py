"""LLM-assisted extraction for the browser extension's save-preview form.

Runs server-side only — the API key never reaches the extension's
client-side code (see app/config.py). Always returns a usable result: if
no API key is configured, or the LLM call fails for any reason, we fall
back to the client-supplied JobPosting structured-data hints instead of
erroring, since a partially-filled form beats a broken one.
"""

from anthropic import Anthropic

from app.config import settings
from app.enums import ApplicationStatus
from app.schemas import ExtractionRequest, ExtractionResponse

MODEL = "claude-haiku-4-5-20251001"

TOOL_SCHEMA = {
    "name": "extract_application_fields",
    "description": "Record the extracted job application details.",
    "input_schema": {
        "type": "object",
        "properties": {
            "company": {
                "type": "string",
                "description": "The hiring company's name. Never the job board/site itself "
                "(e.g. on a LinkedIn, Indeed, or Greenhouse page, that site's own name is NOT the company).",
            },
            "role": {"type": "string", "description": "The job title being applied for."},
            "location": {
                "type": "string",
                "description": "Job location, e.g. 'San Francisco, CA' or 'Remote'. Empty string if unclear.",
            },
            "status": {
                "type": "string",
                "enum": [s.value for s in ApplicationStatus],
                "description": "'applied' ONLY if the page clearly shows an application was already "
                "submitted (e.g. 'Application submitted', 'You applied on...', a confirmation screen). "
                "Otherwise 'saved' — being on a job posting page is not evidence of having applied.",
            },
        },
        "required": ["company", "role", "location", "status"],
    },
}


def infer_application_fields(request: ExtractionRequest) -> ExtractionResponse:
    if settings.anthropic_api_key:
        llm_result = _call_llm(request)
        if llm_result is not None:
            return llm_result
    return _heuristic_fallback(request)


def _heuristic_fallback(request: ExtractionRequest) -> ExtractionResponse:
    hints = request.job_posting_hints or {}
    return ExtractionResponse(
        company=str(hints.get("company") or ""),
        role=str(hints.get("role") or request.title or ""),
        location=str(hints.get("location") or ""),
        status=ApplicationStatus.SAVED,
        method="heuristic",
    )


def _call_llm(request: ExtractionRequest) -> ExtractionResponse | None:
    prompt = (
        "Extract job application details from this page context so a job seeker can save it "
        "to their tracker with one click.\n\n"
        f"Page URL: {request.url}\n"
        f"Page title: {request.title}\n"
        f"Structured job-posting data found on the page (if any): {request.job_posting_hints or 'none'}\n\n"
        "Visible page text (truncated):\n---\n"
        f"{request.visible_text}\n---\n\n"
        "Call extract_application_fields with your best answer. If unsure about a field, use your "
        "best guess for company/role, an empty string for location, and 'saved' for status."
    )

    try:
        client = Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=MODEL,
            max_tokens=500,
            tools=[TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "extract_application_fields"},
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        # Network error, auth failure, rate limit, etc. — degrade to the
        # heuristic path rather than breaking the extension's save flow.
        return None

    tool_input = next(
        (block.input for block in response.content if getattr(block, "type", None) == "tool_use"),
        None,
    )
    if tool_input is None:
        return None

    try:
        return ExtractionResponse(**tool_input, method="llm")
    except Exception:
        return None
