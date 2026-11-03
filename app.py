"""Simplified furniture warehouse decision-support app (three-page entrypoint)."""
import streamlit as st
from src import data, logic
from src.config import DEFAULT_BALANCED_TOLERANCE_HRS

st.set_page_config(page_title='Furniture Workforce Planning', page_icon='📦', layout='wide')
st.markdown('''<style>
.block-container {max-width:1250px;padding-top:1.5rem}
[data-testid="stMetric"] {background:#f6f8fb;border:1px solid #e4eaf0;border-radius:12px;padding:14px}
h1,h2,h3 {letter-spacing:-.02em}
</style>''',unsafe_allow_html=True)
try:
    runs=data.forecast_runs()
    if not runs: raise ValueError('No saved forecast runs were found.')
except (FileNotFoundError,ValueError,KeyError) as exc:
    st.error(f'Could not load warehouse data: {exc}')
    st.stop()
if 'tol' not in st.session_state: st.session_state.tol=DEFAULT_BALANCED_TOLERANCE_HRS
if 'as_of_pick' not in st.session_state: st.session_state.as_of_pick=runs[-1].date()
with st.sidebar:
    st.title('📦 Workforce Planner')
    st.caption('Single furniture fulfillment warehouse')
    selected=st.date_input('Forecast run date',min_value=runs[0].date(),max_value=runs[-1].date(),key='as_of_pick')
    st.session_state['as_of']=logic.snap_to_run(selected)
    if st.session_state['as_of'].date()!=selected:
        st.caption('Showing latest available forecast run on or before your date.')
    st.slider('Balanced margin (labor hours)',0.0,24.0,step=1.0,key='tol')
    st.divider()
    st.caption('Synthetic 2023–2025 data. Forecasts are planning estimates, not guaranteed outcomes.')
nav=st.navigation([
    st.Page('views/workforce_planning.py',title='Workforce Planning',icon=':material/calendar_month:',default=True),
    st.Page('views/staffing_decisions.py',title='Staffing Decisions',icon=':material/tune:'),
    st.Page('views/model_validation.py',title='Model Validation',icon=':material/query_stats:'),
])
nav.run()
