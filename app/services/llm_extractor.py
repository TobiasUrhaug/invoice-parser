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
    "Extract invoice fields. Return ONLY a JSON object "
    "with these five keys:\n"
    "- invoiceDate: ISO 8601 (YYYY-MM-DD) or null\n"
    "- invoiceReference: invoice number or null\n"
    "- netAmount: amount BEFORE tax (excl. VAT) or null\n"
    "- vatAmount: the tax/VAT amount only, or null\n"
    "- totalAmount: final amount AFTER tax (incl. VAT) or null\n"
    'Amount fields: {"amount": number, "currency": "XXX"}.\n'
    "Copy numbers exactly from the invoice. "
    "Do NOT add, subtract, or calculate anything."
)

_FEW_SHOT_INPUT = (
    "Invoice : VF25.194982\n"
    "Date : 27-06-25\n"
    "Qty Description Unit Price Amount in €\n"
    "1 Ontvangen voorschotten/advance 3.152,38 3.152,38\n"
    "Total Excl. VAT 3.152,38\n"
    "21% VAT 662,00\n"
    "Total Incl. VAT in € 3.814,38"
)

_FEW_SHOT_OUTPUT = (
    '{"invoiceDate":"2025-06-27",'
    '"invoiceReference":"VF25.194982",'
    '"netAmount":{"amount":3152.38,"currency":"EUR"},'
    '"vatAmount":{"amount":662.00,"currency":"EUR"},'
    '"totalAmount":{"amount":3814.38,"currency":"EUR"}}'
)

_FEW_SHOT_INPUT_2 = (
    "RECHNUNG\n"
    "ReNr.: DL2129376\n"
    "Datum: 18.05.2021\n"
    "9 items / € 58,50\n"
    "19% MwSt inkl.: € 9,34\n"
    "total: € 58,50"
)

_FEW_SHOT_OUTPUT_2 = (
    '{"invoiceDate":"2021-05-18",'
    '"invoiceReference":"DL2129376",'
    '"netAmount":null,'
    '"vatAmount":{"amount":9.34,"currency":"EUR"},'
    '"totalAmount":{"amount":58.50,"currency":"EUR"}}'
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


def _null_result() -> InvoiceFields:
    return {
        "invoiceDate": None,
        "invoiceReference": None,
        "netAmount": None,
        "vatAmount": None,
        "totalAmount": None,
    }


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
                        "content": f"Extract invoice fields from:\n\n{_FEW_SHOT_INPUT}",
                    },
                    {"role": "assistant", "content": _FEW_SHOT_OUTPUT},
                    {
                        "role": "user",
                        "content": (
                            f"Extract invoice fields from:\n\n{_FEW_SHOT_INPUT_2}"
                        ),
                    },
                    {
                        "role": "assistant",
                        "content": _FEW_SHOT_OUTPUT_2,
                    },
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
            return _null_result()
        raw = str(choices[0]["message"]["content"] or "")
        return self._parse(raw)

    def _parse(self, raw: str) -> InvoiceFields:
        result: InvoiceFields = _null_result()
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
