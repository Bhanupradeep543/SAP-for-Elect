import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
from pathlib import Path
import uuid
import json

DB_FILE = "maintenance_history.db"
IMAGE_DIR = Path("maintenance_images")
IMAGE_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# DATABASE
# ============================================================

def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)


def initialize_database():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            maintenance_date TEXT NOT NULL,
            stage TEXT NOT NULL,
            equipment_name TEXT NOT NULL,
            order_number TEXT,
            work_carried_out TEXT,
            materials_consumed TEXT,
            image_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sap_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notification_date TEXT,
            equipment_name TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

    # --------------------------------------------------------
    # Migration for old maintenance database
    # --------------------------------------------------------

    cursor.execute("PRAGMA table_info(maintenance_records)")
    maintenance_columns = [row[1] for row in cursor.fetchall()]

    required_maintenance_columns = {
        "maintenance_date": "TEXT",
        "stage": "TEXT",
        "equipment_name": "TEXT",
        "order_number": "TEXT",
        "work_carried_out": "TEXT",
        "materials_consumed": "TEXT",
        "image_path": "TEXT"
    }

    for column, data_type in required_maintenance_columns.items():

        if column not in maintenance_columns:

            cursor.execute(
                f"ALTER TABLE maintenance_records ADD COLUMN {column} {data_type}"
            )

    conn.commit()

    # --------------------------------------------------------
    # Migration for old SAP database
    # --------------------------------------------------------

    cursor.execute("PRAGMA table_info(sap_notifications)")
    sap_columns = [row[1] for row in cursor.fetchall()]

    required_sap_columns = {
        "notification_date": "TEXT",
        "equipment_name": "TEXT",
        "description": "TEXT"
    }

    for column, data_type in required_sap_columns.items():

        if column not in sap_columns:

            cursor.execute(
                f"ALTER TABLE sap_notifications ADD COLUMN {column} {data_type}"
            )

    conn.commit()
    conn.close()


# ============================================================
# EQUIPMENT LIST
# ============================================================

def get_equipment_list():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT
            TRIM(equipment_name)
        FROM sap_notifications
        WHERE equipment_name IS NOT NULL
        AND TRIM(equipment_name) != ''
        ORDER BY TRIM(equipment_name)
    """)

    equipment_list = [
        row[0]
        for row in cursor.fetchall()
        if row[0]
    ]

    conn.close()

    return equipment_list


# ============================================================
# SAVE MAINTENANCE RECORD
# ============================================================

def save_record(
    maintenance_date,
    stage,
    equipment_name,
    order_number,
    work_carried_out,
    materials_consumed,
    image_path
):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO maintenance_records
        (
            maintenance_date,
            stage,
            equipment_name,
            order_number,
            work_carried_out,
            materials_consumed,
            image_path
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        maintenance_date,
        stage,
        equipment_name,
        order_number,
        work_carried_out,
        materials_consumed,
        image_path
    ))

    conn.commit()
    conn.close()


# ============================================================
# SAVE SAP DATA
# ============================================================

def save_sap_data(df, replace_existing=False):

    conn = get_connection()

    cursor = conn.cursor()

    if replace_existing:

        cursor.execute(
            "DELETE FROM sap_notifications"
        )

    inserted = 0

    for _, row in df.iterrows():

        equipment = str(
            row["equipment_name"]
        ).strip()

        notification_date = str(
            row["notification_date"]
        ).strip()

        description = str(
            row["description"]
        ).strip()

        if (
            not equipment
            or equipment.lower() == "nan"
        ):

            continue

        if (
            notification_date.lower()
            == "nan"
        ):

            notification_date = ""

        if (
            description.lower()
            == "nan"
        ):

            description = ""

        # ----------------------------------------------------
        # Prevent exact duplicate rows
        # ----------------------------------------------------

        cursor.execute("""
            SELECT COUNT(*)
            FROM sap_notifications
            WHERE equipment_name = ?
            AND notification_date = ?
            AND description = ?
        """, (
            equipment,
            notification_date,
            description
        ))

        duplicate = cursor.fetchone()[0]

        if duplicate == 0:

            cursor.execute("""
                INSERT INTO sap_notifications
                (
                    notification_date,
                    equipment_name,
                    description
                )
                VALUES (?, ?, ?)
            """, (
                notification_date,
                equipment,
                description
            ))

            inserted += 1

    conn.commit()
    conn.close()

    return inserted


# ============================================================
# AUTOMATIC COLUMN DETECTION
# ============================================================

def find_column(df, keyword):

    for column in df.columns:

        if keyword.lower() in str(column).strip().lower():

            return column

    return None


# ============================================================
# MAINTENANCE HISTORY
# ============================================================

def get_equipment_history(equipment_name):

    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT
            maintenance_date AS Date,
            stage AS Stage,
            equipment_name AS Equipment,
            order_number AS 'Order Number',
            work_carried_out AS 'Work Carried Out',
            materials_consumed AS 'Materials Consumed',
            image_path AS Image
        FROM maintenance_records
        WHERE TRIM(equipment_name) = TRIM(?)
        ORDER BY maintenance_date DESC, id DESC
    """, conn, params=(equipment_name,))

    conn.close()

    return df


