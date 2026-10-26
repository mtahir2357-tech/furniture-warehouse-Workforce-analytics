"""Session state shared across pages: forecast run, tolerance, selected day, selected scenario."""
import pandas as pd
import streamlit as st

from src import logic


def as_of() -> pd.Timestamp:
    return st.session_state["as_of"]


def tol() -> float:
    return st.session_state["tol"]


def current_outlook() -> pd.DataFrame:
    return logic.outlook(as_of(), tol())


def target_row(o: pd.DataFrame) -> pd.Series:
    """Selected target day; falls back to the first shortage day, else the first day."""
    tgt = st.session_state.get("target_date")
    if tgt is None or tgt not in set(o["target_date"]):
        short = o[o["status"] == "Shortage"]
        tgt = (short if len(short) else o).iloc[0]["target_date"]
        st.session_state["target_date"] = tgt
    return o[o["target_date"] == tgt].iloc[0]


def set_target(date):
    st.session_state["target_date"] = pd.Timestamp(date)
    st.session_state.pop("scenario_choice", None)
    st.session_state.pop("custom", None)
