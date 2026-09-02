import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime
from pathlib import Path
import uuid
import json
import re

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "maintenance_history.db"
IMAGE_DIR = BASE_DIR / "maintenance_images"
OH_UPLOAD_DIR = BASE_DIR / "oh_records"

IMAGE_DIR.mkdir(exist_ok=True)
OH_UPLOAD_DIR.mkdir(exist_ok=True)

st.set_page_config(
    page_title="Maintenance Navigator",
    page_icon="🔧",
    layout="wide"
)

# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def initialize_database():

    conn = get_connection()
    cursor = conn.cursor()

    # --------------------------------------------------------
    # Equipment Master
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS equipment_master (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_name TEXT UNIQUE NOT NULL,
            created_at TEXT
        )
    """)

    # --------------------------------------------------------
    # Maintenance Records
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            maintenance_date TEXT,
            stage TEXT,
            maintenance_type TEXT,
            equipment_name TEXT,
            order_number TEXT,
            work_carried_out TEXT,
            materials_consumed TEXT,
            image_path TEXT,
            created_at TEXT
        )
    """)

    # --------------------------------------------------------
    # SAP Notifications
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sap_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notification_date TEXT,
            equipment_name TEXT,
            description TEXT,
            created_at TEXT
        )
    """)

    # --------------------------------------------------------
    # OH Records
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS oh_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            oh_date TEXT,
            equipment_name TEXT,
            order_number TEXT,
            description TEXT,
            file_path TEXT,
            created_at TEXT
        )
    """)

    # --------------------------------------------------------
    # Spare Master
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS spare_master (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spare_number TEXT,
            spare_description TEXT,
            uom TEXT,
            quantity REAL,
            created_at TEXT
        )
    """)

    # --------------------------------------------------------
    # Spare Equipment Mapping
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS spare_equipment_mapping (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spare_id INTEGER NOT NULL,
            equipment_name TEXT NOT NULL,
            created_at TEXT,
            FOREIGN KEY(spare_id) REFERENCES spare_master(id)
            ON DELETE CASCADE
        )
    """)

    # --------------------------------------------------------
    # Local Observations
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS local_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            observation_date TEXT,
            stage TEXT,
            equipment_name TEXT,
            defect_description TEXT,
            severity TEXT,
            created_at TEXT
        )
    """)

    # ========================================================
    # MIGRATION FOR EXISTING DATABASE
    # ========================================================

    def get_columns(table_name):

        cursor.execute(
            f"PRAGMA table_info({table_name})"
        )

        return [
            row[1]
            for row in cursor.fetchall()
        ]

    # --------------------------------------------------------
    # Maintenance migration
    # --------------------------------------------------------

    maintenance_columns = get_columns(
        "maintenance_records"
    )

    if "maintenance_type" not in maintenance_columns:

        cursor.execute("""
            ALTER TABLE maintenance_records
            ADD COLUMN maintenance_type TEXT
        """)

    if "materials_consumed" not in maintenance_columns:

        cursor.execute("""
            ALTER TABLE maintenance_records
            ADD COLUMN materials_consumed TEXT
        """)

    if "image_path" not in maintenance_columns:

        cursor.execute("""
            ALTER TABLE maintenance_records
            ADD COLUMN image_path TEXT
        """)

    if "created_at" not in maintenance_columns:

        cursor.execute("""
            ALTER TABLE maintenance_records
            ADD COLUMN created_at TEXT
        """)

    # --------------------------------------------------------
    # SAP migration
    # --------------------------------------------------------

    sap_columns = get_columns(
        "sap_notifications"
    )

    if "notification_date" not in sap_columns:

        cursor.execute("""
            ALTER TABLE sap_notifications
            ADD COLUMN notification_date TEXT
        """)

    if "equipment_name" not in sap_columns:

        cursor.execute("""
            ALTER TABLE sap_notifications
            ADD COLUMN equipment_name TEXT
        """)

    if "description" not in sap_columns:

        cursor.execute("""
            ALTER TABLE sap_notifications
            ADD COLUMN description TEXT
        """)

    if "created_at" not in sap_columns:

        cursor.execute("""
            ALTER TABLE sap_notifications
            ADD COLUMN created_at TEXT
        """)

    conn.commit()
    conn.close()


initialize_database()


# ============================================================
# COMMON FUNCTIONS
# ============================================================

def clean_text(value):

    if pd.isna(value):
        return ""

    return str(value).strip()


def find_column(df, keyword_list):

    if isinstance(keyword_list, str):
        keyword_list = [keyword_list]

    for column in df.columns:

        column_text = str(column).strip().lower()

        for keyword in keyword_list:

            if keyword.lower() in column_text:
                return column

    return None


# ============================================================
# EQUIPMENT MASTER
# ============================================================

def get_equipment_list():

    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT equipment_name
        FROM equipment_master
        ORDER BY equipment_name
    """, conn)

    conn.close()

    if df.empty:
        return []

    return (
        df["equipment_name"]
        .dropna()
        .astype(str)
        .tolist()
    )


