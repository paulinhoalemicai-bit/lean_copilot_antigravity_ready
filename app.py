from __future__ import annotations

from datetime import datetime
import io
from typing import Any, Dict, List

import streamlit as st
import pandas as pd
import altair as alt

import db
from config import TOOLS, VOCVOB_COLUMNS
from coach import (
    coach_run,
    new_session_id,
    suggest_serpentes_steps,
    suggest_sipoc_by_step,
    suggest_charter_from_vocvob,
)

st.set_page_config(page_title="Lean Copilot MVP", layout="wide")
db.init_db()


def normalize_tool_for_coach(tool_label: str) -> str:
    return tool_label


def _filled_or_marker(value: str, marker: str) -> str:
    v = (value or "").strip()
    return v if v else f"<PREENCHER_{marker}>"


def pretty_gap_id(gid: str) -> str:
    if not gid:
        return gid
    if gid.startswith("RUBRIC."):
        parts = gid.split(".")
        last = parts[-1] if parts else gid
        mapping = {
            "PROBLEM": "Gap Problema",
            "GOAL": "Gap Objetivo",
            "OBJECTIVE": "Gap Objetivo",
            "BUSINESS_CASE": "Gap Business Case",
            "SCOPE": "Gap Escopo",
            "CTQ": "Gap CTQ",
            "Y": "Gap Y",
            "STAKE": "Gap Stakeholders",
            "TIME": "Gap Cronograma",
        }
        return mapping.get(last, f"Gap {last}")
    return gid


def default_project_state(name: str) -> dict:
    return {
        "project_id": "",
        "name": name,
        "method": "DMAIC",
        "phase": "Define",
        "status": "active",
        "context": {},
        "voc_vob": {"voc": [], "vob": [], "notes": ""},
        "charter": {
            "problem": "",
            "goal": "",
            "business_case": "",
            "scope_in": "",
            "scope_out": "",
            "stakeholders_struct": {
                "sponsor": "",
                "lider_projeto": "",
                "dono_processo": "",
                "time": "",
                "areas_impactadas": "",
                "outros": "",
            },
            "stakeholders": "",
            "ctq": "",
            "y": "",
            "timeline_weeks": {
                "Define": 0,
                "Measure": 0,
                "Analyze": 0,
                "Improve": 0,
                "Control": 0,
            },
        },
        "sipoc": {"serpentes": [], "rows": [], "notes": ""},
        "metrics": [],
        "baseline": {"period": "", "values": {}, "notes": ""},
        "hypotheses": [],
        "solutions": [],
        "pilots": [],
        "control_plan": [],
        "open_gaps": [],
        "last_session_summary": "",
    }


def voc_vob_to_text(voc_rows: List[Dict[str, Any]], vob_rows: List[Dict[str, Any]], notes: str) -> str:
    def fmt_table(title: str, rows: List[Dict[str, Any]]) -> str:
        lines = [f"## {title}"]
        if not rows:
            lines.append("- (vazio)")
            return "\n".join(lines)

        count = 0
        for _, r in enumerate(rows, start=1):
            voz = (r.get("Voz (necessidade)") or "").strip()
            prob = (r.get("Problema") or "").strip()
            req = (r.get("Requisito crítico") or "").strip()
            y = (r.get("Y (como medir)") or "").strip()
            if not (voz or prob or req or y):
                continue
            count += 1
            lines.append(f"\n### Item {count}")
            lines.append(f"- Voz: {voz if voz else '<PREENCHER_VOZ>'}")
            lines.append(f"- Problema: {prob if prob else '<PREENCHER_PROBLEMA>'}")
            lines.append(f"- Requisito crítico: {req if req else '<PREENCHER_REQUISITO>'}")
            lines.append(f"- Y (como medir): {y if y else '<PREENCHER_Y>'}")

        if count == 0:
            lines.append("- (vazio)")
        return "\n".join(lines)

    out = ["# VOC/VOB (estruturado)", ""]
    out.append(fmt_table("Voz do Cliente (VOC)", voc_rows))
    out.append("")
    out.append(fmt_table("Voz do Negócio (VOB)", vob_rows))
    if (notes or "").strip():
        out.append("")
        out.append("## Notas")
        out.append(notes.strip())
    return "\n".join(out)


