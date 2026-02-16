"""Data models for MCP persistent shell server."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class CommandResult(BaseModel):
    """Result of a shell command execution."""

    status: Literal["success", "error"]
    exit_code: int
    stdout: str
    stderr: str
    command: str
    execution_time: float  # seconds
    security_info: dict[str, bool | str] | None = None


class FileUploadRequest(BaseModel):
    """Request to upload a file to the workspace."""

    path: str = Field(..., description="Path to the file in workspace")
    content: str = Field(..., description="File content (base64 or utf8)")
    encoding: Literal["base64", "utf8"] = Field(default="base64", description="Content encoding")


class FileUploadResponse(BaseModel):
    """Response after uploading a file."""

    status: Literal["uploaded"]
    path: str
    size: int


class FileDownloadRequest(BaseModel):
    """Request to download a file from the workspace."""

    path: str = Field(..., description="Path to the file in workspace")
    encoding: Literal["base64", "utf8"] = Field(default="base64", description="Content encoding")


class FileDownloadResponse(BaseModel):
    """Response with file content."""

    content: str
    size: int
    encoding: Literal["base64", "utf8"]


class WorkingDirectoryResponse(BaseModel):
    """Response with current working directory."""

    cwd: str


class ResetSessionResponse(BaseModel):
    """Response after resetting shell session."""

    status: Literal["reset"]
    message: str