# ============================================================
# SAP IMPORT
# ============================================================

def import_new_sap_data(
    equipment_list,
    notification_df
):

    conn = get_connection()

    try:

        cursor = conn.cursor()

        # ----------------------------------------------------
        # Completely replace equipment master
        # ----------------------------------------------------

        cursor.execute(
            "DELETE FROM equipment_master"
        )

        cleaned_equipment = []

        for equipment in equipment_list:

            equipment = clean_text(
                equipment
            )

            if (
                equipment
                and equipment not in cleaned_equipment
            ):

                cleaned_equipment.append(
                    equipment
                )

        for equipment in cleaned_equipment:

            cursor.execute("""
                INSERT INTO equipment_master
                (
                    equipment_name,
                    created_at
                )
                VALUES (?, ?)
            """, (
                equipment,
                datetime.now().isoformat()
            ))

        # ----------------------------------------------------
        # Completely replace SAP notifications
        # ----------------------------------------------------

        cursor.execute(
            "DELETE FROM sap_notifications"
        )

        for _, row in notification_df.iterrows():

            equipment = clean_text(
                row.get(
                    "equipment_name",
                    ""
                )
            )

            notification_date = clean_text(
                row.get(
                    "notification_date",
                    ""
                )
            )

            description = clean_text(
                row.get(
                    "description",
                    ""
                )
            )

            if not equipment:
                continue

            cursor.execute("""
                INSERT INTO sap_notifications
                (
                    notification_date,
                    equipment_name,
                    description,
                    created_at
                )
                VALUES (?, ?, ?, ?)
            """, (
                notification_date,
                equipment,
                description,
                datetime.now().isoformat()
            ))

        conn.commit()

        return (
            len(cleaned_equipment),
            len(notification_df)
        )

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


# ============================================================
# MAINTENANCE RECORD - SAVE
# ============================================================

def save_record(
    maintenance_date,
    stage,
    maintenance_type,
    equipment_name,
    order_number,
    work_carried_out,
    materials_consumed,
    image_paths
):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO maintenance_records
        (
            maintenance_date,
            stage,
            maintenance_type,
            equipment_name,
            order_number,
            work_carried_out,
            materials_consumed,
            image_path,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(maintenance_date),
        stage,
        maintenance_type,
        equipment_name,
        order_number,
        work_carried_out,
        json.dumps(materials_consumed),
        json.dumps(image_paths),
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


# ============================================================
# MAINTENANCE RECORD - UPDATE
# ============================================================

def update_maintenance_record(
    record_id,
    maintenance_date,
    stage,
    maintenance_type,
    equipment_name,
    order_number,
    work_carried_out,
    materials_consumed,
    image_paths
):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        UPDATE maintenance_records
        SET
            maintenance_date = ?,
            stage = ?,
            maintenance_type = ?,
            equipment_name = ?,
            order_number = ?,
            work_carried_out = ?,
            materials_consumed = ?,
            image_path = ?
        WHERE id = ?
    """, (
        str(maintenance_date),
        stage,
        maintenance_type,
        equipment_name,
        order_number,
        work_carried_out,
        json.dumps(materials_consumed),
        json.dumps(image_paths),
        record_id
    ))

    conn.commit()
    conn.close()


# ============================================================
# GET MAINTENANCE RECORD
# ============================================================

def get_maintenance_record(
    record_id
):

    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT *
        FROM maintenance_records
        WHERE id = ?
    """, conn, params=(record_id,))

    conn.close()

    if df.empty:
        return None

    return df.iloc[0].to_dict()


# ============================================================
# SAVE IMAGES
# ============================================================

def save_uploaded_images(
    uploaded_files,
    equipment_name
):

    if not uploaded_files:
        return []

    safe_equipment = re.sub(
        r"[^A-Za-z0-9_-]",
        "_",
        equipment_name
    )

    equipment_folder = (
        IMAGE_DIR / safe_equipment
    )

    equipment_folder.mkdir(
        exist_ok=True
    )

    saved_paths = []

    for uploaded_file in uploaded_files:

        extension = Path(
            uploaded_file.name
        ).suffix

        file_name = (
            datetime.now().strftime(
                "%Y%m%d_%H%M%S_"
            )
            + str(uuid.uuid4())[:8]
            + extension
        )

        file_path = (
            equipment_folder / file_name
        )

        with open(
            file_path,
            "wb"
        ) as f:

            f.write(
                uploaded_file.getbuffer()
            )

        saved_paths.append(
            str(file_path)
        )

    return saved_paths


