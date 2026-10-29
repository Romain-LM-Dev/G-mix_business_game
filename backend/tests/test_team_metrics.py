"""Mesures de l'équipe (scripts/team_metrics.py) : dédoublonnage, périmètre, collecte sur un faux transcript."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("team_metrics", ROOT / "scripts" / "team_metrics.py")
tm = importlib.util.module_from_spec(_spec)
sys.modules["team_metrics"] = tm  # requis par dataclasses
_spec.loader.exec_module(tm)

BRIEF = "Objectif : corriger X\nContexte : docs\nPérimètre : moteur\nCritère de fin : tests verts\nCompte rendu : court"


def line(kind, ts, msg_id, blocks, usage=None):
    msg = {"id": msg_id, "model": "claude-test", "content": blocks}
    if usage is not None:
        msg["usage"] = usage
    return json.dumps({"type": kind, "timestamp": ts, "message": msg}) + "\n"


@pytest.mark.parametrize(
    ("agent", "rel", "allowed"),
    [
        ("moteur-jeu", "backend/gmix/game/engine.py", True),
        ("moteur-jeu", "godot/scenes/a.tscn", False),
        ("moteur-jeu", "backend/tests/test_engine.py", True),  # shared : backend/tests/**
        ("documentaliste", "docs/decisions/0001.md", False),  # exclu par « !docs/decisions/** »
        ("architecte", "docs/decisions/0001.md", True),
        ("inconnu", "docs/a.md", False),  # agent sans entrée : aucun droit
    ],
)
def test_allowed_respects_patterns_and_exclusions(tmp_path, agent, rel, allowed):
    own = {
        "agents": {
            "moteur-jeu": ["backend/gmix/game/**"],
            "documentaliste": ["docs/**", "!docs/decisions/**"],
            "architecte": ["docs/decisions/**"],
        },
        "shared": ["backend/tests/**"],
    }
    assert tm.allowed(rel, agent, own) is allowed


def test_relpath_maps_absolute_and_relative_paths(tmp_path):
    root = tmp_path / "repo"
    assert tm.relpath(str(root / "docs" / "a.md"), root) == "docs/a.md"
    assert tm.relpath("docs/a.md", root) == "docs/a.md"
    assert tm.relpath(str(tmp_path / "ailleurs.md"), root) is None


def test_collect_counts_each_message_once_and_flags_out_of_scope_edit(tmp_path):
    root = tmp_path / "repo"
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "ownership.json").write_text(
        json.dumps({"version": 1, "agents": {"moteur-jeu": ["backend/gmix/game/**"]}, "shared": []}), encoding="utf-8"
    )
    project = tmp_path / "projects" / "p"
    sub_dir = project / "sess" / "subagents"
    sub_dir.mkdir(parents=True)
    agent_call = [
        {
            "type": "tool_use",
            "id": "tu1",
            "name": "Agent",
            "input": {"subagent_type": "moteur-jeu", "description": "d", "prompt": BRIEF},
        }
    ]
    (project / "sess.jsonl").write_text(
        line("assistant", "2026-10-20T10:00:00Z", "m1", agent_call, {"input_tokens": 10, "output_tokens": 5})
        + json.dumps(
            {
                "type": "user",
                "timestamp": "2026-10-20T10:00:01Z",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tu1",
                            "content": [{"type": "text", "text": "agentId: abcdef123456\n"}],
                        }
                    ]
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    edit = {"type": "tool_use", "id": "su1", "name": "Edit", "input": {"file_path": str(root / "godot" / "a.tscn")}}
    sub = (
        line("assistant", "2026-10-20T10:00:02Z", "s1", [edit], {"input_tokens": 100, "output_tokens": 10})
        + line(
            "assistant",
            "2026-10-20T10:00:03Z",
            "s1",
            [{"type": "text", "text": "fini"}],
            {"input_tokens": 100, "output_tokens": 40},
        )
        + json.dumps(
            {
                "type": "user",
                "timestamp": "2026-10-20T10:00:04Z",
                "message": {
                    "content": [{"type": "tool_result", "tool_use_id": "su1", "is_error": True, "content": "refusé"}]
                },
            }
        )
        + "\n"
    )
    (sub_dir / "agent-abcdef123456.jsonl").write_text(sub, encoding="utf-8")

    data = tm.collect(project, root)

    (run,) = data["runs"]
    assert run["agent"] == "moteur-jeu"
    assert run["tokens"]["input"] == 100  # message s1 compté une fois
    assert run["tokens"]["output"] == 40  # maximum du flux
    assert run["edits"] == 1 and run["out_of_scope_edits"] == 1
    assert run["tool_errors"] == 1
    assert run["brief_rubrics"] == list(tm.RUBRICS)
    assert run["report"] == "fini"


# --- aucune fuite de secret ni de règle de permission ---------------------------------------------------------
SECRETS = ("sk-ant-api03-ABCDEF123456", "Bearer eyJhbGciOiJIUzI1NiJ9.payload.signature", "hunter2-motdepasse")
PERMISSIONS = 'permissions: {"allow": ["Bash(rm -rf *)"], "deny": ["Read(.env)"]}'


def _planted_project(tmp_path: Path) -> tuple[Path, Path]:
    """Transcript où le brief, le compte rendu et un résultat d'outil (lecture de settings.json) portent des secrets."""
    root = tmp_path / "repo"
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "ownership.json").write_text(
        json.dumps({"version": 1, "agents": {"devops": ["scripts/**"]}, "shared": []}), encoding="utf-8"
    )
    project = tmp_path / "projects" / "p"
    (project / "sess" / "subagents").mkdir(parents=True)
    brief = f"{BRIEF}\nCrée le compte avec --password {SECRETS[2]} et la clé {SECRETS[0]}."
    call = {"type": "tool_use", "id": "tu1", "name": "Agent", "input": {"subagent_type": "devops", "prompt": brief}}
    result = {
        "type": "tool_result",
        "tool_use_id": "tu1",
        "content": [{"type": "text", "text": "agentId: abc12345678"}],
    }
    (project / "sess.jsonl").write_text(
        line("assistant", "2026-10-20T10:00:00Z", "m1", [call], {"input_tokens": 1})
        + json.dumps({"type": "user", "timestamp": "2026-10-20T10:00:01Z", "message": {"content": [result]}})
        + "\n",
        encoding="utf-8",
    )
    read = {"type": "tool_use", "id": "su1", "name": "Read", "input": {"file_path": ".claude/settings.json"}}
    leak = {"type": "tool_result", "tool_use_id": "su1", "content": [{"type": "text", "text": PERMISSIONS}]}
    handback = {
        "type": "tool_use",
        "id": "su2",
        "name": "SubagentHandback",
        "input": {"message": f"Jeton {SECRETS[1]}"},
    }
    (project / "sess" / "subagents" / "agent-abc12345678.jsonl").write_text(
        line("assistant", "2026-10-20T10:00:02Z", "s1", [read], {"input_tokens": 5})
        + json.dumps({"type": "user", "timestamp": "2026-10-20T10:00:03Z", "message": {"content": [leak]}})
        + "\n"
        + line("assistant", "2026-10-20T10:00:04Z", "s2", [handback], {"input_tokens": 5}),
        encoding="utf-8",
    )
    return project, root