def charter_to_text(charter: dict) -> str:
    problem = _filled_or_marker(charter.get("problem", ""), "PROBLEMA")
    goal = _filled_or_marker(charter.get("goal", ""), "OBJETIVO")
    business_case = _filled_or_marker(charter.get("business_case", ""), "BUSINESS_CASE")
    scope_in = _filled_or_marker(charter.get("scope_in", ""), "ESCOPO_IN")
    scope_out = _filled_or_marker(charter.get("scope_out", ""), "ESCOPO_OUT")

    st_struct = charter.get("stakeholders_struct") or {}
    sponsor = _filled_or_marker(st_struct.get("sponsor", ""), "PATROCINADOR")
    lider_projeto = _filled_or_marker(st_struct.get("lider_projeto", ""), "LIDER_PROJETO")
    dono_processo = _filled_or_marker(st_struct.get("dono_processo", ""), "DONO_PROCESSO")
    time = _filled_or_marker(st_struct.get("time", ""), "TIME")
    areas = _filled_or_marker(st_struct.get("areas_impactadas", ""), "AREAS_IMPACTADAS")
    outros = _filled_or_marker(st_struct.get("outros", ""), "OUTROS")

    ctq = _filled_or_marker(charter.get("ctq", ""), "CTQ")
    y = _filled_or_marker(charter.get("y", ""), "Y")

    timeline = charter.get("timeline_weeks") or {}
    d = int(timeline.get("Define", 0) or 0)
    m = int(timeline.get("Measure", 0) or 0)
    a = int(timeline.get("Analyze", 0) or 0)
    i = int(timeline.get("Improve", 0) or 0)
    c = int(timeline.get("Control", 0) or 0)
    total = d + m + a + i + c

    return f"""# Project Charter

## Problema
{problem}

## Objetivo
{goal}

## Business Case
{business_case}

## Escopo
- IN: {scope_in}
- OUT: {scope_out}

## Stakeholders
- Patrocinador: {sponsor}
- Líder do projeto: {lider_projeto}
- Dono do processo: {dono_processo}
- Time: {time}
- Áreas impactadas: {areas}
- Outros: {outros}

## CTQ
{ctq}

## Y
{y}

## Cronograma DMAIC
- Define: {d}
- Measure: {m}
- Analyze: {a}
- Improve: {i}
- Control: {c}
- Total: {total}
"""


def build_gantt_df(timeline_weeks: dict) -> pd.DataFrame:
    phases = ["Define", "Measure", "Analyze", "Improve", "Control"]
    starts, ends, durations = [], [], []
    cur = 0
    for p in phases:
        dur = int(timeline_weeks.get(p, 0) or 0)
        start = cur
        end = cur + dur
        starts.append(start)
        ends.append(end)
        durations.append(dur)
        cur = end
    return pd.DataFrame({"Fase": phases, "Start": starts, "End": ends, "Duração": durations})


def gantt_chart(df: pd.DataFrame):
    df2 = df[df["Duração"] > 0].copy()
    if df2.empty:
        return None
    return (
        alt.Chart(df2)
        .mark_bar()
        .encode(
            y=alt.Y("Fase:N", sort=["Define", "Measure", "Analyze", "Improve", "Control"], title=None),
            x=alt.X("Start:Q", title="Semanas", axis=alt.Axis(tickMinStep=1)),
            x2="End:Q",
            tooltip=["Fase:N", "Start:Q", "End:Q", "Duração:Q"],
        )
        .properties(height=220)
    )


def _dedup_clean(items: List[str]) -> List[str]:
    out = []
    seen = set()
    for it in items or []:
        t = (it or "").strip()
        if not t:
            continue
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def sipoc_compact_rows_to_step_map(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[str]]]:
    step_map: Dict[str, Dict[str, List[str]]] = {}
    for r in rows or []:
        p = (r.get("p") or "").strip()
        if not p:
            continue
        step_map[p] = {
            "S": _dedup_clean(r.get("s") or []),
            "I": _dedup_clean(r.get("i") or []),
            "O": _dedup_clean(r.get("o") or []),
            "C": _dedup_clean(r.get("c") or []),
        }
    return step_map


def step_map_to_compact_rows(serp_steps: List[str], step_map: Dict[str, Dict[str, List[str]]]) -> List[Dict[str, Any]]:
    out = []
    for p in serp_steps or []:
        d = step_map.get(p, {"S": [], "I": [], "O": [], "C": []})
        out.append({
            "p": p,
            "s": _dedup_clean(d.get("S", [])),
            "i": _dedup_clean(d.get("I", [])),
            "o": _dedup_clean(d.get("O", [])),
            "c": _dedup_clean(d.get("C", [])),
        })
    return out