# ============================================================
# EQUIPMENT HISTORY
# ============================================================

def get_equipment_history(
    equipment_name
):

    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT
            id,
            maintenance_date AS Date,
            stage AS Stage,
            maintenance_type AS Type,
            order_number AS "Order Number",
            work_carried_out AS "Work Carried Out"
        FROM maintenance_records
        WHERE equipment_name = ?
        ORDER BY maintenance_date DESC
    """, conn, params=(equipment_name,))

    conn.close()

    return df


# ============================================================
# SAP NOTIFICATIONS
# ============================================================

def get_equipment_notifications(
    equipment_name
):

    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT
            notification_date AS Date,
            description AS Notification
        FROM sap_notifications
        WHERE equipment_name = ?
        ORDER BY notification_date DESC
    """, conn, params=(equipment_name,))

    conn.close()

    return df


# ============================================================
# ALL MAINTENANCE RECORDS
# ============================================================

def get_all_records():

    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT
            id,
            maintenance_date AS Date,
            stage AS Stage,
            maintenance_type AS Type,
            equipment_name AS Equipment,
            order_number AS "Order Number",
            work_carried_out AS "Work Carried Out"
        FROM maintenance_records
        ORDER BY maintenance_date DESC
    """, conn)

    conn.close()

    return df


# ============================================================
# OH RECORDS
# ============================================================

def save_oh_records(df):

    equipment_col = find_column(
        df,
        ["equipment"]
    )

    date_col = find_column(
        df,
        ["date"]
    )

    description_col = find_column(
        df,
        ["description", "work"]
    )

    order_col = find_column(
        df,
        ["order"]
    )

    if equipment_col is None:

        raise ValueError(
            "Equipment column could not be identified."
        )

    if date_col is None:

        raise ValueError(
            "Date column could not be identified."
        )

    conn = get_connection()

    cursor = conn.cursor()

    inserted = 0

    for _, row in df.iterrows():

        equipment = clean_text(
            row[equipment_col]
        )

        oh_date = clean_text(
            row[date_col]
        )

        description = (
            clean_text(
                row[description_col]
            )
            if description_col
            else ""
        )

        order_number = (
            clean_text(
                row[order_col]
            )
            if order_col
            else ""
        )

        if not equipment:
            continue

        cursor.execute("""
            INSERT INTO oh_records
            (
                oh_date,
                equipment_name,
                order_number,
                description,
                file_path,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            oh_date,
            equipment,
            order_number,
            description,
            "",
            datetime.now().isoformat()
        ))

        inserted += 1

    conn.commit()
    conn.close()

    return inserted


def get_oh_records(
    equipment_name
):

    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT
            oh_date AS Date,
            order_number AS "Order Number",
            description AS Description
        FROM oh_records
        WHERE equipment_name = ?
        ORDER BY oh_date DESC
    """, conn, params=(equipment_name,))

    conn.close()

    return df


# ============================================================
# SPARE MASTER
# ============================================================

def upload_spare_master(df):

    spare_col = find_column(
        df,
        [
            "spare number",
            "material number",
            "material",
            "spare"
        ]
    )

    description_col = find_column(
        df,
        ["description"]
    )

    uom_col = find_column(
        df,
        ["uom", "unit"]
    )

    quantity_col = find_column(
        df,
        ["quantity", "qty"]
    )

    if spare_col is None:

        raise ValueError(
            "Spare/Material column could not be identified."
        )

    conn = get_connection()

    cursor = conn.cursor()

    inserted = 0

    for _, row in df.iterrows():

        spare_number = clean_text(
            row[spare_col]
        )

        spare_description = (
            clean_text(
                row[description_col]
            )
            if description_col
            else ""
        )

        uom = (
            clean_text(
                row[uom_col]
            )
            if uom_col
            else ""
        )

        quantity = 0

        if quantity_col:

            try:
                quantity = float(
                    row[quantity_col]
                )
            except:
                quantity = 0

        if not spare_number:
            continue

        cursor.execute("""
            INSERT INTO spare_master
            (
                spare_number,
                spare_description,
                uom,
                quantity,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            spare_number,
            spare_description,
            uom,
            quantity,
            datetime.now().isoformat()
        ))

        inserted += 1

    conn.commit()
    conn.close()

    return inserted


