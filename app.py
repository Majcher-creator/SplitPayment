import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
from typing import List, Tuple, Dict
import io

# Database file path
DB_FILE = "data.db"

# Partner names
PARTNERS = ["W1", "W2", "W3"]

# Scenario definitions with share percentages
SCENARIOS = {
    "Scenario 1": {"W1": 40, "W2": 30, "W3": 30},
    "Scenario 2": {"W1": 50, "W2": 25, "W3": 25},
    "Scenario 3": {"W1": 33.33, "W2": 33.33, "W3": 33.34},
}

# Firm percentage (taken from total before partner distribution)
FIRM_PERCENTAGE = 3


def init_db():
    """Initialize the database with required tables."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create projects table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            date TEXT NOT NULL,
            scenario TEXT NOT NULL,
            value REAL NOT NULL,
            planned_days INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    
    # Create worklog table for attendance tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS worklog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            partner TEXT NOT NULL,
            present INTEGER NOT NULL,
            logged_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            UNIQUE(project_id, date, partner)
        )
    """)
    
    conn.commit()
    conn.close()


def get_db_connection():
    """Get a database connection."""
    return sqlite3.connect(DB_FILE)


def create_project(name: str, proj_date: str, scenario: str, value: float, planned_days: int) -> int:
    """Create a new project and return its ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    created_at = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO projects (name, date, scenario, value, planned_days, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, proj_date, scenario, value, planned_days, created_at))
    
    project_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return project_id


def get_all_projects() -> List[Tuple]:
    """Get all projects ordered by creation date descending."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, date, scenario, value, planned_days, created_at
        FROM projects
        ORDER BY created_at DESC
    """)
    
    projects = cursor.fetchall()
    conn.close()
    
    return projects


def get_project_by_id(project_id: int) -> Tuple:
    """Get a specific project by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, date, scenario, value, planned_days, created_at
        FROM projects
        WHERE id = ?
    """, (project_id,))
    
    project = cursor.fetchone()
    conn.close()
    
    return project


def log_attendance(project_id: int, log_date: str, partner: str, present: int):
    """Log attendance for a partner on a specific date. Last write wins."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    logged_at = datetime.now().isoformat()
    
    cursor.execute("""
        INSERT OR REPLACE INTO worklog (project_id, date, partner, present, logged_at)
        VALUES (?, ?, ?, ?, ?)
    """, (project_id, log_date, partner, present, logged_at))
    
    conn.commit()
    conn.close()


def get_worklog_for_project(project_id: int) -> List[Tuple]:
    """Get all worklog entries for a project."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, project_id, date, partner, present, logged_at
        FROM worklog
        WHERE project_id = ?
        ORDER BY date DESC, partner
    """, (project_id,))
    
    logs = cursor.fetchall()
    conn.close()
    
    return logs


def get_worked_days_by_partner(project_id: int) -> Dict[str, int]:
    """Get total worked days (present=1) for each partner in a project."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    worked_days = {partner: 0 for partner in PARTNERS}
    
    for partner in PARTNERS:
        cursor.execute("""
            SELECT COUNT(*) FROM worklog
            WHERE project_id = ? AND partner = ? AND present = 1
        """, (project_id, partner))
        
        count = cursor.fetchone()[0]
        worked_days[partner] = count
    
    conn.close()
    
    return worked_days


def calculate_payouts(project_id: int) -> Dict[str, any]:
    """Calculate payouts for a project based on worked days."""
    project = get_project_by_id(project_id)
    if not project:
        return {
            "error": "Project not found",
            "project_name": "",
            "total_value": 0,
            "firm_cut": 0,
            "distributable": 0,
            "planned_days": 0,
            "total_worked_days": 0,
            "payouts": {},
            "total_paid": 0,
            "remaining": 0,
            "over_plan": False
        }
    
    _, name, proj_date, scenario, total_value, planned_days, _ = project
    
    # Get worked days for each partner
    worked_days = get_worked_days_by_partner(project_id)
    
    # Get scenario shares
    shares = SCENARIOS[scenario]
    
    # Calculate firm cut
    firm_cut = total_value * (FIRM_PERCENTAGE / 100)
    distributable = total_value - firm_cut
    
    # Calculate payouts
    payouts = {}
    for partner in PARTNERS:
        share_pct = shares[partner] / 100
        days_worked = worked_days[partner]
        
        # Payout formula: share% * distributable / planned_days * worked_days
        if planned_days > 0:
            per_day_value = distributable / planned_days
            partner_per_day = share_pct * per_day_value
            payout = partner_per_day * days_worked
        else:
            payout = 0
        
        payouts[partner] = {
            "share_pct": shares[partner],
            "worked_days": days_worked,
            "payout": payout
        }
    
    total_paid = sum(p["payout"] for p in payouts.values())
    remaining = distributable - total_paid
    total_worked = sum(worked_days.values())
    
    return {
        "project_name": name,
        "total_value": total_value,
        "firm_cut": firm_cut,
        "distributable": distributable,
        "planned_days": planned_days,
        "total_worked_days": total_worked,
        "payouts": payouts,
        "total_paid": total_paid,
        "remaining": remaining,
        "over_plan": total_worked > planned_days
    }


def get_monthly_summary() -> pd.DataFrame:
    """Get monthly summary of projects."""
    conn = get_db_connection()
    
    query = """
        SELECT 
            strftime('%Y-%m', date) as month,
            COUNT(*) as project_count,
            SUM(value) as total_value,
            SUM(planned_days) as total_planned_days
        FROM projects
        GROUP BY strftime('%Y-%m', date)
        ORDER BY month DESC
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    return df


