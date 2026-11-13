"""Script generation, stages 1-5 of WORKFLOW_AND_STORAGE.md s2.2."""
import json
import time
from concurrent.futures import ThreadPoolExecutor

from . import llm, store
from .config import settings
from .schemas import (
    Critique,
    GenerateRequest,
    Script,
    SectionBudget,
    SectionDraft,
    Segment,
    Slot,
    StoryAnalysis,
)

# Fraction of total time per section kind; nirupana shares whatever is left.
_FIXED = {"invocation": 0.05, "prastavana": 0.15, "mangalam": 0.05}
_FALLBACK_CPS = 13.2  # chars/sec until calibration.json exists


def analyse(pid: str, req: GenerateRequest) -> StoryAnalysis:
    prompt = f"Extract characters, events, deity, bhava, moral.\nTitle: {req.title}\n{req.story}"

    def mock() -> StoryAnalysis:
        events = [s.strip() for s in req.story.replace("\n", " ").split(".") if s.strip()]
        return StoryAnalysis(
            characters=[], events=events or [req.title], deity="unknown",
            bhava="bhakti", moral="[mock]",
        )

    return llm.complete_json(
        pid=pid, stage="analyse", prompt=prompt, model=StoryAnalysis, mock_fn=mock
    )


def budget(req: GenerateRequest, analysis: StoryAnalysis, cps: float) -> list[SectionBudget]:
    total = req.duration_minutes * 60
    n_nir = max(1, min(4, req.duration_minutes // 2))
    nir_sec = total * (1 - sum(_FIXED.values())) / n_nir

    def slots(types: list[str], sec: float) -> list[Slot]:
        each = sec / len(types)
        return [Slot(type=t, target_sec=each, target_chars=round(each * cps)) for t in types]

    chunks = [analysis.events[i::n_nir] for i in range(n_nir)]
    out = [
        SectionBudget(section="invocation", kind="invocation",
                      target_sec=total * _FIXED["invocation"], slots=slots(["shloka"], total * _FIXED["invocation"])),
        SectionBudget(section="prastavana", kind="prastavana",
                      target_sec=total * _FIXED["prastavana"], slots=slots(["narration"], total * _FIXED["prastavana"])),
    ]
    out += [
        SectionBudget(section=f"nirupana_{i + 1}", kind="nirupana", target_sec=nir_sec,
                      events=chunks[i], slots=slots(["narration", "song", "narration"], nir_sec))
        for i in range(n_nir)
    ]
    out.append(SectionBudget(section="mangalam", kind="mangalam",
                             target_sec=total * _FIXED["mangalam"], slots=slots(["shloka"], total * _FIXED["mangalam"])))
    return out


def retrieve(req: GenerateRequest, analysis: StoryAnalysis, budgets: list[SectionBudget]) -> dict:
    """Offer verified corpus records per section. Only IDs are stored."""
    path = settings.data_dir / "songs.json"
    corpus = json.loads(path.read_text()) if path.exists() else []
    kinds = {"invocation": "shloka", "mangalam": "shloka", "nirupana": "song"}
    result = {}
    for b in budgets:
        kind = kinds.get(b.kind)
        offered = [
            s["id"] for s in corpus
            if s.get("status") == "verified" and s.get("language") == req.language
            and s.get("kind") == kind
            and (analysis.deity in s.get("deity", []) or not s.get("deity"))
        ]
        result[b.section] = {
            "query": {"deity": analysis.deity, "language": req.language, "kind": kind},
            "offered_ids": offered,
            "used_ids": [],
        }
    return result


def write_section(pid: str, b: SectionBudget, offered: list[str], corpus: dict) -> SectionDraft:
    prompt = f"Write section {b.section} ({b.kind}), events={b.events}, slots={b.slots}, offered={offered}"

    def mock() -> SectionDraft:
        segs = []
        for i, slot in enumerate(b.slots, 1):
            text = f"[mock {slot.type} for {b.section}] " + " ".join(b.events)
            segs.append(Segment(
                id=f"{b.section}.{i}", section=b.section, type=slot.type,
                text=text[: max(slot.target_chars, 20)], target_sec=slot.target_sec,
            ))
        return SectionDraft(section=b.section, segments=segs)

    return llm.complete_json(
        pid=pid, stage=f"write:{b.section}", prompt=prompt, model=SectionDraft, mock_fn=mock
    )


def critique(pid: str, script: Script) -> Critique:
    prompt = "Judge this script for invented scripture and overruns:\n" + script.model_dump_json()
    return llm.complete_json(
        pid=pid, stage="critique", prompt=prompt, model=Critique, mock_fn=lambda: Critique(ok=True)
    )


def run_script_job(pid: str) -> None:
    """Background job. Every stage writes its own artifact; failures land in status.json."""
    timings: dict[str, float] = {}
    t0 = time.monotonic()

    def lap(name: str) -> None:
        nonlocal t0
        timings[name] = round(time.monotonic() - t0, 2)
        t0 = time.monotonic()

    try:
        req = GenerateRequest.model_validate(store.read(pid, "request.json"))

        store.write_status(pid, "analysing", progress=0.1)
        analysis = analyse(pid, req)
        store.write_stage(pid, "01_analysis.json", analysis.model_dump())
        lap("analyse")

        store.write_status(pid, "planning", progress=0.3)
        budgets = budget(req, analysis, _FALLBACK_CPS)
        store.write_stage(pid, "02_budget.json", {
            "chars_per_sec": _FALLBACK_CPS, "sections": [b.model_dump() for b in budgets],
        })
        retrieval = retrieve(req, analysis, budgets)
        store.write_stage(pid, "03_retrieval.json", retrieval)
        lap("plan")

        store.write_status(pid, "writing", progress=0.5)
        with ThreadPoolExecutor(max_workers=4) as pool:
            drafts = list(pool.map(
                lambda b: write_section(pid, b, retrieval[b.section]["offered_ids"], {}), budgets
            ))
        for d in drafts:
            store.write_stage(pid, f"04_drafts/{d.section}.json", d.model_dump())
        lap("write")

        script = Script(
            title=req.title, language=req.language, target_sec=req.duration_minutes * 60,
            segments=[s for d in drafts for s in d.segments],
        )
        for sec, r in retrieval.items():
            r["used_ids"] = sorted({i for s in script.segments if s.section == sec for i in s.source_ids})
        store.write_stage(pid, "03_retrieval.json", retrieval)

        store.write_status(pid, "writing", "critique", progress=0.85)
        verdict = critique(pid, script)
        store.write_stage(pid, "05_critique.json", {
            **verdict.model_dump(), "fixes": [],  # before/after text once rewrite pass exists
        })
        lap("critique")

        store.save_script(pid, script.model_dump(mode="json"), "initial + critique")
        store.update_meta(pid, timings_sec=timings, llm_calls=len(budgets) + 2)
        store.write_status(pid, "scripted", progress=1.0)
    except Exception as e:  # noqa: BLE001 - surfaced to the UI via status.json
        store.write_status(pid, "error", f"{type(e).__name__}: {e}")
