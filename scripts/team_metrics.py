#!/usr/bin/env python
"""Mesures de l'équipe d'agents, calculées sur les transcripts de Claude Code (bibliothèque standard seule).

    team_metrics.py report [--since AAAA-MM-JJ] [--session ID]   Markdown de 80 lignes au plus
    team_metrics.py run AGENT_ID                                 un run : statistiques, brief, compte rendu
    team_metrics.py json [--since AAAA-MM-JJ] [--session ID]     toutes les données, run par run
    team_metrics.py check-owners                                 valide .claude/ownership.json

Options globales (avant la commande) : --root <dépôt>, --transcripts <dossier des transcripts du projet>.

Sources : ~/.claude/projects/<slug>/<session>.jsonl (fil principal) et <session>/subagents/agent-<id>.jsonl.
Un même message d'API occupe plusieurs lignes (une par bloc de contenu), avec la même usage : tokens et tours se
comptent une fois par message.id (maximum par champ : output_tokens grandit pendant le flux), appels et erreurs
d'outil une fois par tool_use.id. Seules les lignes de type assistant et user sont des messages ; les copies
api-request-blob sont ignorées. Dates en UTC.

Limite connue : seules les éditions Edit, Write et NotebookEdit sont vues ; ce que PowerShell ou Bash modifie ne l'est
pas. Les fichiers hors du dépôt (scratchpad, mémoire de Claude) sont listés mais jamais jugés.
"""

import argparse
import json
import os
import posixpath
import re
import statistics
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
TOKEN_FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
AGENT_TOOLS = ("Agent", "Task")  # Task : ancien nom de l'outil Agent
EDIT_TOOLS = ("Edit", "Write", "NotebookEdit")
DIRECT_TOOLS = ("Edit", "Write", "PowerShell", "Bash")  # le travail que l'orchestrateur devrait déléguer
# Rubriques d'un brief, cherchées dans le texte sans accents ni majuscules
RUBRICS = {
    "objectif": r"\bobjectifs?\b",
    "contexte": r"\bcontexte\b",
    "périmètre": r"\bperimetres?\b",
    "critère de fin": r"\bcriteres?\s+de\s+fin\b",
    "compte rendu": r"\bcomptes?[\s-]*rendus?\b",
}
AGENT_ID = re.compile(r"agentId:\s*([0-9a-f]{8,})")
MAX_TEXT = 3000
MASK = "[masqué]"
# Secrets cités dans un brief, un compte rendu ou une description : JWT, Bearer, clés sk-…, valeurs de --password,
# password=, token=, secret=, api_key=
SECRET_KEYS = r"(?:password|passwd|token|secret|api[_-]?key)"
SECRET_PATTERNS = (
    (re.compile(r"\beyJ[\w-]*\.[\w-]*\.[\w-]*"), MASK),
    (re.compile(r"\bBearer\s+\S+", re.IGNORECASE), f"Bearer {MASK}"),
    (re.compile(r"\bsk-[\w-]{8,}"), MASK),
    (re.compile(rf"(--{SECRET_KEYS}(?:=|\s+)|\b{SECRET_KEYS}=)\S+", re.IGNORECASE), r"\g<1>" + MASK),
)
MAX_ROWS, MAX_WARNINGS, MAX_ANOMALIES = 25, 5, 10  # bornent le rapport à 80 lignes


@dataclass
class Scan:
    """Ce qu'un transcript apporte, dédoublonné."""

    first: str = ""
    last: str = ""
    bad: int = 0  # lignes JSON invalides, ignorées
    model: str = ""
    effort: str = ""
    usage: dict = field(default_factory=dict)  # message.id -> maximum par champ de tokens
    tools: dict = field(default_factory=dict)  # tool_use.id -> (nom, horodatage, entrée utile)
    errors: set = field(default_factory=set)  # tool_use.id dont le résultat est en erreur
    launched: dict = field(default_factory=dict)  # agentId -> tool_use.id de l'appel Agent qui l'a lancé
    handback: str = ""  # message du dernier SubagentHandback (compte rendu rendu à l'appelant)
    tail: dict = field(default_factory=dict)  # dernier bloc de contenu de l'assistant


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b["text"] for b in content if isinstance(b, dict) and isinstance(b.get("text"), str))
    return ""


