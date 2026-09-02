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
# DATABASE CONNECTION
# ============================================================

def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

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
            raw_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

    # --------------------------------------------------------
    # Automatic database migration
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

    cursor.execute("PRAGMA table_info(sap_notifications)")
    sap_columns = [row[1] for row in cursor.fetchall()]

    required_sap_columns = {
        "notification_date": "TEXT",
        "equipment_name": "TEXT",
        "description": "TEXT",
        "raw_data": "TEXT"
    }

    for column, data_type in required_sap_columns.items():

        if column not in sap_columns:

            cursor.execute(
                f"ALTER TABLE sap_notifications ADD COLUMN {column} {data_type}"
            )

    conn.commit()
    conn.close()


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

    cursor.execute(
        """
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
        """,
        (
            maintenance_date,
            stage,
            equipment_name,
            order_number,
            work_carried_out,
            materials_consumed,
            image_path
        )
    )

    conn.commit()
    conn.close()


# ============================================================
# SAVE SAP NOTIFICATIONS
# ============================================================

def save_sap_notifications(df, mode="append"):

    conn = get_connection()
    cursor = conn.cursor()

    if mode == "replace":

        cursor.execute("DELETE FROM sap_notifications")

    for _, row in df.iterrows():

        notification_date = str(
            row.get("notification_date", "")
        ).strip()

        equipment_name = str(
            row.get("equipment_name", "")
        ).strip().upper()

        description = str(
            row.get("description", "")
        ).strip()

        raw_data = json.dumps(
            row.to_dict(),
            default=str
        )

        # Avoid duplicate notification records
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM sap_notifications
            WHERE notification_date = ?
            AND equipment_name = ?
            AND description = ?
            """,
            (
                notification_date,
                equipment_name,
                description
            )
        )

        exists = cursor.fetchone()[0]

        if exists == 0:

            cursor.execute(
                """
                INSERT INTO sap_notifications
                (
                    notification_date,
                    equipment_name,
                    description,
                    raw_data
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    notification_date,
                    equipment_name,
                    description,
                    raw_data
                )
            )

    conn.commit()
    conn.close()


# ============================================================
# GET ALL MAINTENANCE RECORDS
# ============================================================

def get_all_records():

    conn = get_connection()

    df = pd.read_sql_query(
        """
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
        """,
        conn
    )

    conn.close()

    return df


# ============================================================
# GET EQUIPMENT MAINTENANCE HISTORY
# ============================================================

def get_equipment_history(equipment_name):

    conn = get_connection()

    df = pd.read_sql_query(
        """
        SELECT
            maintenance_date AS Date,
            stage AS Stage,
            equipment_name AS Equipment,
            order_number AS 'Order Number',
            work_carried_out AS 'Work Carried Out',
            materials_consumed AS 'Materials Consumed',
            image_path AS Image
        FROM maintenance_records
        WHERE UPPER(TRIM(equipment_name)) =
              UPPER(TRIM(?))
        ORDER BY maintenance_date DESC, id DESC
        """,
        conn,
        params=(equipment_name,)
    )

    conn.close()

    return df


# ============================================================
# GET ALL SAP NOTIFICATIONS
# ============================================================

def get_all_notifications():

    conn = get_connection()

    df = pd.read_sql_query(
        """
        SELECT
            notification_date AS Date,
            equipment_name AS Equipment,
            description AS Notification
        FROM sap_notifications
        ORDER BY notification_date DESC, id DESC
        """,
        conn
    )

    conn.close()

    return df


# ============================================================
# GET EQUIPMENT SAP NOTIFICATIONS
# ============================================================

def get_equipment_notifications(equipment_name):

    conn = get_connection()

    df = pd.read_sql_query(
        """
        SELECT
            notification_date AS Date,
            description AS Notification
        FROM sap_notifications
        WHERE UPPER(TRIM(equipment_name)) =
              UPPER(TRIM(?))
        ORDER BY notification_date DESC, id DESC
        """,
        conn,
        params=(equipment_name,)
    )

    conn.close()

    return df


# ============================================================
# GET MASTER EQUIPMENT LIST
# ============================================================