def get_spares():

    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT
            id,
            spare_number AS "Spare Number",
            spare_description AS Description,
            uom AS UOM,
            quantity AS Quantity
        FROM spare_master
        ORDER BY spare_number
    """, conn)

    conn.close()

    return df


def link_spare_to_equipment(
    spare_id,
    equipment_list
):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM spare_equipment_mapping
        WHERE spare_id = ?
    """, (spare_id,))

    for equipment in equipment_list:

        cursor.execute("""
            INSERT INTO spare_equipment_mapping
            (
                spare_id,
                equipment_name,
                created_at
            )
            VALUES (?, ?, ?)
        """, (
            spare_id,
            equipment,
            datetime.now().isoformat()
        ))

    conn.commit()
    conn.close()


def get_equipment_spares(
    equipment_name
):

    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT
            s.spare_number AS "Spare Number",
            s.spare_description AS Description,
            s.uom AS UOM,
            s.quantity AS Quantity
        FROM spare_master s
        INNER JOIN spare_equipment_mapping m
            ON s.id = m.spare_id
        WHERE m.equipment_name = ?
        ORDER BY s.spare_number
    """, conn, params=(equipment_name,))

    conn.close()

    return df


# ============================================================
# LOCAL OBSERVATIONS
# ============================================================

def save_local_observation(
    observation_date,
    stage,
    equipment_name,
    defect_description,
    severity
):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO local_observations
        (
            observation_date,
            stage,
            equipment_name,
            defect_description,
            severity,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        str(observation_date),
        stage,
        equipment_name,
        defect_description,
        severity,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


def get_local_observations(
    equipment_name
):

    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT
            observation_date AS Date,
            stage AS Stage,
            defect_description AS "Defect Description",
            severity AS Severity
        FROM local_observations
        WHERE equipment_name = ?
        ORDER BY observation_date DESC
    """, conn, params=(equipment_name,))

    conn.close()

    return df


# ============================================================
# SIDEBAR
# ============================================================

equipment_list = get_equipment_list()

st.sidebar.title(
    "🔧 Maintenance Navigator"
)

st.sidebar.info(
    f"Current Equipment Master: "
    f"{len(equipment_list)} equipment"
)


# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🛠 Maintenance Entry",
    "📋 Equipment History",
    "📊 All Maintenance Records",
    "📥 SAP Notification Upload",
    "🔄 OH Record Upload",
    "🔩 Spare Master",
    "🔎 Local Observations"
])


# ============================================================
# TAB 1 - MAINTENANCE ENTRY
# ============================================================

with tab1:

    st.header(
        "Maintenance Entry"
    )

    if not equipment_list:

        st.warning(
            "No equipment master is available. "
            "Please upload the SAP Excel first."
        )

    else:

        st.subheader(
            "Enter Maintenance Details"
        )

        maintenance_date = st.date_input(
            "Maintenance Date",
            value=date.today()
        )

        stage = st.selectbox(
            "Stage",
            [
                "Stage-1",
                "Stage-2",
                "Stage-3",
                "Other"
            ]
        )

        maintenance_type = st.selectbox(
            "Maintenance Type",
            [
                "Defect",
                "PM",
                "OH"
            ]
        )

        equipment_name = st.selectbox(
            "Equipment",
            equipment_list
        )

        order_number = st.text_input(
            "Order Number"
        )

        work_carried_out = st.text_area(
            "Work Carried Out"
        )

        st.subheader(
            "Materials Consumed"
        )

        if "materials" not in st.session_state:

            st.session_state.materials = [
                {
                    "Material": "",
                    "UOM": "",
                    "Qty": 0.0
                }
            ]

        for i in range(
            len(st.session_state.materials)
        ):

            col1, col2, col3, col4 = st.columns(
                [3, 2, 1.5, 1]
            )

            with col1:

                st.session_state.materials[i][
                    "Material"
                ] = st.text_input(
                    "Material",
                    value=st.session_state.materials[i][
                        "Material"
                    ],
                    key=f"material_{i}"
                )

            with col2:

                st.session_state.materials[i][
                    "UOM"
                ] = st.text_input(
                    "UOM",
                    value=st.session_state.materials[i][
                        "UOM"
                    ],
                    key=f"uom_{i}"
                )

            with col3:

                st.session_state.materials[i][
                    "Qty"
                ] = st.number_input(
                    "Qty",
                    min_value=0.0,
                    value=float(
                        st.session_state.materials[i][
                            "Qty"
                        ]
                    ),
                    key=f"qty_{i}"
                )

            with col4:

                if st.button(
                    "❌",
                    key=f"delete_material_{i}"
                ):

                    st.session_state.materials.pop(i)
                    st.rerun()

        if st.button(
            "➕ Add Material"
        ):

            st.session_state.materials.append({
                "Material": "",
                "UOM": "",
                "Qty": 0.0
            })

            st.rerun()

        uploaded_images = st.file_uploader(
            "Maintenance Images",
            type=[
                "jpg",
                "jpeg",
                "png"
            ],
            accept_multiple_files=True
        )

        if st.button(
            "💾 Save Maintenance Record",
            type="primary"
        ):

            if not work_carried_out.strip():

                st.error(
                    "Please enter the work carried out."
                )

            else:

                image_paths = save_uploaded_images(
                    uploaded_images,
                    equipment_name
                )

                save_record(
                    maintenance_date,
                    stage,
                    maintenance_type,
                    equipment_name,
                    order_number,
                    work_carried_out,
                    st.session_state.materials,
                    image_paths
                )

                st.session_state.materials = [
                    {
                        "Material": "",
                        "UOM": "",
                        "Qty": 0.0
                    }
                ]

                st.success(
                    "Maintenance record saved successfully."
                )

                st.rerun()


