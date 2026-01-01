# SplitPayment - Project Settlement & Time Tracking App

A Streamlit-based application for managing project settlements with time tracking and automated payout calculations using SQLite for data persistence.

## Features

- **Project Management**: Create and manage multiple projects with different scenarios
- **Time Tracking**: Log daily attendance for each partner (W1, W2, W3)
- **Automated Payouts**: Calculate payouts based on actual worked days and predefined share percentages
- **Multiple Scenarios**: Three different share distribution scenarios
- **Summaries**: Monthly and yearly project aggregates
- **Data Export**: CSV export for projects and worklog data
- **Persistent Storage**: SQLite database for reliable data storage

## Requirements

- Python >= 3.9
- Streamlit >= 1.28.0
- Pandas >= 2.0.0

## Installation & Setup

### Local Installation

1. Clone the repository:
```bash
git clone https://github.com/Majcher-creator/SplitPayment.git
cd SplitPayment
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

Or install manually:
```bash
pip install streamlit pandas
```

3. Run the application:
```bash
streamlit run app.py
```

4. Open your browser and navigate to `http://localhost:8501`

## Database Persistence

The application uses SQLite for data storage:

- **Database File**: `data.db` (created automatically on first run)
- **Tables**:
  - `projects`: Stores project information (name, date, scenario, value, planned days)
  - `worklog`: Stores daily attendance records (project_id, date, partner, present/absent)

### Hosting Considerations

When deploying to cloud platforms (Streamlit Cloud, Heroku, etc.):

- **File-based storage**: The `data.db` file will be recreated on each deployment unless you:
  - Bind a persistent volume to store the database file
  - Use an external database service (PostgreSQL, MySQL, etc.)
- **Development/Testing**: The SQLite file works perfectly for local development and testing
- **Production**: Consider using a proper database service for production deployments

## Usage Guide

### 1. Create a Project

1. Open the sidebar (left panel)
2. Expand "➕ Create New Project"
3. Fill in the form:
   - **Project Name**: Enter a descriptive name
   - **Project Date**: Select the project date
   - **Scenario**: Choose one of three scenarios (see below)
   - **Total Value**: Enter the project's total value in dollars
   - **Planned Days**: Enter the number of planned working days
4. Click "Create Project"

### 2. Select an Existing Project

1. In the sidebar, view the "📋 Recent Projects" list
2. Select a project from the dropdown
3. Click "Load Selected Project"

### 3. Log Attendance

1. With a project selected, go to the "⏱️ Log Attendance" section
2. Select the date for attendance logging
3. Check/uncheck boxes for each partner (W1, W2, W3) to mark them as Present or Absent
4. Click "💾 Save Attendance"
5. View recent logs in the table on the right

**Note**: Last write wins - if you log attendance for the same date and partner multiple times, the latest entry will be saved.

### 4. View Payouts

The payout calculation automatically updates based on logged attendance:

- **Firm Cut**: Automatically deducted (3% of total value)
- **Distributable Amount**: Total value minus firm cut
- **Partner Payouts**: Calculated using the formula:
  ```
  Payout = (Share % × Distributable Amount ÷ Planned Days) × Worked Days
  ```
- **Warnings**: You'll see a warning if total worked days exceed planned days

### 5. View Summaries

Navigate to the "📈 Summaries & Reports" section:

- **Monthly Summary**: Aggregated project count, total value, and planned days by month
- **Yearly Summary**: Aggregated project count, total value, and planned days by year

### 6. Export Data

In the "Export Data" tab:

- **Download Projects CSV**: Export all project records
- **Download Worklog CSV**: Export all attendance logs with project details and month information

## Share Distribution Scenarios

The application supports three predefined scenarios:

### Scenario 1
- **W1**: 40%
- **W2**: 30%
- **W3**: 30%
- **Total**: 100%

### Scenario 2
- **W1**: 50%
- **W2**: 25%
- **W3**: 25%
- **Total**: 100%

### Scenario 3
- **W1**: 33.33%
- **W2**: 33.33%
- **W3**: 33.34%
- **Total**: 100%

All scenarios include a 3% firm cut taken from the total value before partner distribution.

## Example Calculation

**Project Setup:**
- Total Value: $10,000
- Scenario: Scenario 1 (W1: 40%, W2: 30%, W3: 30%)
- Planned Days: 10

**Worked Days:**
- W1: 10 days
- W2: 8 days
- W3: 5 days

**Calculations:**
- Firm Cut (3%): $300
- Distributable: $9,700
- W1 Payout: 40% × $9,700 ÷ 10 × 10 = $3,880
- W2 Payout: 30% × $9,700 ÷ 10 × 8 = $2,328
- W3 Payout: 30% × $9,700 ÷ 10 × 5 = $1,455
- Total Paid: $7,663
- Remaining: $2,037

## Technical Details

### Architecture

- **Frontend**: Streamlit for interactive web interface
- **Backend**: Python with SQLite for data persistence
- **Data Processing**: Pandas for data manipulation and CSV exports

### Database Schema

**projects table:**
```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    date TEXT NOT NULL,
    scenario TEXT NOT NULL,
    value REAL NOT NULL,
    planned_days INTEGER NOT NULL,
    created_at TEXT NOT NULL
)
```

**worklog table:**
```sql
CREATE TABLE worklog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    partner TEXT NOT NULL,
    present INTEGER NOT NULL,
    logged_at TEXT NOT NULL,
    UNIQUE(project_id, date, partner),
    FOREIGN KEY (project_id) REFERENCES projects(id)
)
```

## Limitations

- **No Authentication**: This is a single-user application without authentication
- **No External Services**: All data is stored locally in SQLite
- **No Docker**: No containerization provided (can be added if needed)

## Troubleshooting

### Database Issues

If you encounter database errors:

1. Check if `data.db` file has proper permissions
2. Delete `data.db` to start fresh (will lose all data)
3. Ensure SQLite is available in your Python environment

### Streamlit Issues

If the app doesn't load:

1. Verify Streamlit is installed: `pip show streamlit`
2. Check Python version: `python --version` (should be >= 3.9)
3. Try clearing Streamlit cache: `streamlit cache clear`

## Contributing

This is a project settlement calculator application. To contribute:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is provided as-is for project settlement calculations.

## Support

For issues or questions, please open an issue on the GitHub repository.