# ============================================================
# SAP NOTIFICATION HISTORY
# ============================================================

def get_equipment_notifications(equipment_name):

    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT
            notification_date AS Date,
            description AS Notification
        FROM sap_notifications
        WHERE TRIM(equipment_name) = TRIM(?)
        ORDER BY notification_date DESC, id DESC
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
            maintenance_date AS Date,
            stage AS Stage,
            equipment_name AS Equipment,
            order_number AS 'Order Number',
            work_carried_out AS 'Work Carried Out',
            materials_consumed AS 'Materials Consumed',
            image_path AS Image
        FROM maintenance_records
        ORDER BY maintenance_date DESC, id DESC
    """, conn)

    conn.close()

    return df


# ============================================================
# ALL SAP NOTIFICATIONS
# ============================================================

def get_all_notifications():

    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT
            notification_date AS Date,
            equipment_name AS Equipment,
            description AS Notification
        FROM sap_notifications
        ORDER BY notification_date DESC, id DESC
    """, conn)

    conn.close()

    return df


# ============================================================
# IMAGE SAVE
# ============================================================

def save_uploaded_images(
    uploaded_images,
    equipment_name
):

    saved_images = []

    equipment_folder = (
        IMAGE_DIR /
        equipment_name.replace(" ", "_")
    )

    equipment_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    for uploaded_file in uploaded_images:

        unique_name = (
            f"{uuid.uuid4().hex[:8]}_"
            f"{Path(uploaded_file.name).name}"
        )

        image_path = (
            equipment_folder /
            unique_name
        )

        with open(
            image_path,
            "wb"
        ) as file:

            file.write(
                uploaded_file.getbuffer()
            )

        saved_images.append(
            str(image_path)
        )

    return saved_images


# ============================================================
# MATERIAL PARSER
# ============================================================

def parse_materials(material_string):

    if not material_string:

        return []

    try:

        return json.loads(
            material_string
        )

    except:

        return []


# ============================================================
# INITIALIZE DATABASE
# ============================================================

initialize_database()


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Maintenance Navigator",
    page_icon="🔧",
    layout="wide"
)


# ============================================================
# TITLE
# ============================================================

st.title("🔧 Maintenance Navigator")

st.caption(
    "Maintenance Engineer Decision Support System"
)


# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "📝 Maintenance Entry",
    "📚 Equipment History",
    "📊 All Maintenance Records",
    "📥 SAP Notification Upload"
])


# ============================================================
# TAB 1 - MAINTENANCE ENTRY
# ============================================================

