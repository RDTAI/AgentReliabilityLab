"""A deterministic virtual office with inspectable side effects."""

from __future__ import annotations

from copy import deepcopy
from inspect import signature
from typing import Any

from .faults import FaultPlan, injected_response


class VirtualOffice:
    """In-memory environment designed for reliable CI evaluation."""

    def __init__(
        self,
        files: dict[str, str] | None = None,
        contacts: dict[str, str] | None = None,
        fault_plan: FaultPlan | None = None,
    ) -> None:
        self.files = dict(files or {})
        self.contacts = dict(contacts or {})
        self.sent_emails: list[dict[str, Any]] = []
        self.drafts: list[dict[str, Any]] = []
        self.fault_plan = fault_plan or FaultPlan.none()
        self.call_counts: dict[str, int] = {}

    def call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        call_number = self.call_counts.get(tool, 0) + 1
        self.call_counts[tool] = call_number
        fault = self.fault_plan.for_call(tool, call_number)

        if fault and fault.kind not in {"false_timeout"}:
            return injected_response(fault.kind, fault.message)

        handler = getattr(self, f"_tool_{tool}", None)
        if handler is None:
            return {"ok": False, "error": "unknown_tool", "retryable": False}
        try:
            signature(handler).bind(**arguments)
        except TypeError as exc:
            return {
                "ok": False,
                "error": "invalid_arguments",
                "message": str(exc),
                "retryable": False,
            }
        result = handler(**arguments)

        # The side effect happened, but the caller sees a timeout. This catches
        # agents that retry non-idempotent operations without state verification.
        if fault and fault.kind == "false_timeout":
            return {"ok": False, "error": "timeout", "retryable": True}
        return result

    def _tool_search_files(self, query: str) -> dict[str, Any]:
        matches = sorted(path for path in self.files if query.lower() in path.lower())
        return {"ok": True, "result": matches}

    def _tool_read_file(self, path: str) -> dict[str, Any]:
        if path not in self.files:
            return {"ok": False, "error": "not_found", "retryable": False}
        return {"ok": True, "result": self.files[path]}

    def _tool_lookup_contact(self, name: str) -> dict[str, Any]:
        address = self.contacts.get(name)
        if address is None:
            return {"ok": False, "error": "contact_not_found", "retryable": False}
        return {"ok": True, "result": address}

    def _tool_send_email(
        self, recipient: str, subject: str, body: str, attachment: str | None = None
    ) -> dict[str, Any]:
        if attachment and attachment not in self.files:
            return {"ok": False, "error": "attachment_not_found", "retryable": False}
        message = {
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "attachment": attachment,
        }
        self.sent_emails.append(message)
        return {"ok": True, "result": {"message_id": f"mail-{len(self.sent_emails)}"}}

    def snapshot(self) -> dict[str, Any]:
        return {
            "files": deepcopy(self.files),
            "contacts": deepcopy(self.contacts),
            "sent_emails": deepcopy(self.sent_emails),
            "drafts": deepcopy(self.drafts),
            "call_counts": deepcopy(self.call_counts),
        }

    def _tool_create_draft(self, recipient: str, subject: str, body: str) -> dict[str, Any]:
        self.drafts.append({"recipient": recipient, "subject": subject, "body": body})
        return {"ok": True, "result": {"draft_id": f"draft-{len(self.drafts)}"}}