def step_map_to_editor_df(p: str, data: Dict[str, List[str]], min_rows: int = 6) -> pd.DataFrame:
    s = data.get("S", []) or []
    i = data.get("I", []) or []
    o = data.get("O", []) or []
    c = data.get("C", []) or []
    n = max(len(s), len(i), len(o), len(c), min_rows)
    rows = []
    for idx in range(n):
        rows.append({
            "S (Fornecedores)": s[idx] if idx < len(s) else "",
            "I (Entradas)": i[idx] if idx < len(i) else "",
            "P (Etapa do processo)": p,
            "O (Saídas)": o[idx] if idx < len(o) else "",
            "C (Clientes)": c[idx] if idx < len(c) else "",
        })
    return pd.DataFrame(rows)


def editor_df_to_step_lists(df: pd.DataFrame) -> Dict[str, List[str]]:
    s = _dedup_clean(df["S (Fornecedores)"].fillna("").tolist()) if "S (Fornecedores)" in df.columns else []
    i = _dedup_clean(df["I (Entradas)"].fillna("").tolist()) if "I (Entradas)" in df.columns else []
    o = _dedup_clean(df["O (Saídas)"].fillna("").tolist()) if "O (Saídas)" in df.columns else []
    c = _dedup_clean(df["C (Clientes)"].fillna("").tolist()) if "C (Clientes)" in df.columns else []
    return {"S": s, "I": i, "O": o, "C": c}


def sipoc_to_text(serpentes_records: List[Dict[str, Any]], compact_rows: List[Dict[str, Any]], notes: str) -> str:
    serp_steps = [str(x.get("Macro etapa (Serpentes)", "")).strip() for x in serpentes_records or []]
    serp_steps = [s for s in serp_steps if s]
    lines = ["# SIPOC por etapa", "", "## Serpentes (macro etapas)"]
    for idx, s in enumerate(serp_steps, start=1):
        lines.append(f"{idx}. {s}")
    lines.append("")
    lines.append("## SIPOC por etapa (S/I/P/O/C)")
    for r in compact_rows or []:
        p = r.get("p", "")
        lines.append(f"\n### Etapa: {p}")
        lines.append(f"- S: {', '.join(r.get('s', []) or [])}")
        lines.append(f"- I: {', '.join(r.get('i', []) or [])}")
        lines.append(f"- O: {', '.join(r.get('o', []) or [])}")
        lines.append(f"- C: {', '.join(r.get('c', []) or [])}")
    if (notes or "").strip():
        lines.append("")
        lines.append("## Notas")
        lines.append(notes.strip())
    return "\n".join(lines)


st.sidebar.title("Projetos")

if "active_project_id" not in st.session_state:
    st.session_state.active_project_id = None

projects = db.list_projects()

with st.sidebar.expander("➕ Criar novo projeto", expanded=False):
    new_name = st.text_input("Nome do projeto", "")
    if st.button("Criar"):
        pid = f"P{int(datetime.utcnow().timestamp())}"
        state = default_project_state(new_name or pid)
        state["project_id"] = pid
        db.upsert_project(pid, state["name"], state)
        st.session_state.active_project_id = pid
        st.rerun()

if projects:
    st.sidebar.caption("Abrir projeto")
    for p in projects:
        if st.sidebar.button(f"📁 {p['name']}", key=f"open_{p['project_id']}"):
            st.session_state.active_project_id = p["project_id"]
            st.rerun()
else:
    st.sidebar.info("Crie um projeto para começar.")

pid = st.session_state.active_project_id
if not pid:
    st.title("Lean Copilot MVP")
    st.write("Crie ou selecione um projeto no menu lateral.")
    st.stop()

project_state = db.get_project_state(pid)
if not project_state:
    st.error("Projeto não encontrado.")
    st.stop()

st.title(f"Projeto: {project_state['name']} ({pid})")

colA, colB = st.columns([1, 1])
with colA:
    default_tool = st.session_state.get("active_tool", None)
    if not default_tool or default_tool not in TOOLS:
        default_tool = TOOLS[0]
    tool = st.selectbox("Ferramenta", TOOLS, index=TOOLS.index(default_tool))
    st.session_state.active_tool = tool