with tab1:

    st.header("📝 Maintenance Entry")

    equipment_list = get_equipment_list()

    if not equipment_list:

        st.warning(
            "No equipment list is available."
        )

        st.info(
            "Please import the SAP Excel file "
            "from the SAP Notification Upload tab."
        )

    else:

        col1, col2 = st.columns(2)

        with col1:

            maintenance_date = st.date_input(
                "Maintenance Date",
                value=date.today()
            )

            stage = st.selectbox(
                "Stage",
                [
                    "Stage-I",
                    "Stage-II",
                    "Stage-III",
                    "Stage-IV",
                    "Auxiliary",
                    "Other"
                ]
            )

            equipment_name = st.selectbox(
                "Equipment Name",
                equipment_list,
                index=None,
                placeholder="Select Equipment"
            )

            order_number = st.text_input(
                "Order Number"
            )

        with col2:

            work_carried_out = st.text_area(
                "Work Carried Out",
                height=220
            )

        st.divider()

        # ----------------------------------------------------
        # MATERIALS
        # ----------------------------------------------------

        st.subheader(
            "🔩 Materials Consumed"
        )

        if "materials" not in st.session_state:

            st.session_state.materials = [
                {
                    "material": "",
                    "uom": "",
                    "qty": 0.0
                }
            ]

        for i in range(
            len(st.session_state.materials)
        ):

            col1, col2, col3, col4 = st.columns(
                [5, 2, 2, 1]
            )

            with col1:

                st.session_state.materials[i][
                    "material"
                ] = st.text_input(
                    "Material",
                    value=st.session_state.materials[i][
                        "material"
                    ],
                    key=f"material_{i}",
                    placeholder="Material"
                )

            with col2:

                st.session_state.materials[i][
                    "uom"
                ] = st.text_input(
                    "UOM",
                    value=st.session_state.materials[i][
                        "uom"
                    ],
                    key=f"uom_{i}",
                    placeholder="UOM"
                )

            with col3:

                st.session_state.materials[i][
                    "qty"
                ] = st.number_input(
                    "Qty",
                    min_value=0.0,
                    value=float(
                        st.session_state.materials[i][
                            "qty"
                        ]
                    ),
                    step=0.01,
                    key=f"qty_{i}"
                )

            with col4:

                if i > 0:

                    if st.button(
                        "❌",
                        key=f"delete_{i}"
                    ):

                        st.session_state.materials.pop(
                            i
                        )

                        st.rerun()

        if st.button(
            "➕ Add Material"
        ):

            st.session_state.materials.append({
                "material": "",
                "uom": "",
                "qty": 0.0
            })

            st.rerun()

        st.divider()

        # ----------------------------------------------------
        # IMAGES
        # ----------------------------------------------------

        uploaded_images = st.file_uploader(
            "📷 Upload Maintenance Images",
            type=[
                "jpg",
                "jpeg",
                "png"
            ],
            accept_multiple_files=True
        )

        st.divider()

        # ----------------------------------------------------
        # SAVE
        # ----------------------------------------------------

        if st.button(
            "💾 Save Maintenance Record",
            type="primary",
            use_container_width=True
        ):

            if not equipment_name:

                st.error(
                    "Please select Equipment Name."
                )

                st.stop()

            if not work_carried_out.strip():

                st.error(
                    "Please enter Work Carried Out."
                )

                st.stop()

            valid_materials = []

            for material in st.session_state.materials:

                material_name = (
                    material["material"].strip()
                )

                material_uom = (
                    material["uom"].strip()
                )

                material_qty = float(
                    material["qty"]
                )

                if (
                    material_name
                    or material_uom
                    or material_qty > 0
                ):

                    valid_materials.append({
                        "material": material_name,
                        "uom": material_uom,
                        "qty": material_qty
                    })

            saved_images = (
                save_uploaded_images(
                    uploaded_images,
                    equipment_name
                )
                if uploaded_images
                else []
            )

            save_record(
                str(maintenance_date),
                stage,
                equipment_name,
                order_number.strip(),
                work_carried_out.strip(),
                json.dumps(valid_materials),
                ";".join(saved_images)
            )

            st.success(
                "✅ Maintenance record saved successfully."
            )

            st.session_state.materials = [
                {
                    "material": "",
                    "uom": "",
                    "qty": 0.0
                }
            ]


# ============================================================
# TAB 2 - EQUIPMENT HISTORY
# ============================================================