# ============================================================
# TAB 2 - EQUIPMENT HISTORY
# ============================================================

with tab2:

    st.header(
        "Equipment History"
    )

    equipment_list = get_equipment_list()

    if not equipment_list:

        st.warning(
            "No equipment list is available. "
            "Please upload SAP Excel."
        )

    else:

        selected_equipment = st.selectbox(
            "Select Equipment",
            equipment_list,
            key="history_equipment"
        )

        # ====================================================
        # MAINTENANCE HISTORY
        # ====================================================

        st.subheader(
            "🛠 Maintenance History"
        )

        history_df = get_equipment_history(
            selected_equipment
        )

        if history_df.empty:

            st.info(
                "No manual maintenance records available."
            )

        else:

            for _, row in history_df.iterrows():

                with st.container(
                    border=True
                ):

                    col1, col2, col3, col4, col5, col6 = st.columns(
                        [1.2, 1.2, 1.2, 1.5, 4, 1]
                    )

                    with col1:
                        st.write(
                            row["Date"]
                        )

                    with col2:
                        st.write(
                            row["Stage"]
                        )

                    with col3:
                        st.write(
                            row["Type"]
                        )

                    with col4:
                        st.write(
                            row["Order Number"]
                        )

                    with col5:
                        st.write(
                            row["Work Carried Out"]
                        )

                    with col6:

                        if st.button(
                            "✏️ Edit",
                            key=f"edit_{row['id']}"
                        ):

                            st.session_state.edit_record_id = int(
                                row["id"]
                            )

                            st.rerun()

        # ====================================================
        # EDIT MAINTENANCE RECORD
        # ====================================================

        if "edit_record_id" in st.session_state:

            record_id = (
                st.session_state.edit_record_id
            )

            record = get_maintenance_record(
                record_id
            )

            if record:

                st.divider()

                st.subheader(
                    f"✏️ Edit Maintenance Record #{record_id}"
                )

                existing_date = record.get(
                    "maintenance_date"
                )

                try:

                    existing_date = datetime.strptime(
                        str(existing_date),
                        "%Y-%m-%d"
                    ).date()

                except:

                    existing_date = date.today()

                edit_date = st.date_input(
                    "Maintenance Date",
                    value=existing_date,
                    key="edit_date"
                )

                stage_options = [
                    "Stage-1",
                    "Stage-2",
                    "Stage-3",
                    "Other"
                ]

                current_stage = (
                    record.get("stage")
                    or "Stage-1"
                )

                if current_stage not in stage_options:

                    stage_options.append(
                        current_stage
                    )

                edit_stage = st.selectbox(
                    "Stage",
                    stage_options,
                    index=stage_options.index(
                        current_stage
                    ),
                    key="edit_stage"
                )

                type_options = [
                    "Defect",
                    "PM",
                    "OH"
                ]

                current_type = (
                    record.get("maintenance_type")
                    or "Defect"
                )

                if current_type not in type_options:

                    type_options.append(
                        current_type
                    )

                edit_type = st.selectbox(
                    "Maintenance Type",
                    type_options,
                    index=type_options.index(
                        current_type
                    ),
                    key="edit_type"
                )

                equipment_options = (
                    get_equipment_list()
                )

                current_equipment = (
                    record.get("equipment_name")
                )

                if (
                    current_equipment
                    not in equipment_options
                ):

                    equipment_options.append(
                        current_equipment
                    )

                edit_equipment = st.selectbox(
                    "Equipment",
                    equipment_options,
                    index=equipment_options.index(
                        current_equipment
                    ),
                    key="edit_equipment"
                )

                edit_order = st.text_input(
                    "Order Number",
                    value=(
                        record.get(
                            "order_number"
                        )
                        or ""
                    ),
                    key="edit_order"
                )

                edit_work = st.text_area(
                    "Work Carried Out",
                    value=(
                        record.get(
                            "work_carried_out"
                        )
                        or ""
                    ),
                    key="edit_work"
                )

                st.subheader(
                    "Materials Consumed"
                )

                try:

                    existing_materials = json.loads(
                        record.get(
                            "materials_consumed"
                        )
                        or "[]"
                    )

                except:

                    existing_materials = []

                if "edit_materials" not in st.session_state:

                    st.session_state.edit_materials = (
                        existing_materials
                        if existing_materials
                        else [
                            {
                                "Material": "",
                                "UOM": "",
                                "Qty": 0.0
                            }
                        ]
                    )

                for i in range(
                    len(
                        st.session_state.edit_materials
                    )
                ):

                    c1, c2, c3, c4 = st.columns(
                        [3, 2, 1.5, 1]
                    )

                    with c1:

                        st.session_state.edit_materials[i][
                            "Material"
                        ] = st.text_input(
                            "Material",
                            value=st.session_state.edit_materials[i].get(
                                "Material",
                                ""
                            ),
                            key=f"edit_material_{record_id}_{i}"
                        )

                    with c2:

                        st.session_state.edit_materials[i][
                            "UOM"
                        ] = st.text_input(
                            "UOM",
                            value=st.session_state.edit_materials[i].get(
                                "UOM",
                                ""
                            ),
                            key=f"edit_uom_{record_id}_{i}"
                        )

                    with c3:

                        st.session_state.edit_materials[i][
                            "Qty"
                        ] = st.number_input(
                            "Qty",
                            min_value=0.0,
                            value=float(
                                st.session_state.edit_materials[i].get(
                                    "Qty",
                                    0
                                )
                            ),
                            key=f"edit_qty_{record_id}_{i}"
                        )

                    with c4:

                        if st.button(
                            "❌",
                            key=f"edit_delete_{record_id}_{i}"
                        ):

                            st.session_state.edit_materials.pop(i)
                            st.rerun()

                if st.button(
                    "➕ Add Material",
                    key=f"add_edit_material_{record_id}"
                ):

                    st.session_state.edit_materials.append({
                        "Material": "",
                        "UOM": "",
                        "Qty": 0.0
                    })

                    st.rerun()

                existing_images = []

                try:

                    existing_images = json.loads(
                        record.get(
                            "image_path"
                        )
                        or "[]"
                    )

                except:

                    existing_images = []

                if existing_images:

                    st.subheader(
                        "Existing Images"
                    )

                    for image_path in existing_images:

                        image_file = Path(
                            image_path
                        )

                        if image_file.exists():

                            st.image(
                                str(image_file),
                                width=250
                            )

                new_images = st.file_uploader(
                    "Add New Images",
                    type=[
                        "jpg",
                        "jpeg",
                        "png"
                    ],
                    accept_multiple_files=True,
                    key=f"edit_images_{record_id}"
                )

                col_save, col_cancel = st.columns(2)

                with col_save:

                    if st.button(
                        "💾 Update Record",
                        type="primary",
                        key=f"update_{record_id}"
                    ):

                        new_image_paths = (
                            save_uploaded_images(
                                new_images,
                                edit_equipment
                            )
                        )

                        final_images = (
                            existing_images
                            + new_image_paths
                        )

                        update_maintenance_record(
                            record_id,
                            edit_date,
                            edit_stage,
                            edit_type,
                            edit_equipment,
                            edit_order,
                            edit_work,
                            st.session_state.edit_materials,
                            final_images
                        )

                        st.success(
                            "Maintenance record updated successfully."
                        )

                        del st.session_state.edit_record_id

                        if "edit_materials" in st.session_state:

                            del st.session_state.edit_materials

                        st.rerun()

                with col_cancel:

                    if st.button(
                        "Cancel",
                        key=f"cancel_{record_id}"
                    ):

                        del st.session_state.edit_record_id

                        if "edit_materials" in st.session_state:

                            del st.session_state.edit_materials

                        st.rerun()

        # ====================================================
        # LOCAL OBSERVATIONS
        # ====================================================

        st.divider()

        st.subheader(
            "🔎 Local Observations"
        )

        observation_df = get_local_observations(
            selected_equipment
        )

        if observation_df.empty:

            st.info(
                "No local observations available for this equipment."
            )

        else:

            st.dataframe(
                observation_df,
                use_container_width=True,
                hide_index=True
            )

        # ====================================================
        # SAP NOTIFICATIONS
        # ====================================================

        st.divider()

        st.subheader(
            "📢 SAP Notifications"
        )

        notification_df = (
            get_equipment_notifications(
                selected_equipment
            )
        )

        if notification_df.empty:

            st.info(
                "No SAP notifications available."
            )

        else:

            st.dataframe(
                notification_df,
                use_container_width=True,
                hide_index=True
            )

        # ====================================================
        # OH RECORDS
        # ====================================================

        st.divider()

        st.subheader(
            "🔄 OH Records"
        )

        oh_df = get_oh_records(
            selected_equipment
        )

        if oh_df.empty:

            st.info(
                "No OH records available."
            )

        else:

            st.dataframe(
                oh_df,
                use_container_width=True,
                hide_index=True
            )

        # ====================================================
        # LINKED SPARES
        # ====================================================

        st.divider()

        st.subheader(
            "🔩 Linked Spares"
        )

        spare_df = get_equipment_spares(
            selected_equipment
        )

        if spare_df.empty:

            st.info(
                "No spares linked to this equipment."
            )

        else:

            st.dataframe(
                spare_df,
                use_container_width=True,
                hide_index=True
            )