def scan(path):
    """Lit un transcript en flux, sans le garder en mémoire."""
    s = Scan()
    with open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            try:
                o = json.loads(raw)
            except ValueError:
                s.bad += bool(raw.strip())
                continue
            if not isinstance(o, dict):
                continue
            ts = o.get("timestamp")
            if isinstance(ts, str) and ts:
                s.first = min(s.first or ts, ts)
                s.last = max(s.last, ts)
            msg, kind = o.get("message"), o.get("type")
            if kind not in ("assistant", "user") or not isinstance(msg, dict):
                continue
            content = msg.get("content")
            blocks = [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []
            if kind == "assistant":
                if msg.get("id") and isinstance(msg.get("usage"), dict):
                    cur = s.usage.setdefault(msg["id"], dict.fromkeys(TOKEN_FIELDS, 0))
                    for k in TOKEN_FIELDS:
                        cur[k] = max(cur[k], msg["usage"].get(k) or 0)
                model = msg.get("model") or o.get("requestedModel") or ""
                if not s.model and not model.startswith("<"):  # "<synthetic>" : message du harnais
                    s.model = model
                s.effort = s.effort or str(o.get("effort") or "")
                for b in blocks:
                    tid = b.get("id")
                    if b.get("type") != "tool_use" or not tid or tid in s.tools:
                        continue
                    name = b.get("name")
                    inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                    if name in AGENT_TOOLS:
                        keep = inp
                    elif name in EDIT_TOOLS:
                        keep = {"path": inp.get("file_path") or inp.get("notebook_path") or ""}
                    else:
                        keep = {}
                    s.tools[tid] = (name, ts, keep)
                    if name == "SubagentHandback":
                        s.handback = str(inp.get("message") or "")
                if blocks:
                    s.tail = blocks[-1]
            else:
                for b in blocks:
                    if b.get("type") != "tool_result":
                        continue
                    tid = b.get("tool_use_id")
                    if b.get("is_error"):
                        s.errors.add(tid)
                    tool = s.tools.get(tid)
                    if tool and tool[0] in AGENT_TOOLS:
                        m = AGENT_ID.search(text_of(b.get("content")))
                        if m:
                            s.launched[m.group(1)] = tid
    return s


def read(path, warnings):
    try:
        return scan(path)
    except OSError as e:
        warnings.append(f"{path.name} illisible ({e.strerror})")
        return Scan()


def read_meta(transcript):
    try:
        data = json.loads(transcript.with_name(transcript.stem + ".meta.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def find_project_dir(root):
    """Dossier des transcripts du projet : le chemin du dépôt dont tout caractère non alphanumérique devient « - »."""
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(root))
    if (base / slug).is_dir():
        return base / slug
    if base.is_dir():  # la casse de la lettre de lecteur varie (c: / C:)
        return next((d for d in base.iterdir() if d.is_dir() and d.name.lower() == slug.lower()), None)
    return None


# --- propriété des fichiers -------------------------------------------------------------------------------------


def read_ownership(root):
    """(carte, erreurs) : .claude/ownership.json lu et vérifié dans sa forme."""
    path = root / ".claude" / "ownership.json"
    if not path.is_file():
        return None, [".claude/ownership.json absent"]
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        return None, [f"JSON illisible : {e}"]
    errors = []
    if not isinstance(data, dict):
        return None, ["la racine doit être un objet"]
    if data.get("version") != 1:
        errors.append("version attendue : 1")
    agents, shared = data.get("agents"), data.get("shared", [])

    def patterns_ok(value):
        return isinstance(value, list) and all(isinstance(p, str) and p.strip("!") for p in value)

    if not isinstance(agents, dict):
        errors.append("« agents » doit être un objet {agent: [motifs]}")
    else:
        errors += [f"agents.{name} : liste de motifs attendue" for name, v in agents.items() if not patterns_ok(v)]
    if not patterns_ok(shared):
        errors.append("« shared » doit être une liste de motifs")
    return (None if errors else {"agents": agents, "shared": shared}), errors


def load_ownership(root):
    own, errors = read_ownership(root)
    if own is None:
        return None, [f"{errors[0]} : périmètre non analysé" + (f" (+{len(errors) - 1} erreurs)" if len(errors) > 1 else "")]
    return own, []


def agent_names(root):
    """Noms des agents de .claude/agents/*.md (champ « name » du début de fichier, sinon nom du fichier)."""
    names = []
    for f in sorted((root / ".claude" / "agents").glob("*.md")):
        head = re.match(r"---\s*\n(.*?)\n---", f.read_text(encoding="utf-8-sig", errors="replace"), re.S)
        name = re.search(r"^name:\s*(\S+)", head.group(1), re.M) if head else None
        names.append(name.group(1).strip("'\"") if name else f.stem)
    return names


def check_owners(root):
    """Liste des problèmes de la carte de propriété (vide : tout est cohérent)."""
    own, errors = read_ownership(root)
    if own is None:
        return errors
    known = agent_names(root)
    errors += [f"agent sans entrée : {n}" for n in known if n not in own["agents"]]
    errors += [f"entrée inconnue (aucun .claude/agents/{n}.md) : {n}" for n in own["agents"] if n not in known]
    return errors


def relpath(path, root):
    """Chemin ramené à la racine du dépôt, avec des « / » ; None s'il est hors du dépôt."""
    p, r = path.replace("\\", "/"), str(root).replace("\\", "/").rstrip("/")
    if not re.match(r"([A-Za-z]:)?/", p):  # chemin relatif : relatif à la racine
        p = f"{r}/{p}"
    p = posixpath.normpath(p)
    return p[len(r) + 1 :] if p.lower().startswith(r.lower() + "/") else None


def matches(patterns, rel):
    """Un motif positif correspond et aucun motif « !exclusion » ne correspond (PurePosixPath.full_match, Python 3.13+)."""
    pure = PurePosixPath(rel)
    hit = [pure.full_match(p.lstrip("!"), case_sensitive=False) for p in patterns]
    return any(h for h, p in zip(hit, patterns, strict=True) if not p.startswith("!")) and not any(
        h for h, p in zip(hit, patterns, strict=True) if p.startswith("!")
    )


def allowed(rel, agent, own):
    """Permis par un motif de l'agent ou par « shared » ; un agent sans entrée n'a droit à rien."""
    return agent in own["agents"] and (matches(own["agents"][agent], rel) or matches(own["shared"], rel))


# --- collecte ---------------------------------------------------------------------------------------------------


def fold(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).casefold()


def rubrics(text):
    folded = fold(text)
    return [name for name, pattern in RUBRICS.items() if re.search(pattern, folded)]


def seconds(start, end):
    try:
        return max(0.0, (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds())
    except ValueError:
        return 0.0


def in_period(ts, since):
    return not since or bool(ts and ts[:10] >= since)


def final_report(s):
    if s.handback:
        return s.handback
    return str(s.tail.get("text") or "") if s.tail.get("type") == "text" else ""


def make_run(sid, aid, s, call, meta, root, own):
    tokens = {k: sum(u[k] for u in s.usage.values()) for k in TOKEN_FIELDS}
    paths = [t[2]["path"] for t in s.tools.values() if t[0] in EDIT_TOOLS and t[2]["path"]]
    inp = call[2] if call and call[0] in AGENT_TOOLS else {}
    agent = inp.get("subagent_type") or meta.get("agentType") or "inconnu"
    out_calls, out_files, outside = 0, [], set()
    for p in paths:
        rel = relpath(p, root)
        if rel is None:
            outside.add(portable(p))
        elif own is not None and not allowed(rel, agent, own):
            out_calls += 1
            out_files.append(rel)
    brief = inp.get("prompt") if isinstance(inp.get("prompt"), str) else None
    return {
        "agent_id": aid,
        "session": sid,
        "agent": agent,
        "description": mask(inp.get("description") or meta.get("description") or ""),
        "model": s.model,
        "effort": s.effort,
        "start": s.first,
        "end": s.last,
        "duration_s": seconds(s.first, s.last),
        "turns": len(s.usage),
        "tool_calls": dict(Counter(t[0] for t in s.tools.values())),
        "tool_calls_total": len(s.tools),
        "tool_errors": len(s.errors),
        "tokens": {
            "input": tokens["input_tokens"],
            "cache_creation": tokens["cache_creation_input_tokens"],
            "cache_read": tokens["cache_read_input_tokens"],
            "output": tokens["output_tokens"],
            "new": tokens["input_tokens"] + tokens["cache_creation_input_tokens"] + tokens["output_tokens"],
            "total": sum(tokens.values()),
        },
        "edits": len(paths),
        "out_of_scope_edits": None if own is None else out_calls,
        "out_of_scope_files": None if own is None else sorted(set(out_files)),
        "outside_repo_files": sorted(outside),
        "brief_chars": None if brief is None else len(brief),
        "brief_rubrics": None if brief is None else rubrics(brief),
        "report_chars": len(final_report(s)),
        "brief": brief,
        "report": final_report(s),
    }


def collect(project, root, since=None, session=None):
    """Lit les transcripts du projet : runs de sous-agents, fil principal, briefs, avertissements."""
    own, warnings = load_ownership(root)
    runs, briefs, stamps, active = [], [], [], set()
    main_calls, main_paths, bad = Counter(), [], 0
    sids = sorted({p.stem for p in project.glob("*.jsonl")} | {p.parent.name for p in project.glob("*/subagents")})
    for sid in sids:
        if session and not sid.startswith(session):
            continue
        main_file = project / f"{sid}.jsonl"
        main = read(main_file, warnings) if main_file.is_file() else Scan()
        subs = {}
        for f in sorted((project / sid / "subagents").rglob("agent-*.jsonl")):
            subs[f.stem[len("agent-") :]] = (f, read(f, warnings))
        scans = [main, *(s for _, s in subs.values())]
        bad += sum(s.bad for s in scans)
        tools = {tid: t for s in scans for tid, t in s.tools.items()}
        launched = {aid: tid for s in scans for aid, tid in s.launched.items()}
        for name, ts, inp in tools.values():  # les briefs : un par appel Agent, lancé ou non
            if name in AGENT_TOOLS and in_period(ts, since):
                text = inp.get("prompt") if isinstance(inp.get("prompt"), str) else ""
                briefs.append({"agent": inp.get("subagent_type") or "inconnu", "chars": len(text), "rubrics": rubrics(text)})
                stamps.append(ts)
                active.add(sid)
        for name, ts, inp in main.tools.values():
            if in_period(ts, since):
                main_calls[name] += 1
                main_paths += [inp["path"]] if name in EDIT_TOOLS and inp["path"] else []
                stamps.append(ts)
                active.add(sid)
        for aid, (f, s) in subs.items():
            if not in_period(s.first, since):
                continue
            meta = read_meta(f)
            runs.append(make_run(sid, aid, s, tools.get(launched.get(aid) or meta.get("toolUseId")), meta, root, own))
            stamps += [s.first, s.last]
            active.add(sid)
    stamps = [t for t in stamps if t]
    if bad:
        warnings.append(f"{bad} ligne(s) JSON invalide(s) ignorée(s)")
    if unknown := [r["agent_id"] for r in runs if r["agent"] == "inconnu"]:
        warnings.append(f"{len(unknown)} run(s) sans type d'agent identifié : {', '.join(unknown[:3])}")
    if own is not None:
        nameless = sorted({r["agent"] for r in runs if r["edits"] and r["agent"] not in own["agents"]})
        if nameless:
            warnings.append(f"agents sans entrée dans ownership.json (toute édition est hors périmètre) : {', '.join(nameless)}")
    inside = sorted({p for p in main_paths if relpath(p, root)} | {p.replace("\\", "/") for p in main_paths if not relpath(p, root)})
    return {
        "since": since,
        "session": session,
        "period": [min(stamps, default=""), max(stamps, default="")],
        "sessions": len(active),
        "warnings": warnings,
        "runs": sorted(runs, key=lambda r: r["start"]),
        "briefs": briefs,
        "main": {"tool_calls": dict(main_calls.most_common()), "edits": len(main_paths), "edit_files": len(inside)},
    }


# --- agrégats ---------------------------------------------------------------------------------------------------


def by_type(runs):
    groups = {}
    for r in runs:
        groups.setdefault(r["agent"], []).append(r)
    rows = []
    for name, rs in groups.items():
        per_session = Counter(r["session"] for r in rs)
        scoped = [r["out_of_scope_edits"] for r in rs]
        rows.append(
            {
                "agent": name,
                "runs": len(rs),
                "avg_duration_s": sum(r["duration_s"] for r in rs) / len(rs),
                "new_tokens": sum(r["tokens"]["new"] for r in rs),
                "cache_read": sum(r["tokens"]["cache_read"] for r in rs),
                "tool_errors": sum(r["tool_errors"] for r in rs),
                "out_of_scope_edits": None if None in scoped else sum(scoped),
                "relaunches": sum(n - 1 for n in per_session.values()),  # lancé de nouveau dans la même session
            }
        )
    return sorted(rows, key=lambda x: (-x["new_tokens"], x["agent"]))


def anomalies(runs):
    """[(run, [raisons])], les plus graves d'abord : hors périmètre, erreurs, durée, tokens, brief."""
    ref = {}
    for name in {r["agent"] for r in runs}:
        rs = [r for r in runs if r["agent"] == name]
        ref[name] = (
            statistics.median(r["duration_s"] for r in rs),
            statistics.median(r["tokens"]["new"] for r in rs),
        )
    found = []
    for r in runs:
        why, (med_d, med_t) = [], ref[r["agent"]]
        if r["out_of_scope_files"]:
            files = r["out_of_scope_files"]
            why.append((0, "fichier hors périmètre : " + ", ".join(files[:2]) + (f" (+{len(files) - 2})" if len(files) > 2 else "")))
        if r["tool_errors"] >= 5:
            why.append((1, f"{r['tool_errors']} erreurs d'outil"))
        if med_d > 0 and r["duration_s"] > 3 * med_d:
            why.append((2, f"durée {dur(r['duration_s'])} > 3 x médiane ({dur(med_d)})"))
        if med_t > 0 and r["tokens"]["new"] > 3 * med_t:
            why.append((3, f"tokens neufs {tok(r['tokens']['new'])} > 3 x médiane ({tok(med_t)})"))
        if r["brief_rubrics"] is not None and not {"périmètre", "critère de fin"} & set(r["brief_rubrics"]):
            why.append((4, "brief sans périmètre ni critère de fin"))
        if why:
            found.append((min(w[0] for w in why), -len(why), r, [w[1] for w in why]))
    return [(r, reasons) for _, _, r, reasons in sorted(found, key=lambda x: x[:2])]


# --- sorties ----------------------------------------------------------------------------------------------------


def num(n):
    return f"{n:,}".replace(",", " ")


def tok(n):
    if n >= 1_000_000:
        return f"{n / 1e6:.2f} M".replace(".", ",")
    return f"{n / 1e3:.1f} k".replace(".", ",") if n >= 1000 else str(n)


def dur(s):
    h, rest = divmod(round(s), 3600)
    m, sec = divmod(rest, 60)
    return f"{h} h {m:02d} min" if h else f"{m} min {sec:02d} s" if m else f"{sec} s"


def mask(text):
    """Texte où les secrets reconnus (SECRET_PATTERNS) sont remplacés par [masqué]."""
    for pattern, repl in SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def portable(path):
    """Chemin hors dépôt sans le profil Windows (C:/Users/<nom> devient ~), secrets masqués."""
    return mask(re.sub(r"^[A-Za-z]:/Users/[^/]+", "~", path.replace("\\", "/"), flags=re.I))


def clip(text):
    text = mask(text)  # avant la troncature : un secret coupé en deux resterait lisible
    return text if len(text) <= MAX_TEXT else f"{text[:MAX_TEXT]}\n[... tronqué : {num(len(text))} caractères au total]"


def render_report(data):
    runs, rows, found, main, briefs = data["runs"], by_type(data["runs"]), anomalies(data["runs"]), data["main"], data["briefs"]
    lo, hi = data["period"]
    filters = " ".join(f"{k} {v}" for k, v in (("--since", data["since"]), ("--session", data["session"])) if v)
    calls, warnings = main["tool_calls"], data["warnings"]
    out = ["# Mesures de l'équipe d'agents", ""]
    out.append(f"- Période : {lo[:10] or '-'} au {hi[:10] or '-'} (UTC)" + (f" ; filtres : {filters}" if filters else ""))
    out.append(f"- Sessions : {data['sessions']} ; runs de sous-agents : {len(runs)} ; appels d'outil du fil principal : {num(sum(calls.values()))}")
    out.append("- Avertissements : " + ("aucun" if not warnings else ""))
    out += [f"  - {w}" for w in warnings[:MAX_WARNINGS]]
    out += [f"  - (+{len(warnings) - MAX_WARNINGS} autres)"] * (len(warnings) > MAX_WARNINGS)

    out += ["", "## Par type d'agent", ""]
    if rows:
        out += [
            "| Agent | Runs | Durée moy. | Tokens neufs | Moy./run | Cache relus | Err. outil | Hors périm. | Relances |",
            "|---|--:|--:|--:|--:|--:|--:|--:|--:|",
        ]
        for r in rows[:MAX_ROWS]:
            scope = "n/d" if r["out_of_scope_edits"] is None else r["out_of_scope_edits"]
            out.append(
                f"| {r['agent']} | {r['runs']} | {dur(r['avg_duration_s'])} | {tok(r['new_tokens'])} | {tok(r['new_tokens'] // r['runs'])} "
                f"| {tok(r['cache_read'])} | {r['tool_errors']} | {scope} | {r['relaunches']} |"
            )
        out += [f"| (+{len(rows) - MAX_ROWS} autres types : voir `json`) | | | | | | | | |"] * (len(rows) > MAX_ROWS)
    else:
        out.append("(aucun run sur la période)")
    out += [
        "",
        "Tokens neufs = input + cache_creation + output, dédoublonnés par message.id ; cache relus = cache_read. Hors périm. = appels",
        "Edit/Write/NotebookEdit hors des motifs de l'agent et de `shared` (n/d : .claude/ownership.json absent ou invalide) ;",
        "relances = runs au-delà du premier d'un même agent dans une session. Limite : les modifications faites par PowerShell ou",
        "Bash ne sont pas vues ; les fichiers hors dépôt (scratchpad, mémoire) ne sont pas jugés.",
    ]

    direct = sum(calls.get(t, 0) for t in DIRECT_TOOLS)
    total = sum(calls.values())
    out += ["", "## Fil principal", ""]
    out.append("- Appels d'outil : " + (", ".join(f"{k} {v}" for k, v in list(calls.items())[:10]) or "aucun"))
    out.append(
        f"- Travail fait directement ({' + '.join(DIRECT_TOOLS)}) : {direct} appels sur {total} ({round(100 * direct / total) if total else 0} %),"
        f" contre {sum(calls.get(t, 0) for t in AGENT_TOOLS)} délégations (Agent)"
    )
    out.append(f"- Éditions du fil principal : {main['edits']} appels sur {main['edit_files']} fichiers (l'orchestrateur ne devrait pas éditer)")

    out += ["", "## Briefs", ""]
    if briefs:
        full = sum(len(b["rubrics"]) == len(RUBRICS) for b in briefs)
        out.append(
            f"- {len(briefs)} briefs ; longueur moyenne {num(round(sum(b['chars'] for b in briefs) / len(briefs)))} caractères ;"
            f" {round(100 * full / len(briefs))} % avec les cinq rubriques ({', '.join(RUBRICS)})"
        )
        out.append("- Présence par rubrique : " + ", ".join(f"{k} {sum(k in b['rubrics'] for b in briefs)}/{len(briefs)}" for k in RUBRICS))
    else:
        out.append("(aucun brief sur la période)")

    out += ["", f"## Anomalies ({min(len(found), MAX_ANOMALIES)} sur {len(found)})", ""]
    out += [f"- `{r['agent_id']}` ({r['agent']}) : {' ; '.join(why)}" for r, why in found[:MAX_ANOMALIES]]
    out += ["(aucune)"] * (not found)
    return "\n".join(out)


def render_run(r):
    t = r["tokens"]
    scope = r["out_of_scope_files"]
    tools = ", ".join(f"{k} {v}" for k, v in sorted(r["tool_calls"].items(), key=lambda kv: -kv[1]))
    out = [
        f"# Run {r['agent_id']} ({r['agent']})",
        "",
        f"- Session {r['session']} ; modèle {r['model'] or '?'} ; effort {r['effort'] or '?'} ; {r['description']}",
        f"- De {r['start']} à {r['end']} (UTC) : {dur(r['duration_s'])}",
        f"- {r['turns']} tours ; {r['tool_calls_total']} appels d'outil uniques ({tools or 'aucun'}) ; {r['tool_errors']} erreurs d'outil",
        f"- Tokens neufs {num(t['new'])} (input {num(t['input'])}, cache_creation {num(t['cache_creation'])}, output {num(t['output'])})"
        f" ; cache relus {num(t['cache_read'])} ; total {num(t['total'])}",
        f"- Éditions : {r['edits']} ; hors périmètre : {'n/d' if scope is None else r['out_of_scope_edits']}"
        f" ; fichiers hors dépôt : {len(r['outside_repo_files'])}",
        f"- Brief : {'introuvable' if r['brief'] is None else num(r['brief_chars']) + ' caractères'}"
        f" ; rubriques présentes : {', '.join(r['brief_rubrics'] or []) or 'aucune'}",
        "",
        "## Brief",
        "",
        clip(r["brief"]) if r["brief"] else "(introuvable dans les transcripts)",
        "",
        "## Compte rendu final",
        "",
        clip(r["report"]) if r["report"] else "(aucun : run en cours ou interrompu)",
        "",
        "## Fichiers hors périmètre",
        "",
    ]
    if scope is None:
        out.append("(non analysé : .claude/ownership.json absent ou invalide)")
    else:
        out += [f"- {p}" for p in scope] or ["(aucun)"]
    return "\n".join(out)


def as_json(data):
    runs = [{k: v for k, v in r.items() if k not in ("brief", "report")} for r in data["runs"]]
    found = [{"agent_id": r["agent_id"], "agent": r["agent"], "reasons": why} for r, why in anomalies(data["runs"])]
    return json.dumps({**data, "runs": runs, "types": by_type(data["runs"]), "anomalies": found}, ensure_ascii=False, indent=1)


# --- ligne de commande ------------------------------------------------------------------------------------------


def date_arg(value):
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"date attendue : AAAA-MM-JJ (reçu {value!r})") from None
    return value


def build_parser():
    p = argparse.ArgumentParser(prog="team_metrics", description="Mesures de l'équipe d'agents (transcripts Claude Code).")
    p.add_argument("--root", type=Path, default=ROOT, help="racine du dépôt (défaut : celui du script)")
    p.add_argument("--transcripts", type=Path, help="dossier des transcripts du projet (défaut : déduit de la racine)")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, text in (("report", "rapport Markdown"), ("json", "toutes les données par run")):
        s = sub.add_parser(name, help=text)
        s.add_argument("--since", type=date_arg, help="à partir de cette date (UTC)")
        s.add_argument("--session", help="identifiant de session, ou son début")
    sub.add_parser("run", help="un run : statistiques, brief, compte rendu").add_argument("agent_id")
    sub.add_parser("check-owners", help="valide .claude/ownership.json contre .claude/agents/*.md")
    return p


def main(argv=None):
    if sys.version_info < (3, 13):  # PurePosixPath.full_match
        print(f"Python 3.13 ou plus requis (reçu {sys.version.split()[0]})", file=sys.stderr)
        return 2
    args = build_parser().parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    root = Path(os.path.abspath(args.root))
    if args.cmd == "check-owners":
        errors = check_owners(root)
        print("\n".join(f"KO : {e}" for e in errors) if errors else f"OK : {len(agent_names(root))} agents, carte cohérente")
        return 1 if errors else 0
    project = args.transcripts or find_project_dir(root)
    if project is None or not project.is_dir():
        print(f"Aucun dossier de transcripts trouvé pour {root} (voir --transcripts)", file=sys.stderr)
        return 2
    if args.cmd == "run":
        wanted = args.agent_id.removeprefix("agent-")
        found = [r for r in collect(project, root)["runs"] if r["agent_id"].startswith(wanted)]
        if len(found) != 1:
            print(f"{'Aucun run' if not found else 'Plusieurs runs'} pour {args.agent_id!r}" + "".join(f"\n- {r['agent_id']}" for r in found), file=sys.stderr)
            return 1
        print(render_run(found[0]))
        return 0
    data = collect(project, root, args.since, args.session)
    print(render_report(data) if args.cmd == "report" else as_json(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