with tab2:

    st.header(
        "📚 Equipment History"
    )

    # IMPORTANT:
    # Read directly from database every rerun

    equipment_list = get_equipment_list()

    if not equipment_list:

        st.warning(
            "No equipment list is available."
        )

        st.info(
            "Please import the SAP Excel file first."
        )

    else:

        selected_equipment = st.selectbox(
            "Select Equipment",
            equipment_list,
            key="history_equipment"
        )

        # ----------------------------------------------------
        # SAP NOTIFICATION HISTORY
        # ----------------------------------------------------

        st.subheader(
            "🔔 SAP Notification History"
        )

        sap_history = (
            get_equipment_notifications(
                selected_equipment
            )
        )

        if sap_history.empty:

            st.info(
                "No SAP notifications found "
                "for this equipment."
            )

        else:

            st.dataframe(
                sap_history,
                use_container_width=True,
                hide_index=True
            )

        st.divider()

        # ----------------------------------------------------
        # MAINTENANCE HISTORY
        # ----------------------------------------------------

        st.subheader(
            "🔧 Manual Maintenance History"
        )

        maintenance_history = (
            get_equipment_history(
                selected_equipment
            )
        )

        if maintenance_history.empty:

            st.info(
                "No manual maintenance records "
                "found for this equipment."
            )

        else:

            st.dataframe(
                maintenance_history.drop(
                    columns=["Image"]
                ),
                use_container_width=True,
                hide_index=True
            )

        # ----------------------------------------------------
        # MATERIAL HISTORY
        # ----------------------------------------------------

        if not maintenance_history.empty:

            st.divider()

            st.subheader(
                "🔩 Material Consumption History"
            )

            material_found = False

            for _, row in (
                maintenance_history.iterrows()
            ):

                materials = parse_materials(
                    row["Materials Consumed"]
                )

                if materials:

                    material_found = True

                    st.markdown(
                        f"**Date:** {row['Date']} "
                        f" | "
                        f"**Order:** {row['Order Number']}"
                    )

                    material_df = pd.DataFrame(
                        materials
                    )

                    st.dataframe(
                        material_df,
                        use_container_width=True,
                        hide_index=True
                    )

            if not material_found:

                st.info(
                    "No material consumption recorded."
                )

        # ----------------------------------------------------
        # IMAGES
        # ----------------------------------------------------

        if not maintenance_history.empty:

            st.divider()

            st.subheader(
                "📷 Maintenance Images"
            )

            images_found = False

            for _, row in (
                maintenance_history.iterrows()
            ):

                image_paths = row["Image"]

                if image_paths:

                    for image_path in (
                        image_paths.split(";")
                    ):

                        if (
                            image_path
                            and Path(
                                image_path
                            ).exists()
                        ):

                            images_found = True

                            st.image(
                                image_path,
                                caption=(
                                    f"{row['Date']} — "
                                    f"{selected_equipment}"
                                ),
                                width=400
                            )

            if not images_found:

                st.info(
                    "No maintenance images available."
                )


# ============================================================
# TAB 3 - ALL MAINTENANCE RECORDS
# ============================================================

with tab3:

    st.header(
        "📊 All Maintenance Records"
    )

    all_records = get_all_records()

    if all_records.empty:

        st.info(
            "No maintenance records available."
        )

    else:

        col1, col2, col3 = st.columns(3)

        with col1:

            stages = sorted(
                all_records[
                    "Stage"
                ]
                .dropna()
                .unique()
                .tolist()
            )

            selected_stage = st.selectbox(
                "Stage",
                ["All"] + stages
            )

        with col2:

            start_date = st.date_input(
                "From Date",
                value=date.today().replace(
                    day=1
                )
            )

        with col3:

            end_date = st.date_input(
                "To Date",
                value=date.today()
            )

        filtered = all_records.copy()

        if selected_stage != "All":

            filtered = filtered[
                filtered["Stage"]
                == selected_stage
            ]

        filtered["Date"] = pd.to_datetime(
            filtered["Date"],
            errors="coerce"
        )

        filtered = filtered[
            (
                filtered["Date"]
                >= pd.Timestamp(start_date)
            )
            &
            (
                filtered["Date"]
                <= pd.Timestamp(end_date)
            )
        ]

        st.dataframe(
            filtered.drop(
                columns=["Image"]
            ),
            use_container_width=True,
            hide_index=True
        )

        csv_data = (
            filtered
            .drop(columns=["Image"])
            .to_csv(index=False)
            .encode("utf-8")
        )

        st.download_button(
            "⬇️ Download Records",
            csv_data,
            "maintenance_records.csv",
            "text/csv"
        )


# ============================================================
# TAB 4 - SAP NOTIFICATION UPLOAD
# ============================================================

