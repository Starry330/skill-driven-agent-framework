"""Minimal deterministic checks for the static-structural-fea skill.

This script is a reference implementation for input validation. It is not tied to a
specific runtime; adapt the file-discovery and tool-call wrappers as needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SUPPORTED_EXTENSIONS = {".stp", ".step"}
REQUIRED_REPORT_KEYS = ["Products", "复杂度", "外接矩形", "主轴判定"]


@dataclass
class ValidationResult:
    ok: bool
    code: str | None = None
    message: str | None = None
    retryable: bool | None = None
    suggestion: str | None = None


ERRORS = {
    "MISSING_STP_FILE": {
        "message": "未检测到可用于静力学分析的 STP/STEP 文件。",
        "retryable": False,
        "suggestion": "请上传 .stp 或 .step 文件后重试。",
    },
    "UNSUPPORTED_FILE_TYPE": {
        "message": "输入文件不是受支持的 STEP/STP 格式。",
        "retryable": False,
        "suggestion": "请提供 .stp 或 .step 文件。",
    },
    "STP_ANALYZER_FAILED": {
        "message": "stp_analyzer 无法解析该模型。",
        "retryable": True,
        "suggestion": "请检查 STEP 导出版本，或简化模型后重新导出。",
    },
    "MULTIVIEW_RENDER_FAILED": {
        "message": "get_multiview 未返回可用视图。",
        "retryable": True,
        "suggestion": "请重新导出 STP 或检查模型几何完整性。",
    },
}


def error(code: str) -> ValidationResult:
    payload = ERRORS[code]
    return ValidationResult(ok=False, code=code, **payload)


def validate_step_file(file_path: str | Path | None) -> ValidationResult:
    if not file_path:
        return error("MISSING_STP_FILE")
    path = Path(file_path)
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return error("UNSUPPORTED_FILE_TYPE")
    if not path.exists() or not path.is_file():
        return error("MISSING_STP_FILE")
    return ValidationResult(ok=True)


def validate_analyzer_report(report_text: str) -> ValidationResult:
    if not report_text or not all(key in report_text for key in REQUIRED_REPORT_KEYS):
        return error("STP_ANALYZER_FAILED")
    return ValidationResult(ok=True)


def validate_multiview(images: Iterable[Any]) -> ValidationResult:
    images = list(images)
    if not images:
        return error("MULTIVIEW_RENDER_FAILED")
    return ValidationResult(ok=True)


if __name__ == "__main__":
    # Example usage
    import json
    import sys

    file_result = validate_step_file(sys.argv[1] if len(sys.argv) > 1 else None)
    print(json.dumps(file_result.__dict__, ensure_ascii=False, indent=2))