# ============================================================
# TAB 3 - ALL MAINTENANCE RECORDS
# ============================================================

with tab3:

    st.header(
        "All Maintenance Records"
    )

    all_records = get_all_records()

    if all_records.empty:

        st.info(
            "No maintenance records available."
        )

    else:

        st.dataframe(
            all_records,
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# TAB 4 - SAP NOTIFICATION UPLOAD
# ============================================================

with tab4:

    st.header(
        "SAP Notification Upload"
    )

    st.info(
        "Uploading a new SAP Excel will completely replace "
        "the current Equipment Master and SAP Notification "
        "History. Existing manual maintenance records and "
        "local observations will NOT be deleted."
    )

    sap_file = st.file_uploader(
        "Upload SAP Notification Excel",
        type=[
            "xlsx",
            "xls"
        ],
        key="sap_upload"
    )

    if sap_file:

        try:

            df = pd.read_excel(
                sap_file
            )

            equipment_col = find_column(
                df,
                "equipment"
            )

            description_col = find_column(
                df,
                "description"
            )

            date_col = find_column(
                df,
                "date"
            )

            if equipment_col is None:

                st.error(
                    "Equipment column could not be identified."
                )

            elif description_col is None:

                st.error(
                    "Description column could not be identified."
                )

            elif date_col is None:

                st.error(
                    "Date column could not be identified."
                )

            else:

                notification_df = pd.DataFrame()

                notification_df[
                    "equipment_name"
                ] = df[equipment_col].apply(
                    clean_text
                )

                notification_df[
                    "notification_date"
                ] = df[date_col].apply(
                    clean_text
                )

                notification_df[
                    "description"
                ] = df[description_col].apply(
                    clean_text
                )

                notification_df = (
                    notification_df[
                        notification_df[
                            "equipment_name"
                        ] != ""
                    ]
                )

                equipment_list_new = sorted(
                    notification_df[
                        "equipment_name"
                    ]
                    .dropna()
                    .unique()
                    .tolist()
                )

                st.success(
                    f"Excel processed successfully. "
                    f"{len(equipment_list_new)} equipment identified."
                )

                if st.button(
                    "🔄 Replace Master With This Excel",
                    type="primary"
                ):

                    equipment_count, notification_count = (
                        import_new_sap_data(
                            equipment_list_new,
                            notification_df
                        )
                    )

                    if (
                        "history_equipment"
                        in st.session_state
                    ):

                        del st.session_state[
                            "history_equipment"
                        ]

                    st.success(
                        f"Equipment Master replaced successfully. "
                        f"{equipment_count} equipment and "
                        f"{notification_count} SAP notifications imported."
                    )

                    st.rerun()

        except Exception as e:

            st.error(
                f"Error processing Excel: {str(e)}"
            )


# ============================================================
# TAB 5 - OH RECORD UPLOAD
# ============================================================

with tab5:

    st.header(
        "OH Record Upload"
    )

    st.info(
        "Upload the OH Excel file. "
        "The application automatically identifies Equipment, "
        "Date, Description and Order columns."
    )

    oh_file = st.file_uploader(
        "Upload OH Excel",
        type=[
            "xlsx",
            "xls"
        ],
        key="oh_upload"
    )

    if oh_file:

        try:

            oh_df = pd.read_excel(
                oh_file
            )

            equipment_col = find_column(
                oh_df,
                "equipment"
            )

            date_col = find_column(
                oh_df,
                "date"
            )

            if equipment_col is None:

                st.error(
                    "Equipment column could not be identified."
                )

            elif date_col is None:

                st.error(
                    "Date column could not be identified."
                )

            else:

                if st.button(
                    "📥 Import OH Records",
                    type="primary"
                ):

                    count = save_oh_records(
                        oh_df
                    )

                    st.success(
                        f"{count} OH records imported successfully."
                    )

        except Exception as e:

            st.error(
                f"Error processing OH Excel: {str(e)}"
            )


# ============================================================
# TAB 6 - SPARE MASTER
# ============================================================

with tab6:

    st.header(
        "🔩 Spare Master"
    )

    st.subheader(
        "Upload Spare List"
    )

    st.info(
        "Upload your spare/material Excel file. "
        "The application will identify the spare/material "
        "number, description, UOM and quantity automatically."
    )

    spare_file = st.file_uploader(
        "Upload Spare List Excel",
        type=[
            "xlsx",
            "xls"
        ],
        key="spare_upload"
    )

    if spare_file:

        try:

            spare_excel_df = pd.read_excel(
                spare_file
            )

            if st.button(
                "📥 Import Spare List",
                type="primary"
            ):

                count = upload_spare_master(
                    spare_excel_df
                )

                st.success(
                    f"{count} spare records imported successfully."
                )

                st.rerun()

        except Exception as e:

            st.error(
                f"Error processing Spare Excel: {str(e)}"
            )

    st.divider()

    st.subheader(
        "Spare Master List"
    )

    spares_df = get_spares()

    if spares_df.empty:

        st.info(
            "No spare records available."
        )

    else:

        display_spares = spares_df.drop(
            columns=["id"]
        )

        st.dataframe(
            display_spares,
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        st.subheader(
            "Link Spare to Equipment"
        )

        spare_options = {}

        for _, row in spares_df.iterrows():

            label = (
                str(row["Spare Number"])
                + " - "
                + str(row["Description"])
            )

            spare_options[label] = int(
                row["id"]
            )

        selected_spare_label = st.selectbox(
            "Select Spare",
            list(spare_options.keys())
        )

        selected_spare_id = spare_options[
            selected_spare_label
        ]

        selected_equipment_for_spare = (
            st.multiselect(
                "Select Equipment",
                equipment_list
            )
        )

        if st.button(
            "🔗 Link Spare to Equipment",
            type="primary"
        ):

            if not selected_equipment_for_spare:

                st.error(
                    "Please select at least one equipment."
                )

            else:

                link_spare_to_equipment(
                    selected_spare_id,
                    selected_equipment_for_spare
                )

                st.success(
                    "Spare linked to selected equipment successfully."
                )

                st.rerun()


# ============================================================
# TAB 7 - LOCAL OBSERVATIONS
# ============================================================

with tab7:

    st.header(
        "🔎 Local Observation Entry"
    )

    st.info(
        "Enter field observations identified during "
        "inspection or maintenance activities."
    )

    equipment_list = get_equipment_list()

    if not equipment_list:

        st.warning(
            "No equipment master is available. "
            "Please upload the SAP Excel first."
        )

    else:

        observation_date = st.date_input(
            "Observation Date",
            value=date.today()
        )

        stage = st.selectbox(
            "Stage",
            [
                "Stage-1",
                "Stage-2",
                "Stage-3",
                "Other"
            ],
            key="observation_stage"
        )

        equipment_name = st.selectbox(
            "Equipment",
            equipment_list,
            key="observation_equipment"
        )

        defect_description = st.text_area(
            "Defect Description",
            placeholder=(
                "Enter the observed defect / "
                "abnormality..."
            ),
            key="observation_description"
        )

        severity = st.selectbox(
            "Severity",
            [
                "Low",
                "Medium",
                "High"
            ],
            key="observation_severity"
        )

        if st.button(
            "💾 Save Observation",
            type="primary"
        ):

            if not defect_description.strip():

                st.error(
                    "Please enter the defect description."
                )

            else:

                save_local_observation(
                    observation_date,
                    stage,
                    equipment_name,
                    defect_description,
                    severity
                )

                st.success(
                    "Local observation saved successfully."
                )

                st.rerun()