with tab4:

    st.header(
        "📥 SAP Notification Upload"
    )

    st.info(
        "Upload the SAP Excel file. "
        "The application will automatically identify "
        "Equipment, Description and Date columns."
    )

    uploaded_sap_file = st.file_uploader(
        "Upload SAP Excel File",
        type=[
            "xlsx",
            "xls"
        ],
        key="sap_excel"
    )

    if uploaded_sap_file:

        try:

            sap_df = pd.read_excel(
                uploaded_sap_file
            )

        except Exception:

            st.error(
                "Unable to read the Excel file."
            )

            st.stop()

        # ----------------------------------------------------
        # AUTOMATICALLY FIND REQUIRED COLUMNS
        # ----------------------------------------------------

        equipment_column = find_column(
            sap_df,
            "equipment"
        )

        description_column = find_column(
            sap_df,
            "description"
        )

        date_column = find_column(
            sap_df,
            "date"
        )

        if equipment_column is None:

            st.error(
                "Equipment column was not found."
            )

            st.stop()

        if description_column is None:

            st.error(
                "Description column was not found."
            )

            st.stop()

        if date_column is None:

            st.error(
                "Date column was not found."
            )

            st.stop()

        # ----------------------------------------------------
        # CREATE ONLY REQUIRED DATA
        # ----------------------------------------------------

        mapped_df = pd.DataFrame()

        mapped_df[
            "equipment_name"
        ] = (
            sap_df[equipment_column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        mapped_df[
            "notification_date"
        ] = (
            sap_df[date_column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        mapped_df[
            "description"
        ] = (
            sap_df[description_column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        # Remove invalid equipment rows

        mapped_df = mapped_df[
            mapped_df[
                "equipment_name"
            ] != ""
        ]

        mapped_df = mapped_df[
            mapped_df[
                "equipment_name"
            ].str.lower() != "nan"
        ]

        # ----------------------------------------------------
        # EQUIPMENT COUNT
        # ----------------------------------------------------

        unique_equipment = (
            mapped_df[
                "equipment_name"
            ]
            .drop_duplicates()
            .tolist()
        )

        st.success(
            f"Equipment identified: "
            f"{len(unique_equipment)}"
        )

        # ----------------------------------------------------
        # IMPORT MODE
        # ----------------------------------------------------

        import_mode = st.radio(
            "Import Mode",
            [
                "Add New Notifications",
                "Replace Existing SAP Notifications"
            ],
            horizontal=True
        )

        # ----------------------------------------------------
        # IMPORT
        # ----------------------------------------------------

        if st.button(
            "📥 Import SAP Excel",
            type="primary",
            use_container_width=True
        ):

            replace_existing = (
                import_mode
                ==
                "Replace Existing SAP Notifications"
            )

            inserted = save_sap_data(
                mapped_df,
                replace_existing
            )

            # ------------------------------------------------
            # VERIFY DATABASE AFTER IMPORT
            # ------------------------------------------------

            updated_equipment_list = (
                get_equipment_list()
            )

            st.success(
                f"✅ SAP data imported successfully."
            )

            st.success(
                f"🔧 {len(updated_equipment_list)} "
                f"equipments are now available."
            )

            st.success(
                f"🔔 {inserted} new notification "
                f"records added."
            )

            st.rerun()

    # --------------------------------------------------------
    # EXISTING SAP DATABASE
    # --------------------------------------------------------

    st.divider()

    existing_sap = (
        get_all_notifications()
    )

    current_equipment = (
        get_equipment_list()
    )

    if not existing_sap.empty:

        col1, col2 = st.columns(2)

        with col1:

            st.metric(
                "SAP Notifications",
                len(existing_sap)
            )

        with col2:

            st.metric(
                "Equipment",
                len(current_equipment)
            )

        st.dataframe(
            existing_sap,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "No SAP notification data imported yet."
        )


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title(
    "🔧 Maintenance Navigator"
)

current_equipment = get_equipment_list()

if current_equipment:

    st.sidebar.success(
        f"Equipment Master: "
        f"{len(current_equipment)}"
    )

else:

    st.sidebar.warning(
        "Equipment Master Not Loaded"
    )

st.sidebar.markdown(
    """
### Modules

• Maintenance Entry  
• Equipment History  
• SAP Notifications  
• Material Consumption  
• Maintenance Images  
• All Maintenance Records
"""
)
