from __future__ import annotations

from pathlib import Path
from typing import Any

from castdub.delivery import render_delivery
from castdub.jobs import get_episode_job
from castdub.mixing import prepare_mix_approval
from castdub.performance import SenseVoiceSubprocessProvider, analyse_episode_performance
from castdub.preflight import preflight_registered_job
from castdub.qc import complete_episode, run_delivery_qc
from castdub.runner import import_registered_draft
from castdub.synthesis import QwenMlxSubprocessProvider, synthesize_episode
from castdub.voices import prepare_voice_profile_approval


HUMAN_GATES = {
    "awaiting_role_approval": "approve-roles",
    "awaiting_translation_approval": "approve-translation",
    "awaiting_voice_profile_approval": "approve-voices",
    "synthesis_completed": "approve-takes",
    "voice_approved": "prepare-mix",
}


def _missing(*values: object) -> bool:
    return any(value is None for value in values)


def continue_episode(
    store_path: Path,
    job_id: str,
    *,
    library_root: Path | None = None,
    performance_python: Path | None = None,
    performance_model: Path | None = None,
    performance_revision: str | None = None,
    tts_python: Path | None = None,
    tts_model: Path | None = None,
    tts_revision: str | None = None,
) -> dict[str, Any]:
    actions: list[str] = []
    while True:
        job = get_episode_job(store_path, job_id)
        status = job["status"]
        if status == "ready_for_preflight":
            report = preflight_registered_job(store_path, job_id)
            if not report["ok"]:
                return {
                    "ok": False,
                    "status": status,
                    "actions": actions,
                    "failure": "preflight_failed",
                    "report": report,
                }
            actions.append("preflight")
            continue
        if status == "inputs_verified":
            import_registered_draft(store_path, job_id)
            actions.append("import-episode")
            continue
        if status == "translation_approved":
            if library_root is None:
                return _needs_configuration(status, actions, "--library-root")
            prepare_voice_profile_approval(store_path, job_id, library_root)
            actions.append("prepare-voices")
            continue
        if status == "voice_profiles_approved":
            if _missing(
                performance_python, performance_model, performance_revision
            ):
                return _needs_configuration(
                    status,
                    actions,
                    "--performance-python, --performance-model, --performance-revision",
                )
            provider = SenseVoiceSubprocessProvider(
                performance_python, performance_model, performance_revision
            )
            analyse_episode_performance(store_path, job_id, provider)
            actions.append("analyse-performance")
            continue
        if status == "performance_analysed":
            if _missing(tts_python, tts_model, tts_revision):
                return _needs_configuration(
                    status,
                    actions,
                    "--tts-python, --tts-model, --tts-revision",
                )
            provider = QwenMlxSubprocessProvider(tts_python, tts_model, tts_revision)
            result = synthesize_episode(store_path, job_id, provider)
            actions.append("synthesize")
            if not result["ok"]:
                return {
                    "ok": False,
                    "status": status,
                    "actions": actions,
                    "failure": "needs_text_adaptation",
                    "report": result,
                }
            continue
        if status == "mix_completed":
            render_delivery(store_path, job_id)
            actions.append("render-delivery")
            continue
        if status == "render_completed":
            result = run_delivery_qc(store_path, job_id)
            actions.append("run-qc")
            if not result["ok"]:
                return {
                    "ok": False,
                    "status": status,
                    "actions": actions,
                    "failure": "qc_failed",
                    "report": result,
                }
            continue
        if status == "qc_passed":
            complete_episode(store_path, job_id)
            actions.append("complete-episode")
            continue
        if status == "completed":
            return {
                "ok": True,
                "status": status,
                "actions": actions,
                "next_action": None,
            }
        if status == "voice_approved":
            prepared = prepare_mix_approval(store_path, job_id)
            actions.append("prepare-mix")
            return {
                "ok": True,
                "status": status,
                "actions": actions,
                "next_action": "render-mix",
                "approval_template": prepared["approval_template"],
            }
        if status in HUMAN_GATES:
            return {
                "ok": True,
                "status": status,
                "actions": actions,
                "next_action": HUMAN_GATES[status],
            }
        return {
            "ok": False,
            "status": status,
            "actions": actions,
            "failure": "unsupported_state",
        }


def _needs_configuration(
    status: str, actions: list[str], required: str
) -> dict[str, Any]:
    return {
        "ok": True,
        "status": status,
        "actions": actions,
        "next_action": "continue-episode",
        "required_configuration": required,
    }
