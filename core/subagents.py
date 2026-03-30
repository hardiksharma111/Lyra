import json
import os
import re
import time
from datetime import datetime
from typing import Callable

TRACE_FILE = os.path.join("memory", "phase9_trace.jsonl")


class SubAgentOrchestrator:
    """Lightweight Phase 9 orchestrator for role-based multi-pass responses.

    This does not create new runtime environments. It runs logical sub-agents
    (research, writing, verifier) in the same Lyra backend process.
    """

    def __init__(self, llm_call: Callable, debug: bool = False):
        self.llm_call = llm_call
        self.debug = debug

    def set_debug(self, enabled: bool):
        self.debug = enabled

    def should_route(self, user_input: str) -> bool:
        text = (user_input or "").strip().lower()
        if not text:
            return False

        # Keep Phase 8 and explicit command paths untouched.
        blocked_prefixes = (
            "do task ", "record task ", "replay task ", "list tasks",
            "benchmark", "remind me", "set briefing", "approve ",
            "pending", "errors", "suggestions", "debug on", "debug off",
        )
        if text.startswith(blocked_prefixes):
            return False

        # Route only likely research/writing/comparison requests.
        trigger_keywords = (
            "research", "analyze", "compare", "deep dive", "break down",
            "summarize", "summary", "draft", "write", "plan",
        )
        return any(k in text for k in trigger_keywords)

    def run(self, user_input: str, memory_context: str, history: list[dict]) -> str | None:
        if not self.should_route(user_input):
            return None

        started = time.time()
        route = self._classify_route(user_input, memory_context, history)
        self._trace("route", user_input=user_input, route=route)

        if route == "writer_only":
            draft = self._writer_pass(user_input, memory_context, history, "")
            final = self._verifier_pass(user_input, draft, memory_context)
            self._trace("done", route=route, latency_ms=int((time.time() - started) * 1000))
            return final

        research = self._research_pass(user_input, memory_context, history)
        draft = self._writer_pass(user_input, memory_context, history, research)
        final = self._verifier_pass(user_input, draft, memory_context)
        self._trace("done", route=route, latency_ms=int((time.time() - started) * 1000))
        return final

    def _classify_route(self, user_input: str, memory_context: str, history: list[dict]) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "Classify the request into one route. "
                    "Return JSON only: {\"route\":\"research_writer_verifier\"|\"writer_only\"}. "
                    "Use writer_only for pure drafting/rewriting."
                )
            },
            {"role": "user", "content": user_input},
        ]
        raw = self.llm_call(messages, max_tokens=60, temperature=0.0)
        try:
            data = self._parse_json(raw)
            route = data.get("route", "research_writer_verifier")
            if route in {"research_writer_verifier", "writer_only"}:
                return route
        except Exception:
            pass
        return "research_writer_verifier"

    def _research_pass(self, user_input: str, memory_context: str, history: list[dict]) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are Research Agent. Extract key facts, assumptions, and unknowns. "
                    "No markdown. Keep concise and actionable."
                )
            },
        ]
        if memory_context:
            messages.append({"role": "system", "content": f"Memory context:\n{memory_context}"})
        messages.extend(history[-6:])
        messages.append({"role": "user", "content": user_input})
        out = self.llm_call(messages, max_tokens=420, temperature=0.2)
        self._trace("research", chars=len(out or ""))
        return out or ""

    def _writer_pass(self, user_input: str, memory_context: str, history: list[dict], research_notes: str) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are Writing Agent. Produce a direct, plain-text response. "
                    "No markdown. No bullet lists unless user explicitly asks."
                )
            },
        ]
        if memory_context:
            messages.append({"role": "system", "content": f"Memory context:\n{memory_context}"})
        if research_notes:
            messages.append({"role": "system", "content": f"Research notes:\n{research_notes}"})
        messages.extend(history[-6:])
        messages.append({"role": "user", "content": user_input})
        out = self.llm_call(messages, max_tokens=620, temperature=0.5)
        self._trace("writer", chars=len(out or ""))
        return out or ""

    def _verifier_pass(self, user_input: str, draft: str, memory_context: str) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are Verifier Agent. Check draft for contradictions, hallucination risk, and user-intent mismatch. "
                    "Return JSON only: {\"ok\": true|false, \"reason\": \"...\", \"revised\": \"...\"}. "
                    "If ok is true, revised may be empty."
                )
            },
            {"role": "system", "content": f"Memory context:\n{memory_context}" if memory_context else "No memory context."},
            {"role": "user", "content": f"Original request:\n{user_input}\n\nDraft:\n{draft}"},
        ]
        raw = self.llm_call(messages, max_tokens=260, temperature=0.1)
        try:
            data = self._parse_json(raw)
            ok = bool(data.get("ok", True))
            revised = (data.get("revised") or "").strip()
            reason = (data.get("reason") or "").strip()
            self._trace("verifier", ok=ok, reason=reason[:160])
            if ok:
                return draft
            return revised if revised else draft
        except Exception as e:
            self._trace("verifier_parse_error", error=str(e)[:160])
            return draft

    def _parse_json(self, text: str) -> dict:
        if not text:
            return {}
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if not m:
                raise ValueError("No JSON object found")
            return json.loads(m.group())

    def _trace(self, event: str, **data):
        try:
            os.makedirs(os.path.dirname(TRACE_FILE), exist_ok=True)
            row = {"ts": datetime.now().isoformat(), "event": event, **data}
            with open(TRACE_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=True) + "\n")
        except Exception:
            if self.debug:
                print(f"[Phase9 trace skipped] {event}")
