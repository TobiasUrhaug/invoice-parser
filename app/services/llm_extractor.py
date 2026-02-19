import json
from pathlib import Path
from typing import Any, TypedDict, cast

from huggingface_hub import hf_hub_download
from llama_cpp import CreateChatCompletionResponse, Llama

_FIVE_KEYS = frozenset(
    {
        "invoiceDate",
        "invoiceReference",
        "netAmount",
        "vatAmount",
        "totalAmount",
    }
)

_SYSTEM_PROMPT = (
    "You are an invoice data extraction assistant. "
    "Extract the following fields from the invoice text provided "
    "and return ONLY a JSON object with exactly these five keys: "
    "invoiceDate, invoiceReference, netAmount, vatAmount, totalAmount. "
    "Rules:\n"
    "- invoiceDate: ISO 8601 date string (YYYY-MM-DD) or null\n"
    "- invoiceReference: invoice number/reference string or null\n"
    "- netAmount, vatAmount, totalAmount: object with 'amount' (number) "
    "and 'currency' (ISO 4217 code), or null\n"
    "- Set any field to null if it cannot be determined from the text\n"
    "- Handle invoices in any European language\n"
    "Return only the JSON object with no additional text."
)


class AmountField(TypedDict):
    amount: float
    currency: str


class InvoiceFields(TypedDict):
    invoiceDate: str | None
    invoiceReference: str | None
    netAmount: AmountField | None
    vatAmount: AmountField | None
    totalAmount: AmountField | None


def _extract_json_object(raw: str) -> str | None:
    """Return the first balanced {...} substring in raw, handling nested objects."""
    start = raw.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(raw)):
        ch = raw[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return raw[start : i + 1]
    return None


class LLMExtractor:
    def __init__(self, model: Llama) -> None:
        self._model = model

    def extract_fields(self, text: str) -> InvoiceFields:
        # NOTE: invoice text is interpolated directly into the user message.
        # Assumes input is trusted OCR/PDF text, not user-controlled. If input
        # is ever user-supplied or externally fetched, consider adding a
        # structural delimiter or input sanitisation.
        response = cast(
            CreateChatCompletionResponse,
            self._model.create_chat_completion(
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Extract invoice fields from:\n\n{text}",
                    },
                ],
                max_tokens=512,
                temperature=0,
            ),
        )
        choices = response["choices"]
        if not choices:
            return {
                "invoiceDate": None,
                "invoiceReference": None,
                "netAmount": None,
                "vatAmount": None,
                "totalAmount": None,
            }
        raw = str(choices[0]["message"]["content"] or "")
        return self._parse(raw)

    def _parse(self, raw: str) -> InvoiceFields:
        result: InvoiceFields = {
            "invoiceDate": None,
            "invoiceReference": None,
            "netAmount": None,
            "vatAmount": None,
            "totalAmount": None,
        }
        data: Any = None

        try:
            obj: Any = json.loads(raw)
            if isinstance(obj, dict):
                data = obj
        except json.JSONDecodeError:
            extracted = _extract_json_object(raw)
            if extracted:
                try:
                    obj = json.loads(extracted)
                    if isinstance(obj, dict):
                        data = obj
                except json.JSONDecodeError:
                    pass

        if data is not None:
            # Amount field values (netAmount, vatAmount, totalAmount) are stored as-is.
            # Validation that they conform to {"amount": number, "currency": string}
            # is intentionally deferred to the caller.
            result["invoiceDate"] = data.get("invoiceDate")
            result["invoiceReference"] = data.get("invoiceReference")
            result["netAmount"] = data.get("netAmount")
            result["vatAmount"] = data.get("vatAmount")
            result["totalAmount"] = data.get("totalAmount")

        return result


def init_model(
    model_dir: Path,
    repo_id: str,
    filename: str,
    n_ctx: int = 4096,
    n_gpu_layers: int = 0,
) -> Llama:
    model_path = model_dir / filename
    if not model_path.exists():
        downloaded = hf_hub_download(
            repo_id=repo_id, filename=filename, local_dir=model_dir
        )
        model_path = Path(downloaded)
    return Llama(
        model_path=str(model_path),
        n_ctx=n_ctx,
        n_gpu_layers=n_gpu_layers,
        verbose=False,
    )
