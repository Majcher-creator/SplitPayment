import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
from typing import List, Tuple, Dict
import io
import json
import plotly.express as px

# Database file path
DB_FILE = "data.db"

# Default partner names (can be customized by users)
DEFAULT_PARTNERS = ["W1", "W2", "W3"]

# Scenario definitions with share percentages
SCENARIOS = {
    "Scenariusz 1": {"W1": 40, "W2": 30, "W3": 30},
    "Scenariusz 2": {"W1": 50, "W2": 25, "W3": 25},
    "Scenariusz 3": {"W1": 33.33, "W2": 33.33, "W3": 33.34},
}

# Firm percentage (taken from total before partner distribution)
FIRM_PERCENTAGE = 3

# Currency symbol
CURRENCY = "zł"


def init_db():
    """Inicjalizacja bazy danych z wymaganymi tabelami."""
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
    
    # Create users/partners table with share information
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            share_percentage REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    
    # Create scenarios table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scenarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            is_default INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    # Create scenario_shares table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scenario_shares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scenario_id INTEGER NOT NULL,
            user_name TEXT NOT NULL,
            share_percentage REAL NOT NULL,
            FOREIGN KEY (scenario_id) REFERENCES scenarios(id),
            UNIQUE(scenario_id, user_name)
        )
    """)
    
    # Create audit_log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            action TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            created_at TEXT NOT NULL
        )
    """)
    
    conn.commit()
    
    # Migrate hardcoded scenarios if scenarios table is empty
    migrate_hardcoded_scenarios(conn)
    
    conn.close()


def get_db_connection():
    """Get a database connection."""
    return sqlite3.connect(DB_FILE)


def create_project(name: str, proj_date: str, scenario: str, value: float, planned_days: int) -> int:
    """Tworzenie nowego projektu i zwrócenie jego ID."""
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


def update_project_days(project_id: int, planned_days: int):
    """Aktualizacja liczby planowanych dni projektu."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE projects
        SET planned_days = ?
        WHERE id = ?
    """, (planned_days, project_id))
    
    conn.commit()
    conn.close()


def update_project(project_id: int, name: str, proj_date: str, scenario: str, value: float, planned_days: int):
    """Aktualizacja pełnych danych projektu."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE projects
        SET name = ?, date = ?, scenario = ?, value = ?, planned_days = ?
        WHERE id = ?
    """, (name, proj_date, scenario, value, planned_days, project_id))
    
    conn.commit()
    conn.close()


def delete_project(project_id: int):
    """Usunięcie projektu i powiązanych danych."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Delete worklog entries first (foreign key constraint)
    cursor.execute("DELETE FROM worklog WHERE project_id = ?", (project_id,))
    
    # Delete the project
    cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    
    conn.commit()
    conn.close()


def get_all_projects() -> List[Tuple]:
    """Pobierz wszystkie projekty posortowane według daty utworzenia."""
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
    """Pobierz konkretny projekt po ID."""
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


# User management functions
def add_user(name: str, share_percentage: float = 0):
    """Dodaj nowego użytkownika/partnera."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    created_at = datetime.now().isoformat()
    try:
        cursor.execute("""
            INSERT INTO users (name, share_percentage, created_at)
            VALUES (?, ?, ?)
        """, (name, share_percentage, created_at))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def update_user(old_name: str, new_name: str, share_percentage: float):
    """Aktualizuj dane użytkownika/partnera."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE users
            SET name = ?, share_percentage = ?
            WHERE name = ?
        """, (new_name, share_percentage, old_name))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def get_all_users() -> List[str]:
    """Pobierz wszystkich użytkowników."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM users ORDER BY name")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    # If no users, return default partners
    if not users:
        return DEFAULT_PARTNERS
    
    return users


def get_all_users_with_shares() -> List[Tuple]:
    """Pobierz wszystkich użytkowników z ich udziałami."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT name, share_percentage FROM users ORDER BY name")
    users = cursor.fetchall()
    conn.close()
    
    return users


def delete_user(name: str):
    """Usuń użytkownika."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM users WHERE name = ?", (name,))
    conn.commit()
    conn.close()


# Scenario management functions
def migrate_hardcoded_scenarios(conn):
    """Migrate hardcoded scenarios to database on first run."""
    cursor = conn.cursor()
    
    # Check if scenarios already exist
    cursor.execute("SELECT COUNT(*) FROM scenarios")
    count = cursor.fetchone()[0]
    
    if count == 0:
        # Migrate hardcoded scenarios
        now = datetime.now().isoformat()
        
        for idx, (scenario_name, shares) in enumerate(SCENARIOS.items()):
            cursor.execute("""
                INSERT INTO scenarios (name, description, is_default, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (scenario_name, f"Zmigrowany scenariusz: {scenario_name}", 1 if idx == 0 else 0, now, now))
            
            scenario_id = cursor.lastrowid
            
            # Insert shares for this scenario
            for user_name, share_pct in shares.items():
                cursor.execute("""
                    INSERT INTO scenario_shares (scenario_id, user_name, share_percentage)
                    VALUES (?, ?, ?)
                """, (scenario_id, user_name, share_pct))
            
            # Log the migration
            log_audit(cursor, "scenario", scenario_id, "migrated", None, json.dumps(shares), now)
        
        conn.commit()


