"""Split --agent-* flags from SLURM passthrough argv."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

KNOWN_AGENT_FLAGS = {
    "agent-profile",
    "agent-skills",
    "agent-output-dir",
    "agent-node-llm",
    "agent-launcher",
    "agent-hosts",
}

BOOLEAN_AGENT_FLAGS = {"agent-node-llm"}

PROFILES = frozenset({"tools-only", "node-assist", "job-assist"})


class AgentParseError(Exception):
    def __init__(self, message: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass
class AgentOptions:
    profile: str = "tools-only"
    skills: tuple[str, ...] = ()
    output_dir: str | None = None
    node_llm: bool = False
    launcher: str | None = None
    hosts: str | None = None


@dataclass
class ParsedArgv:
    command: str
    options: AgentOptions
    passthrough: list[str] = field(default_factory=list)


def _flag_name(token: str) -> str | None:
    if not token.startswith("--"):
        return None
    body = token[2:]
    name, _, _ = body.partition("=")
    return name


def parse_agent_argv(argv: Sequence[str]) -> ParsedArgv:
    if not argv:
        raise AgentParseError("usage: agent srun|sbatch|salloc|supervisor|report ...")
    command = argv[0]
    options = AgentOptions()
    passthrough: list[str] = []
    tokens = list(argv[1:])
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--":
            passthrough.extend(tokens[i:])
            break
        name = _flag_name(tok)
        if name is None or not name.startswith("agent-"):
            passthrough.extend(tokens[i:])
            break
        if name not in KNOWN_AGENT_FLAGS:
            raise AgentParseError(f"unrecognized agent flag: --{name}")
        if "=" in tok:
            value = tok.split("=", 1)[1]
            _assign(options, name, value, present=True)
            i += 1
            continue
        if name in BOOLEAN_AGENT_FLAGS:
            _assign(options, name, "1", present=True)
            i += 1
            continue
        if i + 1 >= len(tokens):
            raise AgentParseError(f"missing value for --{name}")
        _assign(options, name, tokens[i + 1], present=True)
        i += 2
    return ParsedArgv(command=command, options=options, passthrough=passthrough)


def _assign(options: AgentOptions, name: str, value: str, *, present: bool) -> None:
    if name == "agent-profile":
        options.profile = value
    elif name == "agent-skills":
        options.skills = tuple(s for s in value.split(",") if s)
    elif name == "agent-output-dir":
        options.output_dir = value
    elif name == "agent-node-llm":
        options.node_llm = present
    elif name == "agent-launcher":
        options.launcher = value
    elif name == "agent-hosts":
        options.hosts = value


def validate_profile(profile: str) -> str:
    if not profile:
        return "tools-only"
    if profile not in PROFILES:
        raise AgentParseError(f"unknown --agent-profile={profile}")
    return profile


def apply_profile_defaults(options: AgentOptions) -> AgentOptions:
    options.profile = validate_profile(options.profile or "tools-only")
    return options