def get_equipment_list():

    conn = get_connection()

    df = pd.read_sql_query(
        """
        SELECT DISTINCT
            UPPER(TRIM(equipment_name)) AS Equipment
        FROM sap_notifications
        WHERE equipment_name IS NOT NULL
        AND TRIM(equipment_name) != ''
        ORDER BY Equipment
        """,
        conn
    )

    conn.close()

    if df.empty:

        return []

    return df["Equipment"].tolist()


# ============================================================
# FIND COLUMN AUTOMATICALLY
# ============================================================

def find_column(df, keyword):

    matching_columns = [
        col
        for col in df.columns
        if keyword.lower() in str(col).lower()
    ]

    if matching_columns:

        return matching_columns[0]

    return None


# ============================================================
# PARSE MATERIALS
# ============================================================

def parse_materials(material_string):

    if not material_string:

        return []

    try:

        return json.loads(material_string)

    except (json.JSONDecodeError, TypeError):

        return []


# ============================================================
# SAVE IMAGES
# ============================================================

def save_uploaded_images(uploaded_images, equipment_name):

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

        image_path = equipment_folder / unique_name

        with open(image_path, "wb") as file:

            file.write(
                uploaded_file.getbuffer()
            )

        saved_images.append(
            str(image_path)
        )

    return saved_images


# ============================================================
# INITIALIZE DATABASE
# ============================================================

initialize_database()


# ============================================================
# PAGE CONFIGURATION
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
    "Equipment-wise maintenance records and SAP notification history"
)


# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "📝 Maintenance Entry",
        "📚 Equipment History",
        "📊 All Maintenance Records",
        "📥 SAP Notification Upload"
    ]
)


# ============================================================
# GET CURRENT MASTER EQUIPMENT LIST
# ============================================================

equipment_list = get_equipment_list()


# ============================================================
# TAB 1 - MAINTENANCE ENTRY
# ============================================================