def log_audit(cursor, entity_type: str, entity_id: int, action: str, old_value: str, new_value: str, timestamp: str = None):
    """Log an audit entry."""
    if timestamp is None:
        timestamp = datetime.now().isoformat()
    
    cursor.execute("""
        INSERT INTO audit_log (entity_type, entity_id, action, old_value, new_value, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (entity_type, entity_id, action, old_value, new_value, timestamp))


def create_scenario(name: str, description: str = "", is_default: int = 0) -> int:
    """Create a new scenario and return its ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    
    try:
        # If setting as default, unset other defaults first
        if is_default:
            cursor.execute("UPDATE scenarios SET is_default = 0")
        
        cursor.execute("""
            INSERT INTO scenarios (name, description, is_default, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (name, description, is_default, now, now))
        
        scenario_id = cursor.lastrowid
        
        # Log the creation
        log_audit(cursor, "scenario", scenario_id, "created", None, json.dumps({"name": name, "description": description}), now)
        
        conn.commit()
        conn.close()
        return scenario_id
    except sqlite3.IntegrityError:
        conn.close()
        return -1


def update_scenario(scenario_id: int, name: str, description: str = "", is_default: int = 0):
    """Update a scenario."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get old values for audit
    cursor.execute("SELECT name, description, is_default FROM scenarios WHERE id = ?", (scenario_id,))
    old_data = cursor.fetchone()
    
    now = datetime.now().isoformat()
    
    try:
        # If setting as default, unset other defaults first
        if is_default:
            cursor.execute("UPDATE scenarios SET is_default = 0")
        
        cursor.execute("""
            UPDATE scenarios
            SET name = ?, description = ?, is_default = ?, updated_at = ?
            WHERE id = ?
        """, (name, description, is_default, now, scenario_id))
        
        # Log the update
        if old_data:
            old_value = json.dumps({"name": old_data[0], "description": old_data[1], "is_default": old_data[2]})
            new_value = json.dumps({"name": name, "description": description, "is_default": is_default})
            log_audit(cursor, "scenario", scenario_id, "updated", old_value, new_value, now)
        
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def delete_scenario(scenario_id: int):
    """Delete a scenario if it's not used in any projects."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if scenario is used in any projects
    cursor.execute("SELECT name FROM scenarios WHERE id = ?", (scenario_id,))
    scenario = cursor.fetchone()
    
    if not scenario:
        conn.close()
        return False, "Scenariusz nie istnieje"
    
    scenario_name = scenario[0]
    
    cursor.execute("SELECT COUNT(*) FROM projects WHERE scenario = ?", (scenario_name,))
    count = cursor.fetchone()[0]
    
    if count > 0:
        conn.close()
        return False, f"Nie można usunąć scenariusza używanego w {count} projektach"
    
    # Get scenario data for audit
    cursor.execute("SELECT name, description FROM scenarios WHERE id = ?", (scenario_id,))
    old_data = cursor.fetchone()
    
    # Delete scenario shares first
    cursor.execute("DELETE FROM scenario_shares WHERE scenario_id = ?", (scenario_id,))
    
    # Delete the scenario
    cursor.execute("DELETE FROM scenarios WHERE id = ?", (scenario_id,))
    
    # Log the deletion
    now = datetime.now().isoformat()
    if old_data:
        old_value = json.dumps({"name": old_data[0], "description": old_data[1]})
        log_audit(cursor, "scenario", scenario_id, "deleted", old_value, None, now)
    
    conn.commit()
    conn.close()
    
    return True, "Scenariusz usunięty pomyślnie"


def get_all_scenarios() -> List[Tuple]:
    """Get all scenarios."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, description, is_default, created_at, updated_at
        FROM scenarios
        ORDER BY is_default DESC, name ASC
    """)
    
    scenarios = cursor.fetchall()
    conn.close()
    
    return scenarios


def get_scenario_by_id(scenario_id: int) -> Tuple:
    """Get a specific scenario by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, description, is_default, created_at, updated_at
        FROM scenarios
        WHERE id = ?
    """, (scenario_id,))
    
    scenario = cursor.fetchone()
    conn.close()
    
    return scenario


def get_scenario_by_name(name: str) -> Tuple:
    """Get a specific scenario by name."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, description, is_default, created_at, updated_at
        FROM scenarios
        WHERE name = ?
    """, (name,))
    
    scenario = cursor.fetchone()
    conn.close()
    
    return scenario


def set_scenario_shares(scenario_id: int, shares: Dict[str, float]):
    """Set shares for a scenario. Replaces existing shares."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get old shares for audit
    cursor.execute("SELECT user_name, share_percentage FROM scenario_shares WHERE scenario_id = ?", (scenario_id,))
    old_shares = {row[0]: row[1] for row in cursor.fetchall()}
    
    # Delete existing shares
    cursor.execute("DELETE FROM scenario_shares WHERE scenario_id = ?", (scenario_id,))
    
    # Insert new shares
    for user_name, share_pct in shares.items():
        cursor.execute("""
            INSERT INTO scenario_shares (scenario_id, user_name, share_percentage)
            VALUES (?, ?, ?)
        """, (scenario_id, user_name, share_pct))
    
    # Update scenario updated_at
    now = datetime.now().isoformat()
    cursor.execute("UPDATE scenarios SET updated_at = ? WHERE id = ?", (now, scenario_id))
    
    # Log the update
    log_audit(cursor, "scenario_shares", scenario_id, "updated", json.dumps(old_shares), json.dumps(shares), now)
    
    conn.commit()
    conn.close()


def get_scenario_shares(scenario_id: int) -> Dict[str, float]:
    """Get shares for a scenario."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT user_name, share_percentage
        FROM scenario_shares
        WHERE scenario_id = ?
    """, (scenario_id,))
    
    shares = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    
    return shares


def validate_shares(shares: Dict[str, float]) -> Tuple[bool, str, float]:
    """Validate that shares sum to 100%. Returns (is_valid, message, total)."""
    total = sum(shares.values())
    
    if abs(total - 100.0) < 0.01:  # Allow small floating point errors
        return True, "Suma udziałów wynosi 100%", total
    elif total < 100.0:
        diff = 100.0 - total
        return False, f"Suma udziałów jest za mała o {diff:.2f}%", total
    else:
        diff = total - 100.0
        return False, f"Suma udziałów jest za duża o {diff:.2f}%", total


def get_audit_log(entity_type: str = None, entity_id: int = None, limit: int = 50) -> List[Tuple]:
    """Get audit log entries."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT id, entity_type, entity_id, action, old_value, new_value, created_at FROM audit_log"
    params = []
    
    conditions = []
    if entity_type:
        conditions.append("entity_type = ?")
        params.append(entity_type)
    if entity_id is not None:
        conditions.append("entity_id = ?")
        params.append(entity_id)
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    logs = cursor.fetchall()
    conn.close()
    
    return logs


def export_scenarios_json() -> str:
    """Export all scenarios to JSON format."""
    scenarios = get_all_scenarios()
    
    export_data = []
    for scenario in scenarios:
        scenario_id, name, description, is_default, created_at, updated_at = scenario
        shares = get_scenario_shares(scenario_id)
        
        export_data.append({
            "name": name,
            "description": description,
            "is_default": bool(is_default),
            "shares": shares
        })
    
    return json.dumps(export_data, indent=2, ensure_ascii=False)


def import_scenarios_json(json_data: str) -> Tuple[bool, str]:
    """Import scenarios from JSON format."""
    try:
        scenarios_data = json.loads(json_data)
        
        imported_count = 0
        for scenario_data in scenarios_data:
            name = scenario_data.get("name")
            description = scenario_data.get("description", "")
            is_default = 1 if scenario_data.get("is_default", False) else 0
            shares = scenario_data.get("shares", {})
            
            # Check if scenario already exists
            existing = get_scenario_by_name(name)
            
            if existing:
                # Update existing scenario
                scenario_id = existing[0]
                update_scenario(scenario_id, name, description, is_default)
            else:
                # Create new scenario
                scenario_id = create_scenario(name, description, is_default)
                
                if scenario_id == -1:
                    continue
            
            # Set shares
            set_scenario_shares(scenario_id, shares)
            imported_count += 1
        
        return True, f"Zaimportowano {imported_count} scenariuszy"
    except Exception as e:
        return False, f"Błąd importu: {str(e)}"


def log_attendance(project_id: int, log_date: str, partner: str, present: int):
    """Rejestrowanie obecności partnera w określonym dniu. Ostatni zapis nadpisuje poprzedni."""
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
    """Pobierz wszystkie wpisy dziennika pracy dla projektu."""
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


def get_worked_days_by_partner(project_id: int, partners: List[str]) -> Dict[str, int]:
    """Pobierz całkowitą liczbę przepracowanych dni (obecność=1) dla każdego partnera w projekcie."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    worked_days = {partner: 0 for partner in partners}
    
    for partner in partners:
        cursor.execute("""
            SELECT COUNT(*) FROM worklog
            WHERE project_id = ? AND partner = ? AND present = 1
        """, (project_id, partner))
        
        count = cursor.fetchone()[0]
        worked_days[partner] = count
    
    conn.close()
    
    return worked_days


def calculate_payouts(project_id: int, partners: List[str]) -> Dict[str, any]:
    """Obliczanie wypłat dla projektu na podstawie przepracowanych dni."""
    project = get_project_by_id(project_id)
    if not project:
        return {
            "error": "Nie znaleziono projektu",
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
    worked_days = get_worked_days_by_partner(project_id, partners)
    
    # Get partner shares from scenario in database
    scenario_data = get_scenario_by_name(scenario)
    partner_shares = {}
    
    if scenario_data:
        # Use dynamic shares from database
        scenario_id = scenario_data[0]
        partner_shares = get_scenario_shares(scenario_id)
    else:
        # Fallback to hardcoded scenarios if scenario not found in database (backward compatibility)
        shares = SCENARIOS.get(scenario, {})
        partner_shares = shares
    
    # Calculate firm cut
    firm_cut = total_value * (FIRM_PERCENTAGE / 100)
    distributable = total_value - firm_cut
    
    # Calculate payouts
    payouts = {}
    for partner in partners:
        # Get partner's share percentage
        share_pct_value = partner_shares.get(partner, 0)
        
        if share_pct_value > 0:
            share_pct = share_pct_value / 100
            days_worked = worked_days.get(partner, 0)
            
            # Payout formula: share% * distributable / planned_days * worked_days
            if planned_days > 0:
                per_day_value = distributable / planned_days
                partner_per_day = share_pct * per_day_value
                payout = partner_per_day * days_worked
            else:
                payout = 0
            
            payouts[partner] = {
                "share_pct": share_pct_value,
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
    """Pobierz miesięczne podsumowanie projektów."""
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
    """Pobierz roczne podsumowanie projektów."""
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
    """Eksport wszystkich projektów do formatu CSV."""
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM projects ORDER BY created_at DESC", conn)
    conn.close()
    
    return df.to_csv(index=False)


def export_worklog_csv() -> str:
    """Eksport dziennika pracy ze szczegółami projektu do formatu CSV."""
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
    st.set_page_config(page_title="System Rozliczeń Projektów", layout="wide")
    
    # Initialize database
    init_db()
    
    # Initialize session state
    if "current_project_id" not in st.session_state:
        st.session_state.current_project_id = None
    
    st.title("💰 System Rozliczeń Projektów i Śledzenia Czasu")
    
    # Get current users list
    partners = get_all_users()
    
    # Create tabs for main sections
    tab_projects, tab_scenarios, tab_users = st.tabs(["Projekty", "Zarządzanie Scenariuszami", "Zarządzanie Użytkownikami"])
    
    with tab_users:
        st.header("👥 Zarządzanie Użytkownikami/Partnerami")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("Dodaj nowego partnera")
            with st.form("add_user_form"):
                new_user_name = st.text_input("Nazwa partnera", placeholder="np. W4, Jan Kowalski")
                new_user_share = st.number_input("Udział (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.01)
                add_user_btn = st.form_submit_button("➕ Dodaj partnera")
                
                if add_user_btn:
                    if new_user_name.strip():
                        if add_user(new_user_name.strip(), new_user_share):
                            st.success(f"✅ Dodano partnera: {new_user_name} ({new_user_share}%)")
                            st.rerun()
                        else:
                            st.error("❌ Partner o tej nazwie już istnieje")
                    else:
                        st.error("Proszę podać nazwę partnera")
        
        with col2:
            st.subheader("Aktualni partnerzy")
            users_with_shares = get_all_users_with_shares()
            if users_with_shares:
                for user_name, user_share in users_with_shares:
                    with st.expander(f"👤 {user_name} ({user_share}%)"):
                        with st.form(f"edit_user_{user_name}"):
                            edited_name = st.text_input("Nazwa", value=user_name, key=f"name_{user_name}")
                            edited_share = st.number_input("Udział (%)", min_value=0.0, max_value=100.0, value=float(user_share), step=0.01, key=f"share_{user_name}")
                            
                            col_update, col_delete = st.columns(2)
                            with col_update:
                                if st.form_submit_button("💾 Aktualizuj"):
                                    if update_user(user_name, edited_name.strip(), edited_share):
                                        st.success(f"✅ Zaktualizowano partnera")
                                        st.rerun()
                                    else:
                                        st.error("❌ Błąd aktualizacji (może istnieć partner o tej nazwie)")
                            with col_delete:
                                if st.form_submit_button("🗑️ Usuń"):
                                    delete_user(user_name)
                                    st.success(f"✅ Usunięto partnera {user_name}")
                                    st.rerun()
            elif partners:
                # Show default partners without shares
                for user in partners:
                    st.write(f"👤 {user} (domyślny)")
            else:
                st.info("Brak zdefiniowanych partnerów. Dodaj pierwszego!")
    
    with tab_scenarios:
        st.header("🎯 Zarządzanie Scenariuszami")
        
        # Search and filter
        col_search, col_new = st.columns([3, 1])
        with col_search:
            search_query = st.text_input("🔍 Szukaj scenariusza", placeholder="Wpisz nazwę scenariusza...", key="search_scenario")
        with col_new:
            st.write("")  # Spacing
            st.write("")  # Spacing
            show_create = st.button("➕ Utwórz Nowy Scenariusz", use_container_width=True)
        
        # Create new scenario form
        if show_create or ("show_create_scenario" in st.session_state and st.session_state.show_create_scenario):
            st.session_state.show_create_scenario = show_create
            
            with st.expander("➕ Tworzenie Nowego Scenariusza", expanded=True):
                with st.form("create_scenario_form"):
                    new_scenario_name = st.text_input("Nazwa scenariusza *", placeholder="np. Scenariusz 4")
                    new_scenario_desc = st.text_area("Opis", placeholder="Opcjonalny opis scenariusza")
                    new_is_default = st.checkbox("Ustaw jako domyślny")
                    
                    st.subheader("Udziały partnerów")
                    st.caption("Przypisz procenty do każdego partnera. Suma musi wynosić 100%.")
                    
                    new_shares = {}
                    for partner in partners:
                        share_val = st.number_input(f"{partner} (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.01, key=f"new_share_{partner}")
                        new_shares[partner] = share_val
                    
                    # Show validation
                    is_valid, msg, total = validate_shares(new_shares)
                    if is_valid:
                        st.success(f"✅ {msg}")
                    else:
                        st.warning(f"⚠️ {msg} (Aktualna suma: {total:.2f}%)")
                    
                    col_submit, col_cancel = st.columns(2)
                    with col_submit:
                        if st.form_submit_button("💾 Utwórz Scenariusz", disabled=not is_valid):
                            if new_scenario_name.strip():
                                scenario_id = create_scenario(new_scenario_name.strip(), new_scenario_desc, 1 if new_is_default else 0)
                                if scenario_id != -1:
                                    set_scenario_shares(scenario_id, new_shares)
                                    st.success(f"✅ Utworzono scenariusz '{new_scenario_name}'")
                                    st.session_state.show_create_scenario = False
                                    st.rerun()
                                else:
                                    st.error("❌ Scenariusz o tej nazwie już istnieje")
                            else:
                                st.error("Proszę podać nazwę scenariusza")
                    with col_cancel:
                        if st.form_submit_button("❌ Anuluj"):
                            st.session_state.show_create_scenario = False
                            st.rerun()
        
        st.divider()
        
        # Display existing scenarios
        st.subheader("📋 Istniejące Scenariusze")
        
        scenarios = get_all_scenarios()
        
        # Filter by search query
        if search_query:
            scenarios = [s for s in scenarios if search_query.lower() in s[1].lower()]
        
        if scenarios:
            for scenario in scenarios:
                scenario_id, scenario_name, description, is_default, created_at, updated_at = scenario
                shares = get_scenario_shares(scenario_id)
                
                # Validate shares
                is_valid, validation_msg, total = validate_shares(shares)
                
                # Display scenario card
                default_badge = "⭐ " if is_default else ""
                validation_icon = "✅" if is_valid else "⚠️"
                
                with st.expander(f"{default_badge}{scenario_name} {validation_icon}", expanded=False):
                    col_info, col_viz = st.columns([1, 1])
                    
                    with col_info:
                        st.write(f"**Opis:** {description if description else 'Brak opisu'}")
                        st.write(f"**Status:** {validation_msg}")
                        st.write(f"**Utworzono:** {created_at[:10]}")
                        st.write(f"**Zaktualizowano:** {updated_at[:10]}")
                        
                        st.write("**Udziały:**")
                        for partner, share in shares.items():
                            st.write(f"  • {partner}: {share:.2f}%")
                    
                    with col_viz:
                        # Pie chart visualization
                        if shares:
                            fig = px.pie(
                                values=list(shares.values()),
                                names=list(shares.keys()),
                                title=f"Podział w {scenario_name}",
                                hole=0.3
                            )
                            fig.update_traces(textposition='inside', textinfo='percent+label')
                            st.plotly_chart(fig, use_container_width=True)
                    
                    st.divider()
                    
                    # Edit form
                    with st.form(f"edit_scenario_{scenario_id}"):
                        st.subheader("✏️ Edytuj Scenariusz")
                        
                        edit_name = st.text_input("Nazwa", value=scenario_name, key=f"edit_name_{scenario_id}")
                        edit_desc = st.text_area("Opis", value=description, key=f"edit_desc_{scenario_id}")
                        edit_is_default = st.checkbox("Ustaw jako domyślny", value=bool(is_default), key=f"edit_default_{scenario_id}")
                        
                        st.subheader("Udziały partnerów")
                        edit_shares = {}
                        for partner in partners:
                            current_share = shares.get(partner, 0.0)
                            share_val = st.number_input(f"{partner} (%)", min_value=0.0, max_value=100.0, value=float(current_share), step=0.01, key=f"edit_share_{scenario_id}_{partner}")
                            edit_shares[partner] = share_val
                        
                        # Show validation
                        edit_is_valid, edit_msg, edit_total = validate_shares(edit_shares)
                        if edit_is_valid:
                            st.success(f"✅ {edit_msg}")
                        else:
                            st.warning(f"⚠️ {edit_msg} (Aktualna suma: {edit_total:.2f}%)")
                        
                        col_update, col_delete = st.columns(2)
                        with col_update:
                            if st.form_submit_button("💾 Zapisz Zmiany", disabled=not edit_is_valid):
                                if update_scenario(scenario_id, edit_name.strip(), edit_desc, 1 if edit_is_default else 0):
                                    set_scenario_shares(scenario_id, edit_shares)
                                    st.success("✅ Scenariusz zaktualizowany!")
                                    st.rerun()
                                else:
                                    st.error("❌ Błąd aktualizacji (może istnieć scenariusz o tej nazwie)")
                        
                        with col_delete:
                            if st.form_submit_button("🗑️ Usuń Scenariusz", type="secondary"):
                                success, message = delete_scenario(scenario_id)
                                if success:
                                    st.success(f"✅ {message}")
                                    st.rerun()
                                else:
                                    st.error(f"❌ {message}")
                    
                    # Show audit log for this scenario
                    with st.expander("📜 Historia Zmian"):
                        audit_logs = get_audit_log(entity_type="scenario", entity_id=scenario_id, limit=20)
                        share_logs = get_audit_log(entity_type="scenario_shares", entity_id=scenario_id, limit=20)
                        
                        all_logs = sorted(audit_logs + share_logs, key=lambda x: x[6], reverse=True)
                        
                        if all_logs:
                            for log in all_logs:
                                log_id, entity_type, entity_id, action, old_value, new_value, created_at = log
                                st.caption(f"**{created_at[:19]}** - {action.upper()} ({entity_type})")
                                if old_value:
                                    st.caption(f"  Stara wartość: {old_value}")
                                if new_value:
                                    st.caption(f"  Nowa wartość: {new_value}")
                        else:
                            st.info("Brak historii zmian")
        else:
            if search_query:
                st.info(f"Nie znaleziono scenariuszy pasujących do '{search_query}'")
            else:
                st.info("Brak scenariuszy. Utwórz pierwszy scenariusz powyżej!")
        
        st.divider()
        
        # Import/Export section
        st.subheader("📤 Import/Export Scenariuszy")
        
        col_exp, col_imp = st.columns(2)
        
        with col_exp:
            st.write("**Eksport do JSON**")
            if st.button("📥 Generuj JSON", use_container_width=True):
                json_data = export_scenarios_json()
                st.download_button(
                    label="📥 Pobierz JSON",
                    data=json_data,
                    file_name=f"scenariusze_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    use_container_width=True
                )
        
        with col_imp:
            st.write("**Import z JSON**")
            uploaded_file = st.file_uploader("Wybierz plik JSON", type=["json"], key="import_scenarios")
            if uploaded_file is not None:
                json_data = uploaded_file.read().decode("utf-8")
                if st.button("📤 Importuj", use_container_width=True):
                    success, message = import_scenarios_json(json_data)
                    if success:
                        st.success(f"✅ {message}")
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
    
    
    with tab_projects:
        # Sidebar for project management
        with st.sidebar:
            st.header("Zarządzanie Projektami")
        
            # Create new project
            with st.expander("➕ Utwórz Nowy Projekt", expanded=False):
                with st.form("create_project_form"):
                    proj_name = st.text_input("Nazwa Projektu", placeholder="Wprowadź nazwę projektu")
                    proj_date = st.date_input("Data Projektu", value=date.today())
                    
                    # Get scenarios from database
                    db_scenarios = get_all_scenarios()
                    scenario_names = [s[1] for s in db_scenarios]
                    
                    # Fallback to hardcoded if no scenarios in database
                    if not scenario_names:
                        scenario_names = list(SCENARIOS.keys())
                    
                    scenario = st.selectbox("Scenariusz", options=scenario_names)
                    
                    # Show scenario details
                    st.caption(f"**{scenario} - Podział:**")
                    
                    # Get shares from database or fallback to hardcoded
                    scenario_data = get_scenario_by_name(scenario)
                    if scenario_data:
                        shares = get_scenario_shares(scenario_data[0])
                    else:
                        shares = SCENARIOS.get(scenario, {})
                    
                    for partner, share in shares.items():
                        st.caption(f"  {partner}: {share}%")
                    
                    proj_value = st.number_input(f"Wartość Całkowita ({CURRENCY})", min_value=0.0, value=1000.0, step=100.0)
                    planned_days = st.number_input("Planowane Dni", min_value=1, value=10, step=1)
                    
                    submitted = st.form_submit_button("Utwórz Projekt")
                    
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
                            st.success(f"✅ Utworzono projekt '{proj_name}'!")
                            st.rerun()
                        else:
                            st.error("Proszę wprowadzić nazwę projektu")
            
            # Select existing project
            st.subheader("📋 Ostatnie Projekty")
            projects = get_all_projects()
            
            if projects:
                project_options = {f"{p[1]} ({p[2]})": p[0] for p in projects}
                
                selected_project_label = st.selectbox(
                    "Wybierz Projekt",
                    options=list(project_options.keys()),
                    index=0 if st.session_state.current_project_id is None else 
                          list(project_options.values()).index(st.session_state.current_project_id) 
                          if st.session_state.current_project_id in project_options.values() else 0
                )
                
                if st.button("Wczytaj Wybrany Projekt"):
                    st.session_state.current_project_id = project_options[selected_project_label]
                    st.rerun()
            else:
                st.info("Brak projektów. Utwórz nowy powyżej!")
    
        # Main content area
        if st.session_state.current_project_id:
            project = get_project_by_id(st.session_state.current_project_id)
            
            if project:
                _, proj_name, proj_date, scenario, value, planned_days, _ = project
                
                st.header(f"📊 Aktualny Projekt: {proj_name}")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Wartość Całkowita", f"{value:,.2f} {CURRENCY}")
                with col2:
                    st.metric("Scenariusz", scenario)
                with col3:
                    # Editable planned days
                    st.metric("Planowane Dni", planned_days)
                with col4:
                    st.metric("Data", proj_date)
                
                # Add edit and delete project functionality
                col_edit, col_delete = st.columns(2)
                
                with col_edit:
                    with st.expander("✏️ Edytuj projekt"):
                        with st.form("edit_project_form"):
                            edit_name = st.text_input("Nazwa projektu", value=proj_name)
                            edit_date = st.date_input("Data projektu", value=datetime.fromisoformat(proj_date).date())
                            
                            # Get scenarios from database
                            db_scenarios = get_all_scenarios()
                            scenario_names = [s[1] for s in db_scenarios]
                            
                            # Fallback to hardcoded if no scenarios in database
                            if not scenario_names:
                                scenario_names = list(SCENARIOS.keys())
                            
                            # Find current scenario index
                            try:
                                scenario_idx = scenario_names.index(scenario)
                            except ValueError:
                                scenario_idx = 0
                            
                            edit_scenario = st.selectbox("Scenariusz", options=scenario_names, index=scenario_idx)
                            edit_value = st.number_input(f"Wartość całkowita ({CURRENCY})", min_value=0.0, value=float(value), step=100.0)
                            edit_days = st.number_input("Planowane dni", min_value=1, value=planned_days, step=1)
                            
                            if st.form_submit_button("💾 Zapisz zmiany"):
                                update_project(
                                    st.session_state.current_project_id,
                                    edit_name.strip(),
                                    edit_date.isoformat(),
                                    edit_scenario,
                                    edit_value,
                                    edit_days
                                )
                                st.success("✅ Projekt zaktualizowany!")
                                st.rerun()
                
                with col_delete:
                    with st.expander("🗑️ Usuń projekt"):
                        st.warning("⚠️ Ta operacja jest nieodwracalna i usunie projekt wraz ze wszystkimi wpisami obecności!")
                        with st.form("delete_project_form"):
                            confirm_text = st.text_input("Wpisz 'USUŃ' aby potwierdzić:", placeholder="USUŃ")
                            if st.form_submit_button("🗑️ Usuń projekt"):
                                if confirm_text == "USUŃ":
                                    delete_project(st.session_state.current_project_id)
                                    st.session_state.current_project_id = None
                                    st.success("✅ Projekt został usunięty")
                                    st.rerun()
                                else:
                                    st.error("Nieprawidłowe potwierdzenie")
                
                st.divider()
                
                # Attendance Logging
                st.subheader("⏱️ Rejestrowanie Obecności")
                
                col_left, col_right = st.columns([1, 1])
                
                with col_left:
                    with st.form("attendance_form"):
                        log_date = st.date_input("Data", value=date.today())
                        
                        st.write("**Obecność Partnerów:**")
                        attendance = {}
                        for partner in partners:
                            attendance[partner] = st.checkbox(f"{partner} - Obecny", value=True, key=f"attend_{partner}")
                        
                        log_submitted = st.form_submit_button("💾 Zapisz Obecność")
                        
                        if log_submitted:
                            for partner, present in attendance.items():
                                log_attendance(
                                    st.session_state.current_project_id,
                                    log_date.isoformat(),
                                    partner,
                                    1 if present else 0
                                )
                            st.success(f"✅ Zapisano obecność dla {log_date}")
                            st.rerun()
                
                with col_right:
                    st.write("**Ostatnie Wpisy Obecności:**")
                    logs = get_worklog_for_project(st.session_state.current_project_id)
                    
                    if logs:
                        log_df = pd.DataFrame(logs, columns=["ID", "ID Projektu", "Data", "Partner", "Obecny", "Zapisano"])
                        log_df["Status"] = log_df["Obecny"].apply(lambda x: "✅ Obecny" if x == 1 else "❌ Nieobecny")
                        display_df = log_df[["Data", "Partner", "Status"]].head(10)
                        st.dataframe(display_df, hide_index=True, width='stretch')
                    else:
                        st.info("Brak wpisów obecności")
                
                st.divider()
                
                # Payout Calculation
                st.subheader("💵 Obliczanie Wypłat")
                
                payout_data = calculate_payouts(st.session_state.current_project_id, partners)
                
                if payout_data:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Opłata Firmy (3%)", f"{payout_data['firm_cut']:,.2f} {CURRENCY}")
                    with col2:
                        st.metric("Do Podziału", f"{payout_data['distributable']:,.2f} {CURRENCY}")
                    with col3:
                        st.metric("Całkowicie Wypłacone", f"{payout_data['total_paid']:,.2f} {CURRENCY}")
                    with col4:
                        st.metric("Pozostało", f"{payout_data['remaining']:,.2f} {CURRENCY}")
                    
                    if payout_data['over_plan']:
                        st.warning(f"⚠️ Całkowita liczba przepracowanych dni ({payout_data['total_worked_days']}) przekracza planowane dni ({payout_data['planned_days']})")
                    
                    # Payout table
                    st.write("**Wypłaty dla Partnerów:**")
                    payout_rows = []
                    for partner in partners:
                        if partner in payout_data['payouts']:
                            p_data = payout_data['payouts'][partner]
                            payout_rows.append({
                                "Partner": partner,
                                "Udział %": f"{p_data['share_pct']:.2f}%",
                                "Przepracowane Dni": p_data['worked_days'],
                                "Wypłata": f"{p_data['payout']:,.2f} {CURRENCY}"
                            })
                    
                    payout_df = pd.DataFrame(payout_rows)
                    st.dataframe(payout_df, hide_index=True, width='stretch')
        else:
            st.info("👈 Proszę utworzyć lub wybrać projekt z paska bocznego, aby rozpocząć!")
        
        st.divider()
        
        # Summaries and Exports
        st.header("📈 Podsumowania i Raporty")
        
        tab1, tab2, tab3 = st.tabs(["Podsumowanie Miesięczne", "Podsumowanie Roczne", "Eksport Danych"])
        
        with tab1:
            st.subheader("Podsumowanie Miesięczne")
            monthly_df = get_monthly_summary()
            if not monthly_df.empty:
                # Rename columns to Polish
                monthly_df.columns = ['Miesiąc', 'Liczba Projektów', f'Całkowita Wartość ({CURRENCY})', 'Całkowite Planowane Dni']
                st.dataframe(monthly_df, hide_index=True, width='stretch')
            else:
                st.info("Brak dostępnych danych")
        
        with tab2:
            st.subheader("Podsumowanie Roczne")
            yearly_df = get_yearly_summary()
            if not yearly_df.empty:
                # Rename columns to Polish
                yearly_df.columns = ['Rok', 'Liczba Projektów', f'Całkowita Wartość ({CURRENCY})', 'Całkowite Planowane Dni']
                st.dataframe(yearly_df, hide_index=True, width='stretch')
            else:
                st.info("Brak dostępnych danych")
        
        with tab3:
            st.subheader("Eksport Danych")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Dane Projektów**")
                projects_csv = export_projects_csv()
                st.download_button(
                    label="📥 Pobierz CSV Projektów",
                    data=projects_csv,
                    file_name=f"projekty_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            
            with col2:
                st.write("**Dane Dziennika Pracy**")
                worklog_csv = export_worklog_csv()
                st.download_button(
                    label="📥 Pobierz CSV Dziennika",
                    data=worklog_csv,
                    file_name=f"dziennik_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        
        # Footer
        st.divider()
        st.caption("💡 **Wskazówka:** Dane są zapisywane w bazie danych SQLite (data.db)")


if __name__ == "__main__":
    main()