def get_yearly_summary() -> pd.DataFrame:
    """Get yearly summary of projects."""
    conn = get_db_connection()
    
    query = """
        SELECT 
            strftime('%Y', date) as year,
            COUNT(*) as project_count,
            SUM(value) as total_value,
            SUM(planned_days) as total_planned_days
        FROM projects
        GROUP BY strftime('%Y', date)
        ORDER BY year DESC
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    return df


def export_projects_csv() -> str:
    """Export all projects to CSV format."""
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM projects ORDER BY created_at DESC", conn)
    conn.close()
    
    return df.to_csv(index=False)


def export_worklog_csv() -> str:
    """Export worklog with project details to CSV format."""
    conn = get_db_connection()
    
    query = """
        SELECT 
            w.id,
            w.project_id,
            p.name as project_name,
            strftime('%Y-%m', p.date) as project_month,
            w.date,
            w.partner,
            w.present,
            w.logged_at
        FROM worklog w
        JOIN projects p ON w.project_id = p.id
        ORDER BY w.logged_at DESC
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    return df.to_csv(index=False)


def main():
    st.set_page_config(page_title="Project Settlement App", layout="wide")
    
    # Initialize database
    init_db()
    
    # Initialize session state
    if "current_project_id" not in st.session_state:
        st.session_state.current_project_id = None
    
    st.title("💰 Project Settlement & Time Tracking")
    
    # Sidebar for project management
    with st.sidebar:
        st.header("Project Management")
        
        # Create new project
        with st.expander("➕ Create New Project", expanded=False):
            with st.form("create_project_form"):
                proj_name = st.text_input("Project Name", placeholder="Enter project name")
                proj_date = st.date_input("Project Date", value=date.today())
                
                scenario = st.selectbox("Scenario", options=list(SCENARIOS.keys()))
                
                # Show scenario details
                st.caption(f"**{scenario} Distribution:**")
                for partner, share in SCENARIOS[scenario].items():
                    st.caption(f"  {partner}: {share}%")
                
                proj_value = st.number_input("Total Value ($)", min_value=0.0, value=1000.0, step=100.0)
                planned_days = st.number_input("Planned Days", min_value=1, value=10, step=1)
                
                submitted = st.form_submit_button("Create Project")
                
                if submitted:
                    if proj_name.strip():
                        project_id = create_project(
                            proj_name.strip(),
                            proj_date.isoformat(),
                            scenario,
                            proj_value,
                            planned_days
                        )
                        st.session_state.current_project_id = project_id
                        st.success(f"✅ Project '{proj_name}' created!")
                        st.rerun()
                    else:
                        st.error("Please enter a project name")
        
        # Select existing project
        st.subheader("📋 Recent Projects")
        projects = get_all_projects()
        
        if projects:
            project_options = {f"{p[1]} ({p[2]})": p[0] for p in projects}
            
            selected_project_label = st.selectbox(
                "Select Project",
                options=list(project_options.keys()),
                index=0 if st.session_state.current_project_id is None else 
                      list(project_options.values()).index(st.session_state.current_project_id) 
                      if st.session_state.current_project_id in project_options.values() else 0
            )
            
            if st.button("Load Selected Project"):
                st.session_state.current_project_id = project_options[selected_project_label]
                st.rerun()
        else:
            st.info("No projects yet. Create one above!")
    
    # Main content area
    if st.session_state.current_project_id:
        project = get_project_by_id(st.session_state.current_project_id)
        
        if project:
            _, proj_name, proj_date, scenario, value, planned_days, _ = project
            
            st.header(f"📊 Current Project: {proj_name}")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Value", f"${value:,.2f}")
            with col2:
                st.metric("Scenario", scenario)
            with col3:
                st.metric("Planned Days", planned_days)
            with col4:
                st.metric("Date", proj_date)
            
            st.divider()
            
            # Attendance Logging
            st.subheader("⏱️ Log Attendance")
            
            col_left, col_right = st.columns([1, 1])
            
            with col_left:
                with st.form("attendance_form"):
                    log_date = st.date_input("Date", value=date.today())
                    
                    st.write("**Partner Attendance:**")
                    attendance = {}
                    for partner in PARTNERS:
                        attendance[partner] = st.checkbox(f"{partner} - Present", value=True, key=f"attend_{partner}")
                    
                    log_submitted = st.form_submit_button("💾 Save Attendance")
                    
                    if log_submitted:
                        for partner, present in attendance.items():
                            log_attendance(
                                st.session_state.current_project_id,
                                log_date.isoformat(),
                                partner,
                                1 if present else 0
                            )
                        st.success(f"✅ Attendance logged for {log_date}")
                        st.rerun()
            
            with col_right:
                st.write("**Recent Attendance Logs:**")
                logs = get_worklog_for_project(st.session_state.current_project_id)
                
                if logs:
                    log_df = pd.DataFrame(logs, columns=["ID", "Project ID", "Date", "Partner", "Present", "Logged At"])
                    log_df["Status"] = log_df["Present"].apply(lambda x: "✅ Present" if x == 1 else "❌ Absent")
                    display_df = log_df[["Date", "Partner", "Status"]].head(10)
                    st.dataframe(display_df, hide_index=True, use_container_width=True)
                else:
                    st.info("No attendance logs yet")
            
            st.divider()
            
            # Payout Calculation
            st.subheader("💵 Payout Calculation")
            
            payout_data = calculate_payouts(st.session_state.current_project_id)
            
            if payout_data:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Firm Cut (3%)", f"${payout_data['firm_cut']:,.2f}")
                with col2:
                    st.metric("Distributable", f"${payout_data['distributable']:,.2f}")
                with col3:
                    st.metric("Total Paid", f"${payout_data['total_paid']:,.2f}")
                with col4:
                    st.metric("Remaining", f"${payout_data['remaining']:,.2f}")
                
                if payout_data['over_plan']:
                    st.warning(f"⚠️ Total worked days ({payout_data['total_worked_days']}) exceeds planned days ({payout_data['planned_days']})")
                
                # Payout table
                st.write("**Partner Payouts:**")
                payout_rows = []
                for partner in PARTNERS:
                    p_data = payout_data['payouts'][partner]
                    payout_rows.append({
                        "Partner": partner,
                        "Share %": f"{p_data['share_pct']:.2f}%",
                        "Worked Days": p_data['worked_days'],
                        "Payout": f"${p_data['payout']:,.2f}"
                    })
                
                payout_df = pd.DataFrame(payout_rows)
                st.dataframe(payout_df, hide_index=True, use_container_width=True)
    else:
        st.info("👈 Please create or select a project from the sidebar to get started!")
    
    st.divider()
    
    # Summaries and Exports
    st.header("📈 Summaries & Reports")
    
    tab1, tab2, tab3 = st.tabs(["Monthly Summary", "Yearly Summary", "Export Data"])
    
    with tab1:
        st.subheader("Monthly Summary")
        monthly_df = get_monthly_summary()
        if not monthly_df.empty:
            st.dataframe(monthly_df, hide_index=True, use_container_width=True)
        else:
            st.info("No data available")
    
    with tab2:
        st.subheader("Yearly Summary")
        yearly_df = get_yearly_summary()
        if not yearly_df.empty:
            st.dataframe(yearly_df, hide_index=True, use_container_width=True)
        else:
            st.info("No data available")
    
    with tab3:
        st.subheader("Export Data")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Projects Data**")
            projects_csv = export_projects_csv()
            st.download_button(
                label="📥 Download Projects CSV",
                data=projects_csv,
                file_name=f"projects_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        
        with col2:
            st.write("**Worklog Data**")
            worklog_csv = export_worklog_csv()
            st.download_button(
                label="📥 Download Worklog CSV",
                data=worklog_csv,
                file_name=f"worklog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    
    # Footer
    st.divider()
    st.caption("💡 **Tip:** Data is persisted in SQLite database (data.db)")


if __name__ == "__main__":
    main()
