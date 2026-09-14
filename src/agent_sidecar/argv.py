"""Split --agent-* flags from SLURM passthrough argv."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Sequence

KNOWN_AGENT_FLAGS = {
    "agent-profile",
    "agent-skills",
    "agent-output-dir",
    "agent-node-llm",
    "agent-launcher",
    "agent-hosts",
    "agent-verbose",
    "agent-quiet",
    "agent-llm-base-url",
    "agent-llm-model",
    "agent-match",
    "agent-interval",
    "agent-live-plot",
    "agent-no-live-plot",
}

BOOLEAN_AGENT_FLAGS = {
    "agent-node-llm",
    "agent-verbose",
    "agent-quiet",
    "agent-live-plot",
    "agent-no-live-plot",
}

PROFILES = frozenset({"tools-only", "node-assist", "job-assist"})
DEFAULT_SKILLS = ("proc-monitor", "mpi-scan", "slurm-tap", "node-diag", "eth-monitor")


class AgentParseError(Exception):
    def __init__(self, message: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass
class AgentOptions:
    profile: str = "job-assist"
    profile_explicit: bool = False
    skills: tuple[str, ...] = ()
    output_dir: str | None = None
    node_llm: bool = False
    verbose: bool = False
    quiet: bool = True
    launcher: str | None = None
    hosts: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    match: str | None = None
    interval: float = 1.0
    live_plot_cli: bool | None = None


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


def _take_agent_flag(tokens: list[str], i: int, options: AgentOptions) -> int:
    tok = tokens[i]
    name = _flag_name(tok)
    if name is None or not name.startswith("agent-"):
        return i
    if name not in KNOWN_AGENT_FLAGS:
        raise AgentParseError(f"unrecognized agent flag: --{name}")
    if "=" in tok:
        _assign(options, name, tok.split("=", 1)[1], present=True)
        return i + 1
    if name in BOOLEAN_AGENT_FLAGS:
        _assign(options, name, "1", present=True)
        return i + 1
    if i + 1 >= len(tokens):
        raise AgentParseError(f"missing value for --{name}")
    _assign(options, name, tokens[i + 1], present=True)
    return i + 2


def parse_agent_argv(argv: Sequence[str]) -> ParsedArgv:
    if not argv:
        raise AgentParseError(
            "usage: agent [--agent-*] srun|sbatch|salloc|supervisor|report|serve ..."
        )
    options = AgentOptions()
    tokens = list(argv)
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--":
            i += 1
            break
        name = _flag_name(tok)
        if name is None or not name.startswith("agent-"):
            break
        i = _take_agent_flag(tokens, i, options)
    if i >= len(tokens):
        raise AgentParseError(
            "usage: agent [--agent-*] srun|sbatch|salloc|supervisor|report|serve ..."
        )
    command = tokens[i]
    i += 1
    passthrough: list[str] = []
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--":
            passthrough.extend(tokens[i:])
            break
        name = _flag_name(tok)
        if name is None or not name.startswith("agent-"):
            passthrough.extend(tokens[i:])
            break
        i = _take_agent_flag(tokens, i, options)
    return ParsedArgv(command=command, options=options, passthrough=passthrough)


def _assign(options: AgentOptions, name: str, value: str, *, present: bool) -> None:
    if name == "agent-profile":
        options.profile = value
        options.profile_explicit = True
    elif name == "agent-skills":
        options.skills = tuple(s for s in value.split(",") if s)
    elif name == "agent-output-dir":
        options.output_dir = value
    elif name == "agent-node-llm":
        options.node_llm = present
    elif name == "agent-verbose":
        options.verbose = present
    elif name == "agent-quiet":
        options.quiet = present
    elif name == "agent-launcher":
        options.launcher = value
    elif name == "agent-hosts":
        options.hosts = value
    elif name == "agent-llm-base-url":
        options.llm_base_url = value
    elif name == "agent-llm-model":
        options.llm_model = value
    elif name == "agent-match":
        options.match = value
    elif name == "agent-interval":
        try:
            options.interval = float(value)
        except ValueError as exc:
            raise AgentParseError(f"invalid --agent-interval={value}") from exc
    elif name == "agent-live-plot":
        options.live_plot_cli = True
    elif name == "agent-no-live-plot":
        options.live_plot_cli = False


def validate_profile(profile: str) -> str:
    if not profile:
        return "job-assist"
    if profile not in PROFILES:
        raise AgentParseError(f"unknown --agent-profile={profile}")
    return profile


def apply_profile_defaults(
    options: AgentOptions, env: dict[str, str] | None = None
) -> AgentOptions:
    _ = env
    options.profile = validate_profile(options.profile or "job-assist")
    if not options.skills:
        options.skills = DEFAULT_SKILLS
    return options


def agent_quiet(options: AgentOptions | None = None, env: dict[str, str] | None = None) -> bool:
    env = env if env is not None else os.environ
    if options is not None and options.verbose:
        return False
    if (env.get("AGENT_VERBOSE") or "").strip() == "1":
        return False
    if (env.get("AGENT_QUIET") or "").strip() == "0":
        return False
    return True


def agent_live_plot(options: AgentOptions | None = None, env: dict[str, str] | None = None) -> bool:
    env = env if env is not None else os.environ
    if options is not None and options.live_plot_cli is True:
        return True
    if options is not None and options.live_plot_cli is False:
        return False
    if (env.get("AGENT_LIVE_PLOT") or "").strip() == "0":
        return False
    return True
