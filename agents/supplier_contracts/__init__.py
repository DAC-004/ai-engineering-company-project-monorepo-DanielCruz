"""Supplier and contract supervisor package."""

from __future__ import annotations

__all__ = [
    "ContractRuntime",
    "Supervisor",
    "SupervisorRequest",
    "SupervisorResponse",
    "handle",
]


def __getattr__(name: str):
    if name == "ContractRuntime":
        from agents.supplier_contracts.runtime import ContractRuntime

        return ContractRuntime
    if name in {"Supervisor", "handle"}:
        from agents.supplier_contracts.supervisor import Supervisor, handle

        return handle if name == "handle" else Supervisor
    if name in {"SupervisorRequest", "SupervisorResponse"}:
        from agents.supplier_contracts.types import SupervisorRequest, SupervisorResponse

        return SupervisorRequest if name == "SupervisorRequest" else SupervisorResponse
    raise AttributeError(name)