with tab1:

    st.header("📝 Maintenance Entry")

    equipment_list = get_equipment_list()

    if not equipment_list:

        st.warning(
            "⚠️ No equipment list is available."
        )

        st.info(
            "Please upload the SAP Excel file first "
            "from the '📥 SAP Notification Upload' tab."
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
                "Order Number",
                placeholder="Example: 4500123456"
            )

        with col2:

            work_carried_out = st.text_area(
                "Work Carried Out",
                placeholder=(
                    "Describe the maintenance work "
                    "carried out..."
                ),
                height=220
            )

        st.divider()

        # ----------------------------------------------------
        # MATERIAL CONSUMPTION
        # ----------------------------------------------------

        st.subheader("🔩 Material Consumed")

        if "materials" not in st.session_state:

            st.session_state.materials = [
                {
                    "material": "",
                    "uom": "",
                    "qty": 0.0
                }
            ]

        col1, col2, col3, col4 = st.columns(
            [5, 2, 2, 1]
        )

        with col1:

            st.markdown("**Material**")

        with col2:

            st.markdown("**UOM**")

        with col3:

            st.markdown("**Qty**")

        with col4:

            st.markdown("**Action**")

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
                    label_visibility="collapsed",
                    placeholder="Material description"
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
                    label_visibility="collapsed",
                    placeholder="Nos / Kg / Mtr"
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
                    key=f"qty_{i}",
                    label_visibility="collapsed"
                )

            with col4:

                if i > 0:

                    if st.button(
                        "❌",
                        key=f"delete_material_{i}"
                    ):

                        st.session_state.materials.pop(i)

                        st.rerun()

        if st.button(
            "➕ Add Material",
            key="add_material"
        ):

            st.session_state.materials.append(
                {
                    "material": "",
                    "uom": "",
                    "qty": 0.0
                }
            )

            st.rerun()

        st.divider()

        # ----------------------------------------------------
        # IMAGE UPLOAD
        # ----------------------------------------------------

        uploaded_images = st.file_uploader(
            "📷 Upload Equipment / Maintenance Images",
            type=[
                "jpg",
                "jpeg",
                "png"
            ],
            accept_multiple_files=True
        )

        st.divider()

        # ----------------------------------------------------
        # SAVE MAINTENANCE RECORD
        # ----------------------------------------------------

        if st.button(
            "💾 Save Maintenance Record",
            type="primary",
            use_container_width=True
        ):

            if not equipment_name:

                st.error(
                    "Please select the Equipment Name."
                )

                st.stop()

            if not work_carried_out.strip():

                st.error(
                    "Please enter the Work Carried Out details."
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

                    if not material_name:

                        st.error(
                            "Please enter Material name."
                        )

                        st.stop()

                    if not material_uom:

                        st.error(
                            f"Please enter UOM for "
                            f"{material_name}."
                        )

                        st.stop()

                    if material_qty <= 0:

                        st.error(
                            f"Please enter valid quantity "
                            f"for {material_name}."
                        )

                        st.stop()

                    valid_materials.append(
                        {
                            "material": material_name,
                            "uom": material_uom,
                            "qty": material_qty
                        }
                    )

            saved_images = (
                save_uploaded_images(
                    uploaded_images,
                    equipment_name
                )
                if uploaded_images
                else []
            )

            materials_json = json.dumps(
                valid_materials
            )

            image_path_string = ";".join(
                saved_images
            )

            save_record(
                str(maintenance_date),
                stage,
                equipment_name.strip().upper(),
                order_number.strip(),
                work_carried_out.strip(),
                materials_json,
                image_path_string
            )

            st.success(
                f"✅ Maintenance record saved successfully "
                f"for {equipment_name}."
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

    st.header("📚 Equipment-wise History")

    equipment_list = get_equipment_list()

    if not equipment_list:

        st.warning(
            "⚠️ No equipment list is available."
        )

        st.info(
            "Please upload the SAP Excel file first."
        )

    else:

        selected_equipment = st.selectbox(
            "🔍 Select Equipment",
            equipment_list,
            key="history_equipment"
        )

        # ----------------------------------------------------
        # FETCH BOTH HISTORIES
        # ----------------------------------------------------

        maintenance_history = (
            get_equipment_history(
                selected_equipment
            )
        )

        notification_history = (
            get_equipment_notifications(
                selected_equipment
            )
        )

        st.divider()

        # ----------------------------------------------------
        # SUMMARY
        # ----------------------------------------------------

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "🔧 Maintenance Records",
                len(maintenance_history)
            )

        with col2:

            st.metric(
                "🔔 SAP Notifications",
                len(notification_history)
            )

        with col3:

            st.metric(
                "📋 Total History",
                len(maintenance_history)
                + len(notification_history)
            )

        st.divider()

        # ----------------------------------------------------
        # SAP NOTIFICATION HISTORY
        # ----------------------------------------------------

        st.subheader(
            f"🔔 SAP Notification History — "
            f"{selected_equipment}"
        )

        if notification_history.empty:

            st.info(
                "No SAP notifications found for "
                "this equipment."
            )

        else:

            st.dataframe(
                notification_history,
                use_container_width=True,
                hide_index=True
            )

        st.divider()

        # ----------------------------------------------------
        # MAINTENANCE HISTORY
        # ----------------------------------------------------

        st.subheader(
            f"🔧 Maintenance History — "
            f"{selected_equipment}"
        )

        if maintenance_history.empty:

            st.info(
                "No manually entered maintenance "
                "records found."
            )

        else:

            st.dataframe(
                maintenance_history.drop(
                    columns=["Image"]
                ),
                use_container_width=True,
                hide_index=True
            )

        st.divider()

        # ----------------------------------------------------
        # MATERIAL HISTORY
        # ----------------------------------------------------

        st.subheader(
            "🔩 Material Consumption History"
        )

        material_found = False

        for _, row in maintenance_history.iterrows():

            materials = parse_materials(
                row["Materials Consumed"]
            )

            if materials:

                material_found = True

                st.markdown(
                    f"**Date:** {row['Date']} "
                    f"&nbsp;&nbsp; "
                    f"**Order:** {row['Order Number']}"
                )

                material_df = pd.DataFrame(
                    materials
                )

                if not material_df.empty:

                    material_df.columns = [
                        "Material",
                        "UOM",
                        "Qty"
                    ]

                    st.dataframe(
                        material_df,
                        use_container_width=True,
                        hide_index=True
                    )

        if not material_found:

            st.info(
                "No material consumption recorded."
            )

        st.divider()

        # ----------------------------------------------------
        # IMAGES
        # ----------------------------------------------------

        st.subheader(
            "📷 Maintenance Images"
        )

        images_found = False

        for _, row in maintenance_history.iterrows():

            image_paths = row["Image"]

            if image_paths:

                for image_path in image_paths.split(";"):

                    if (
                        image_path
                        and Path(image_path).exists()
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

            selected_stage = st.selectbox(
                "Filter by Stage",
                [
                    "All"
                ]
                + sorted(
                    all_records[
                        "Stage"
                    ]
                    .dropna()
                    .unique()
                    .tolist()
                )
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
            "⬇️ Download Maintenance Records",
            csv_data,
            "maintenance_records.csv",
            "text/csv"
        )


# ============================================================
# TAB 4 - SAP EXCEL UPLOAD
# ============================================================

with tab4:

    st.header(
        "📥 SAP Notification Excel Upload"
    )

    st.info(
        "The application automatically identifies the "
        "Equipment, Description and Date columns from "
        "the Excel header."
    )

    uploaded_sap_file = st.file_uploader(
        "Select SAP Notification Excel File",
        type=[
            "xlsx",
            "xls"
        ],
        key="sap_notification_upload"
    )

    if uploaded_sap_file:

        # ----------------------------------------------------
        # READ EXCEL
        # ----------------------------------------------------

        try:

            sap_df = pd.read_excel(
                uploaded_sap_file
            )

        except Exception as error:

            st.error(
                "Unable to read the uploaded Excel file. "
                "Please check that it is a valid Excel file."
            )

            st.stop()

        if sap_df.empty:

            st.error(
                "The uploaded Excel file does not "
                "contain any data."
            )

            st.stop()

        st.success(
            f"✅ {len(sap_df)} rows found in the "
            f"uploaded Excel file."
        )

        # ----------------------------------------------------
        # SHOW ORIGINAL COLUMNS
        # ----------------------------------------------------

        st.subheader(
            "📋 Excel Columns Detected"
        )

        st.write(
            sap_df.columns.tolist()
        )

        st.divider()

        # ----------------------------------------------------
        # AUTOMATIC COLUMN DETECTION
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

        # ----------------------------------------------------
        # DISPLAY DETECTED COLUMNS
        # ----------------------------------------------------

        col1, col2, col3 = st.columns(3)

        with col1:

            if equipment_column:

                st.success(
                    f"🔧 Equipment column:\n\n"
                    f"**{equipment_column}**"
                )

            else:

                st.error(
                    "❌ Equipment column not found."
                )

        with col2:

            if description_column:

                st.success(
                    f"🔔 Description column:\n\n"
                    f"**{description_column}**"
                )

            else:

                st.error(
                    "❌ Description column not found."
                )

        with col3:

            if date_column:

                st.success(
                    f"📅 Date column:\n\n"
                    f"**{date_column}**"
                )

            else:

                st.error(
                    "❌ Date column not found."
                )

        # ----------------------------------------------------
        # STOP IF REQUIRED COLUMNS NOT FOUND
        # ----------------------------------------------------

        if (
            equipment_column is None
            or description_column is None
            or date_column is None
        ):

            st.error(
                "The Excel must contain column headings "
                "containing the words Equipment, "
                "Description and Date."
            )

            st.dataframe(
                sap_df.head(20),
                use_container_width=True,
                hide_index=True
            )

            st.stop()

        st.divider()

        # ----------------------------------------------------
        # PREVIEW IMPORTANT DATA
        # ----------------------------------------------------

        preview_df = pd.DataFrame()

        preview_df["Equipment"] = (
            sap_df[equipment_column]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
        )

        preview_df["Date"] = (
            sap_df[date_column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        preview_df["Notification"] = (
            sap_df[description_column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        preview_df = preview_df[
            preview_df["Equipment"] != ""
        ]

        st.subheader(
            "🔍 SAP Notification Preview"
        )

        st.dataframe(
            preview_df.head(20),
            use_container_width=True,
            hide_index=True
        )

        # ----------------------------------------------------
        # EQUIPMENT LIST FROM CURRENT EXCEL
        # ----------------------------------------------------

        excel_equipment_list = sorted(
            [
                x
                for x in
                preview_df["Equipment"]
                .unique()
                .tolist()
                if x
                and x.lower() != "nan"
            ]
        )

        st.divider()

        st.subheader(
            "🔧 Equipment List From Excel"
        )

        st.success(
            f"Found {len(excel_equipment_list)} "
            f"unique equipments."
        )

        equipment_master_df = pd.DataFrame(
            {
                "Equipment":
                    excel_equipment_list
            }
        )

        st.dataframe(
            equipment_master_df,
            use_container_width=True,
            hide_index=True
        )

        # ----------------------------------------------------
        # IMPORT OPTION
        # ----------------------------------------------------

        st.divider()

        upload_mode = st.radio(
            "SAP Data Import Mode",
            [
                "Add New Notifications",
                "Replace Existing SAP Notifications"
            ],
            horizontal=True
        )

        st.caption(
            "Use 'Add New Notifications' for routine uploads. "
            "Use 'Replace Existing SAP Notifications' when "
            "the Excel contains the complete SAP notification "
            "database."
        )

        # ----------------------------------------------------
        # IMPORT BUTTON
        # ----------------------------------------------------

        if st.button(
            "📥 Import SAP Notifications",
            type="primary",
            use_container_width=True
        ):

            mapped_df = pd.DataFrame()

            mapped_df[
                "notification_date"
            ] = sap_df[
                date_column
            ].fillna("").astype(str).str.strip()

            mapped_df[
                "equipment_name"
            ] = sap_df[
                equipment_column
            ].fillna("").astype(str).str.strip().str.upper()

            mapped_df[
                "description"
            ] = sap_df[
                description_column
            ].fillna("").astype(str).str.strip()

            mapped_df = mapped_df[
                mapped_df[
                    "equipment_name"
                ] != ""
            ]

            if mapped_df.empty:

                st.error(
                    "No valid equipment records were "
                    "found in the Equipment column."
                )

                st.stop()

            mode = (
                "replace"
                if upload_mode
                ==
                "Replace Existing SAP Notifications"
                else
                "append"
            )

            save_sap_notifications(
                mapped_df,
                mode
            )

            unique_equipment_count = (
                mapped_df[
                    "equipment_name"
                ].nunique()
            )

            st.success(
                f"✅ {len(mapped_df)} SAP notification "
                f"rows processed successfully."
            )

            st.success(
                f"🔧 {unique_equipment_count} unique "
                f"equipments are now available in "
                f"Maintenance Entry."
            )

            st.rerun()

    # --------------------------------------------------------
    # CURRENT DATABASE
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "📋 Current SAP Notification Database"
    )

    existing_notifications = (
        get_all_notifications()
    )

    if existing_notifications.empty:

        st.info(
            "No SAP notifications have been imported yet."
        )

    else:

        current_equipment_list = (
            get_equipment_list()
        )

        col1, col2 = st.columns(2)

        with col1:

            st.metric(
                "Total SAP Notifications",
                len(existing_notifications)
            )

        with col2:

            st.metric(
                "Unique Equipments",
                len(current_equipment_list)
            )

        st.dataframe(
            existing_notifications,
            use_container_width=True,
            hide_index=True
        )

        # ----------------------------------------------------
        # DOWNLOAD SAP DATABASE
        # ----------------------------------------------------

        sap_csv = (
            existing_notifications
            .to_csv(index=False)
            .encode("utf-8")
        )

        st.download_button(
            "⬇️ Download SAP Notification Database",
            sap_csv,
            "SAP_notifications.csv",
            "text/csv"
        )

        st.divider()

        # ----------------------------------------------------
        # MASTER EQUIPMENT LIST
        # ----------------------------------------------------

        st.subheader(
            "🔧 Master Equipment List"
        )

        equipment_master_df = pd.DataFrame(
            {
                "Equipment":
                    current_equipment_list
            }
        )

        st.dataframe(
            equipment_master_df,
            use_container_width=True,
            hide_index=True
        )

        equipment_csv = (
            equipment_master_df
            .to_csv(index=False)
            .encode("utf-8")
        )

        st.download_button(
            "⬇️ Download Equipment Master List",
            equipment_csv,
            "equipment_master.csv",
            "text/csv"
        )


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title(
    "🔧 Maintenance Navigator"
)

st.sidebar.info(
    """
Modules:

• SAP Equipment List
• Maintenance Entry
• Equipment History
• SAP Notifications
• Material Consumption
• Maintenance Images
• Date Filtering
• Stage Filtering
• Equipment-wise Search
• CSV Download
"""
)

equipment_list = get_equipment_list()

if equipment_list:

    st.sidebar.success(
        f"🔧 Master Equipment: "
        f"{len(equipment_list)}"
    )

else:

    st.sidebar.warning(
        "⚠️ SAP Equipment List Not Loaded"
    )