with colB:
    mode = st.radio("Modo do coach", ["review", "generate"], horizontal=True)

left, right = st.columns([1.6, 1.0], gap="large")
new_text = ""

with left:
    if tool == "VOC/VOB":
        st.subheader("VOC/VOB (estruturado)")

        draft = db.load_draft(pid, tool) or {}
        stored = draft.get("voc_vob") or project_state.get("voc_vob") or {"voc": [], "vob": [], "notes": ""}
        voc_rows = stored.get("voc") or []
        vob_rows = stored.get("vob") or []
        notes = stored.get("notes") or ""

        def build_df(rows: List[Dict[str, Any]], n: int = 6) -> pd.DataFrame:
            if rows:
                df = pd.DataFrame(rows)
            else:
                df = pd.DataFrame([{c: "" for c in VOCVOB_COLUMNS} for _ in range(n)])
            for c in VOCVOB_COLUMNS:
                if c not in df.columns:
                    df[c] = ""
            return df[VOCVOB_COLUMNS]

        tab1, tab2 = st.tabs(["VOC — Voz do Cliente", "VOB — Voz do Negócio"])
        with tab1:
            df_voc = build_df(voc_rows)
            df_voc_edit = st.data_editor(df_voc, num_rows="dynamic", use_container_width=True, key=f"voc_{pid}")
        with tab2:
            df_vob = build_df(vob_rows)
            df_vob_edit = st.data_editor(df_vob, num_rows="dynamic", use_container_width=True, key=f"vob_{pid}")

        notes = st.text_area("Notas (opcional)", value=notes, height=100)

        voc_out = df_voc_edit.fillna("").to_dict(orient="records")
        vob_out = df_vob_edit.fillna("").to_dict(orient="records")
        new_text = voc_vob_to_text(voc_out, vob_out, notes)

        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            if st.button("💾 Salvar VOC/VOB"):
                payload = {"voc_vob": {"voc": voc_out, "vob": vob_out, "notes": notes}, "text": new_text}
                db.save_draft(pid, tool, payload)
                project_state["voc_vob"] = {"voc": voc_out, "vob": vob_out, "notes": notes}
                db.upsert_project(pid, project_state["name"], project_state)
                st.success("VOC/VOB salvo.")

        key_charter_sug = f"vocvob_to_charter_sug_{pid}"
        if key_charter_sug not in st.session_state:
            st.session_state[key_charter_sug] = None

        with c2:
            if st.button("🧠 IA sugerir Problema/Objetivo (Charter)"):
                st.session_state[key_charter_sug] = suggest_charter_from_vocvob(project_state, new_text)
                st.success("Sugestões geradas.")

        with c3:
            with st.expander("👀 Pré-visualizar texto do coach", expanded=False):
                st.markdown(new_text)

        sug = st.session_state.get(key_charter_sug)
        if sug and sug.get("candidates"):
            st.markdown("### Sugestões editáveis para o Project Charter")
            for idx, c in enumerate(sug["candidates"], start=1):
                with st.expander(f"Opção {idx}: {c.get('title','(sem título)')}"):
                    st.markdown("**Rascunho:**")
                    st.write(c.get("draft", ""))
                    st.markdown("**Por que faz sentido:**")
                    st.write(c.get("why", ""))
                    st.markdown("**Como testar/refutar:**")
                    st.write(c.get("how_to_test", ""))
                    if st.button(f"✅ Aplicar ao Project Charter — Opção {idx}", key=f"apply_vocvob_{pid}_{idx}"):
                        draft_txt = (c.get("draft") or "").strip()
                        prob_line = ""
                        obj_line = ""
                        for line in draft_txt.splitlines():
                            l = line.strip()
                            if l.lower().startswith("problema:"):
                                prob_line = l.split(":", 1)[1].strip()
                            if l.lower().startswith("objetivo:"):
                                obj_line = l.split(":", 1)[1].strip()
                        ch = project_state.get("charter") or {}
                        if prob_line:
                            ch["problem"] = prob_line
                        if obj_line:
                            ch["goal"] = obj_line
                        project_state["charter"] = ch
                        db.upsert_project(pid, project_state["name"], project_state)
                        st.success("Aplicado ao Project Charter.")
                        st.rerun()

    elif tool == "Project Charter":
        st.subheader("Project Charter (campos estruturados)")
        storage_tool = tool
        coach_tool = normalize_tool_for_coach(tool)

        draft = db.load_draft(pid, storage_tool) or {}
        charter = draft.get("charter") or project_state.get("charter") or {}
        timeline = charter.get("timeline_weeks") or {"Define": 0, "Measure": 0, "Analyze": 0, "Improve": 0, "Control": 0}
        st_struct = charter.get("stakeholders_struct") or {}

        form_col, chart_col = st.columns([2.2, 1.0], gap="large")
        with form_col:
            problem = st.text_area("Problema", value=charter.get("problem", ""), height=80)
            goal = st.text_area("Objetivo SMART", value=charter.get("goal", ""), height=80)
            business_case = st.text_area("Business case", value=charter.get("business_case", ""), height=80)
            col1, col2 = st.columns(2)
            with col1:
                scope_in = st.text_area("Escopo IN", value=charter.get("scope_in", ""), height=80)
            with col2:
                scope_out = st.text_area("Escopo OUT", value=charter.get("scope_out", ""), height=80)

            st.markdown("### Stakeholders")
            sA, sB = st.columns(2)
            with sA:
                sponsor = st.text_input("Patrocinador", value=st_struct.get("sponsor", ""))
                lider_projeto = st.text_input("Líder do projeto", value=st_struct.get("lider_projeto", ""))
                dono_processo = st.text_input("Dono do processo", value=st_struct.get("dono_processo", ""))
            with sB:
                time_txt = st.text_area("Time", value=st_struct.get("time", ""), height=80)
                areas_txt = st.text_area("Áreas impactadas", value=st_struct.get("areas_impactadas", ""), height=80)
            outros_txt = st.text_area("Outros stakeholders", value=st_struct.get("outros", ""), height=70)

            ctq = st.text_area("CTQ", value=charter.get("ctq", ""), height=90)
            y = st.text_area("Y", value=charter.get("y", ""), height=90)

            st.markdown("### Cronograma DMAIC (semanas)")
            cA, cB, cC, cD, cE = st.columns(5)
            with cA:
                define_w = st.number_input("Define", min_value=0, max_value=52, value=int(timeline.get("Define", 0) or 0), step=1)
            with cB:
                measure_w = st.number_input("Measure", min_value=0, max_value=52, value=int(timeline.get("Measure", 0) or 0), step=1)
            with cC:
                analyze_w = st.number_input("Analyze", min_value=0, max_value=52, value=int(timeline.get("Analyze", 0) or 0), step=1)
            with cD:
                improve_w = st.number_input("Improve", min_value=0, max_value=52, value=int(timeline.get("Improve", 0) or 0), step=1)
            with cE:
                control_w = st.number_input("Control", min_value=0, max_value=52, value=int(timeline.get("Control", 0) or 0), step=1)

            timeline_weeks = {
                "Define": int(define_w),
                "Measure": int(measure_w),
                "Analyze": int(analyze_w),
                "Improve": int(improve_w),
                "Control": int(control_w),
            }

            stakeholders_struct = {
                "sponsor": sponsor,
                "lider_projeto": lider_projeto,
                "dono_processo": dono_processo,
                "time": time_txt,
                "areas_impactadas": areas_txt,
                "outros": outros_txt,
            }

            charter_obj = {
                "problem": problem,
                "goal": goal,
                "business_case": business_case,
                "scope_in": scope_in,
                "scope_out": scope_out,
                "stakeholders_struct": stakeholders_struct,
                "stakeholders": "",
                "ctq": ctq,
                "y": y,
                "timeline_weeks": timeline_weeks,
            }

            new_text = charter_to_text(charter_obj)

            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                if st.button("💾 Salvar Project Charter"):
                    db.save_draft(pid, storage_tool, {"charter": charter_obj, "text": new_text})
                    project_state["charter"] = charter_obj
                    db.upsert_project(pid, project_state["name"], project_state)
                    st.success("Project Charter salvo.")
            with c2:
                if st.button("🧹 Limpar campos"):
                    empty = default_project_state(project_state["name"])["charter"]
                    db.save_draft(pid, storage_tool, {"charter": empty, "text": charter_to_text(empty)})
                    project_state["charter"] = empty
                    db.upsert_project(pid, project_state["name"], project_state)
                    st.rerun()
            with c3:
                with st.expander("👀 Pré-visualizar texto do coach", expanded=False):
                    st.markdown(new_text)

        with chart_col:
            st.markdown("### Cronograma (Gantt)")
            df = build_gantt_df(timeline_weeks)
            total = int(df["Duração"].sum())
            st.metric("Total (semanas)", total)
            chart = gantt_chart(df)
            if chart is None:
                st.info("Preencha as semanas para ver o Gantt.")
            else:
                st.altair_chart(chart, use_container_width=True)

    elif tool == "SIPOC (por etapa)":
        st.subheader("SIPOC (por etapa) — ordem S | I | P | O | C")

        draft = db.load_draft(pid, tool) or {}
        stored = draft.get("sipoc") or project_state.get("sipoc") or {}
        serpentes_rows = stored.get("serpentes") or []
        sipoc_rows_compact = stored.get("rows") or []
        notes = stored.get("notes") or ""

        work_key = f"sipoc_step_map_{pid}"
        ver_key = f"sipoc_editor_ver_{pid}"
        if ver_key not in st.session_state:
            st.session_state[ver_key] = 0
        if work_key not in st.session_state:
            st.session_state[work_key] = sipoc_compact_rows_to_step_map(sipoc_rows_compact)
        step_map = st.session_state[work_key]

        st.markdown("### 1) Diagrama de Serpentes")
        serp_df = pd.DataFrame(serpentes_rows) if serpentes_rows else pd.DataFrame([{"Macro etapa (Serpentes)": ""} for _ in range(8)])
        if "Macro etapa (Serpentes)" not in serp_df.columns:
            serp_df["Macro etapa (Serpentes)"] = ""
        serp_edit = st.data_editor(serp_df, num_rows="dynamic", use_container_width=True, key=f"serp_{pid}")

        hint = st.text_input("Dica para a IA (opcional)", value=st.session_state.get(f"sipoc_hint_{pid}", ""), key=f"sipoc_hint_{pid}")

        cS1, cS2 = st.columns([1, 2])
        with cS1:
            if st.button("🤖 IA sugerir macro etapas", key=f"btn_serp_suggest_{pid}"):
                out = suggest_serpentes_steps(project_state, hint=hint)
                steps = out.get("macro_etapas", []) or []
                st.session_state[f"serp_suggest_df_{pid}"] = pd.DataFrame([{"Macro etapa (Serpentes)": s} for s in steps])
                st.success("Sugestão gerada.")
        with cS2:
            if f"serp_suggest_df_{pid}" in st.session_state:
                with st.expander("Ver sugestão da IA"):
                    sdf = st.session_state[f"serp_suggest_df_{pid}"]
                    st.dataframe(sdf, use_container_width=True)
                    if st.button("✅ Aplicar sugestão no Serpentes", key=f"apply_serp_{pid}"):
                        st.session_state[f"serp_applied_df_{pid}"] = sdf
                        st.session_state[f"serp_apply_now_{pid}"] = True
                        st.rerun()

        if st.session_state.get(f"serp_apply_now_{pid}"):
            st.session_state[f"serp_apply_now_{pid}"] = False
            serp_edit = st.session_state.get(f"serp_applied_df_{pid}", serp_edit)

        serp_steps = [str(x or "").strip() for x in serp_edit["Macro etapa (Serpentes)"].fillna("").tolist()]
        serp_steps = [s for s in serp_steps if s]
        for p in serp_steps:
            if p not in step_map:
                step_map[p] = {"S": [], "I": [], "O": [], "C": []}
        if not serp_steps and step_map:
            serp_steps = list(step_map.keys())

        st.markdown("---")
        st.markdown("### 2) SIPOC por etapa — 1 item por linha")

        if not serp_steps:
            st.info("Preencha o Serpentes para criar as etapas.")
        else:
            key_sipoc_sug = f"sipoc_suggestions_{pid}"
            if key_sipoc_sug not in st.session_state:
                st.session_state[key_sipoc_sug] = None

            if st.button("Gerar sugestões por etapa (IA)", key=f"btn_sipoc_sug_{pid}"):
                out = suggest_sipoc_by_step(project_state, serp_steps)
                st.session_state[key_sipoc_sug] = out
                st.success("Sugestões geradas.")

            sug = st.session_state.get(key_sipoc_sug)
            if sug:
                with st.expander("Ver sugestões (por etapa)"):
                    if sug.get("observacoes"):
                        st.write(sug.get("observacoes"))
                    for r in sug.get("rows", []):
                        with st.expander(f"Etapa: {r.get('p','(sem nome)')}"):
                            st.markdown("**Fornecedores (S):**")
                            st.write("\n".join(r.get("s", [])))
                            st.markdown("**Entradas (I):**")
                            st.write("\n".join(r.get("i", [])))
                            st.markdown("**Saídas (O):**")
                            st.write("\n".join(r.get("o", [])))
                            st.markdown("**Clientes (C):**")
                            st.write("\n".join(r.get("c", [])))

                apply_only_empty = st.checkbox("Aplicar apenas onde estiver vazio", value=True, key=f"apply_empty_{pid}")
                if st.button("✅ Aplicar sugestões ao SIPOC", key=f"apply_sipoc_sug_{pid}"):
                    sug_map = {r["p"]: r for r in sug.get("rows", []) if r.get("p")}

                    def merge_list(cur_list: list[str], sug_list: list[str]) -> list[str]:
                        cur_list = cur_list or []
                        sug_list = sug_list or []
                        if apply_only_empty and cur_list:
                            return cur_list
                        out_list = list(cur_list)
                        for item in sug_list:
                            t = (item or "").strip()
                            if t and t not in out_list:
                                out_list.append(t)
                        return out_list

                    for p in serp_steps:
                        if p not in sug_map:
                            continue
                        r = sug_map[p]
                        cur = step_map.get(p, {"S": [], "I": [], "O": [], "C": []})
                        cur["S"] = merge_list(cur.get("S", []), r.get("s", []))
                        cur["I"] = merge_list(cur.get("I", []), r.get("i", []))
                        cur["O"] = merge_list(cur.get("O", []), r.get("o", []))
                        cur["C"] = merge_list(cur.get("C", []), r.get("c", []))
                        step_map[p] = cur
                    st.session_state[work_key] = step_map
                    st.session_state[ver_key] += 1
                    st.success("Sugestões aplicadas.")
                    st.rerun()

            edited_step_map: dict[str, dict[str, list[str]]] = {}
            ver = st.session_state[ver_key]
            for idx, p in enumerate(serp_steps, start=1):
                st.markdown(f"#### Etapa {idx}: {p}")
                data = step_map.get(p, {"S": [], "I": [], "O": [], "C": []})
                df_step = step_map_to_editor_df(p, data, min_rows=6)
                df_edit = st.data_editor(
                    df_step,
                    num_rows="dynamic",
                    use_container_width=True,
                    key=f"sipoc_step_{pid}_{idx}_v{ver}",
                    column_config={
                        "P (Etapa do processo)": st.column_config.TextColumn(
                            "P (Etapa do processo)",
                            disabled=True,
                            width="small",
                        )
                    },
                )
                df_edit["P (Etapa do processo)"] = p
                edited_step_map[p] = editor_df_to_step_lists(df_edit)
                st.markdown("---")

            st.session_state[work_key] = edited_step_map
            step_map = edited_step_map
            notes = st.text_area("Notas (opcional)", value=notes, height=90)

            sipoc_rows_compact_out = step_map_to_compact_rows(serp_steps, step_map)
            serp_records = serp_edit.fillna("").to_dict(orient="records")
            new_text = sipoc_to_text(serp_records, sipoc_rows_compact_out, notes)

            st.markdown("### 3) SIPOC Geral (planilha única)")
            rows_general = []
            for p in serp_steps:
                d = step_map.get(p, {"S": [], "I": [], "O": [], "C": []})
                rows_general.append({
                    "S (Fornecedores)": "\n".join(d.get("S", [])),
                    "I (Entradas)": "\n".join(d.get("I", [])),
                    "P (Etapa do processo)": p,
                    "O (Saídas)": "\n".join(d.get("O", [])),
                    "C (Clientes)": "\n".join(d.get("C", [])),
                })
            df_general = pd.DataFrame(rows_general, columns=["S (Fornecedores)", "I (Entradas)", "P (Etapa do processo)", "O (Saídas)", "C (Clientes)"])
            st.dataframe(df_general, use_container_width=True)

            csv_bytes = df_general.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "⬇️ Baixar SIPOC Geral (CSV)",
                data=csv_bytes,
                file_name=f"sipoc_geral_{pid}.csv",
                mime="text/csv",
            )

            xlsx_buffer = io.BytesIO()
            with pd.ExcelWriter(xlsx_buffer, engine="openpyxl") as writer:
                df_general.to_excel(writer, index=False, sheet_name="SIPOC_Geral")
            st.download_button(
                "⬇️ Baixar SIPOC Geral (Excel)",
                data=xlsx_buffer.getvalue(),
                file_name=f"sipoc_geral_{pid}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

            b1, b2, b3 = st.columns([1, 1, 1])
            with b1:
                if st.button("💾 Salvar SIPOC"):
                    payload = {"sipoc": {"serpentes": serp_records, "rows": sipoc_rows_compact_out, "notes": notes}, "text": new_text}
                    db.save_draft(pid, tool, payload)
                    project_state["sipoc"] = {"serpentes": serp_records, "rows": sipoc_rows_compact_out, "notes": notes}
                    db.upsert_project(pid, project_state["name"], project_state)
                    st.success("SIPOC salvo.")
            with b2:
                if st.button("🧹 Limpar SIPOC"):
                    empty_serp = pd.DataFrame([{"Macro etapa (Serpentes)": ""} for _ in range(8)]).to_dict(orient="records")
                    payload = {"sipoc": {"serpentes": empty_serp, "rows": [], "notes": ""}, "text": ""}
                    db.save_draft(pid, tool, payload)
                    project_state["sipoc"] = {"serpentes": empty_serp, "rows": [], "notes": ""}
                    db.upsert_project(pid, project_state["name"], project_state)
                    if work_key in st.session_state:
                        del st.session_state[work_key]
                    st.session_state[ver_key] = 0
                    st.rerun()
            with b3:
                with st.expander("👀 Pré-visualizar texto do coach", expanded=False):
                    st.markdown(new_text)

    else:
        st.subheader("Rascunho do aluno (texto livre)")
        draft = db.load_draft(pid, tool) or {}
        draft_text = draft.get("text", "")
        new_text = st.text_area("Escreva/cole o conteúdo atual desta ferramenta aqui:", value=draft_text, height=420)
        col_save, col_hint = st.columns([1, 2])
        with col_save:
            if st.button("💾 Salvar rascunho"):
                db.save_draft(pid, tool, {"text": new_text})
                st.success("Rascunho salvo.")
        with col_hint:
            st.caption("Dica: salve a cada iteração curta.")

with right:
    st.subheader("Coach agora")
    coach_tool = normalize_tool_for_coach(tool)

    if st.button("🔎 Revisar agora"):
        coach_json, rubric_scores, _ = coach_run(coach_tool, project_state, new_text, mode=mode)
        sid = new_session_id()
        db.add_session_log(
            session_id=sid,
            project_id=pid,
            tool=tool,
            event_type="REQUEST_REVIEW_NOW" if mode == "review" else "REQUEST_GENERATE_OPTIONS",
            user_delta="Revisão solicitada pelo usuário",
            coach_payload=coach_json,
        )

        st.markdown("### ✅ O que está OK")
        if coach_json.get("ok"):
            for ok in coach_json["ok"]:
                st.write(f"- {ok}")
        else:
            st.write("- (ainda nada bem definido)")

        st.markdown("### ⚠️ Lacunas (gaps)")
        if coach_json.get("gaps"):
            for g in coach_json["gaps"]:
                gid = pretty_gap_id(g.get("id", ""))
                st.write(f"- **{gid}** ({g.get('severity','')}): {g.get('reason','')}")
        else:
            st.write("- Sem lacunas relevantes detectadas.")

        st.markdown("### ❓ Perguntas prioritárias")
        for q in coach_json.get("questions", []):
            st.write(f"- {q}")

        st.markdown("### ➡️ Próximo passo")
        st.info(coach_json.get("next_action", ""))

        st.markdown("### 📊 Rubrica parcial")
        st.json(rubric_scores)

        if mode == "generate":
            st.markdown("### 🧠 Candidatos (editáveis)")
            if coach_json.get("candidates"):
                st.json(coach_json["candidates"])
            else:
                st.write("Nenhum candidato gerado.")

    st.markdown("---")
    st.subheader("Memória recente (logs)")
    recent = db.list_recent_sessions(pid, limit=6)
    if not recent:
        st.write("Sem sessões ainda.")
    else:
        for s in recent:
            title = f"{s['created_at']} · {s['tool']} · {s['event_type']}"
            with st.expander(title):
                st.write("Delta:", s["user_delta"])
                st.json(s["coach"])