def test_report_and_json_never_carry_briefs_reports_secrets_or_permission_rules(tmp_path: Path) -> None:
    project, root = _planted_project(tmp_path)
    data = tm.collect(project, root)
    assert data["runs"][0]["report"].startswith("Jeton")  # le texte est bien lu en mémoire...
    for output in (tm.render_report(data), tm.as_json(data), json.dumps(data["briefs"]), json.dumps(data["main"])):
        for needle in (*SECRETS, "Bash(rm", "Read(.env)", "--password"):
            assert needle not in output  # ...mais ne sort ni dans le rapport ni dans le JSON


def test_run_view_masks_secrets_of_brief_and_report(tmp_path: Path) -> None:
    project, root = _planted_project(tmp_path)
    shown = tm.render_run(tm.collect(project, root)["runs"][0])
    assert not [needle for needle in SECRETS if needle in shown]
    assert tm.MASK in shown


@pytest.mark.parametrize(
    ("text", "secret"),
    [
        ("clé sk-ant-api03-ABCDEF123456 ici", "sk-ant-api03-ABCDEF123456"),
        ("Authorization: Bearer abc.def.ghi", "abc.def.ghi"),
        ("jeton eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig", "eyJhbGciOiJIUzI1NiJ9"),
        ("lancer --password hunter2 maintenant", "hunter2"),
        ("password=hunter2 token=abc123 secret=s3cr3t api_key=k3y", "hunter2"),
        ("token=abc123", "abc123"),
        ("secret=s3cr3t", "s3cr3t"),
        ("api_key=k3y", "k3y"),
    ],
)
def test_mask_hides_secret_values(text: str, secret: str) -> None:
    masked = tm.mask(text)
    assert secret not in masked and tm.MASK in masked


def test_mask_keeps_ordinary_prose() -> None:
    assert tm.mask("le token expire, la tâche task-42 part") == "le token expire, la tâche task-42 part"


def test_portable_replaces_windows_profile_only() -> None:
    assert tm.portable("C:\\Users\\Flash\\AppData\\Local\\Temp\\x.py") == "~/AppData/Local/Temp/x.py"
    assert tm.portable("D:/projets/a.py") == "D:/projets/a.py"
