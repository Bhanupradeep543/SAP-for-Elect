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

def get_connection(): return sqlite3.connect(DB_FILE, check_same_thread=False)

def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS maintenance_records (id INTEGER PRIMARY KEY AUTOINCREMENT, maintenance_date TEXT NOT NULL, stage TEXT NOT NULL, equipment_name TEXT NOT NULL, order_number TEXT, work_carried_out TEXT, materials_consumed TEXT, image_path TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS sap_notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, notification_number TEXT, notification_date TEXT, equipment_name TEXT, notification_type TEXT, description TEXT, status TEXT, raw_data TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit()
    conn.close()

def save_record(maintenance_date, stage, equipment_name, order_number, work_carried_out, materials_consumed, image_path):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""INSERT INTO maintenance_records (maintenance_date, stage, equipment_name, order_number, work_carried_out, materials_consumed, image_path) VALUES (?, ?, ?, ?, ?, ?, ?)""", (maintenance_date, stage, equipment_name, order_number, work_carried_out, materials_consumed, image_path))
    conn.commit()
    conn.close()

def save_sap_notifications(df):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sap_notifications")
    for _, row in df.iterrows():
        raw_data = json.dumps(row.to_dict(), default=str)
        cursor.execute("""INSERT INTO sap_notifications (notification_number, notification_date, equipment_name, notification_type, description, status, raw_data) VALUES (?, ?, ?, ?, ?, ?, ?)""", (str(row.get("notification_number", "")), str(row.get("notification_date", "")), str(row.get("equipment_name", "")), str(row.get("notification_type", "")), str(row.get("description", "")), str(row.get("status", "")), raw_data))
    conn.commit()
    conn.close()

def get_all_records():
    conn = get_connection()
    df = pd.read_sql_query("""SELECT maintenance_date AS Date, stage AS Stage, equipment_name AS Equipment, order_number AS 'Order Number', work_carried_out AS 'Work Carried Out', materials_consumed AS 'Materials Consumed', image_path AS Image FROM maintenance_records ORDER BY maintenance_date DESC, id DESC""", conn)
    conn.close()
    return df

def get_equipment_history(equipment_name):
    conn = get_connection()
    df = pd.read_sql_query("""SELECT maintenance_date AS Date, stage AS Stage, equipment_name AS Equipment, order_number AS 'Order Number', work_carried_out AS 'Work Carried Out', materials_consumed AS 'Materials Consumed', image_path AS Image FROM maintenance_records WHERE LOWER(TRIM(equipment_name)) = LOWER(TRIM(?)) ORDER BY maintenance_date DESC, id DESC""", conn, params=(equipment_name,))
    conn.close()
    return df

def get_all_notifications():
    conn = get_connection()
    df = pd.read_sql_query("""SELECT notification_number AS 'Notification Number', notification_date AS Date, equipment_name AS Equipment, notification_type AS 'Notification Type', description AS Description, status AS Status FROM sap_notifications ORDER BY notification_date DESC, id DESC""", conn)
    conn.close()
    return df

def get_equipment_notifications(equipment_name):
    conn = get_connection()
    df = pd.read_sql_query("""SELECT notification_number AS 'Notification Number', notification_date AS Date, equipment_name AS Equipment, notification_type AS 'Notification Type', description AS Description, status AS Status FROM sap_notifications WHERE LOWER(TRIM(equipment_name)) = LOWER(TRIM(?)) ORDER BY notification_date DESC, id DESC""", conn, params=(equipment_name,))
    conn.close()
    return df

def parse_materials(material_string):
    try: return json.loads(material_string) if material_string else []
    except (json.JSONDecodeError, TypeError): return []

def save_uploaded_images(uploaded_images, equipment_name):
    saved_images = []
    equipment_folder = IMAGE_DIR / equipment_name.replace(" ", "_")
    equipment_folder.mkdir(parents=True, exist_ok=True)
    for uploaded_file in uploaded_images:
        unique_name = f"{uuid.uuid4().hex[:8]}_{Path(uploaded_file.name).name}"
        image_path = equipment_folder / unique_name
        with open(image_path, "wb") as file: file.write(uploaded_file.getbuffer())
        saved_images.append(str(image_path))
    return saved_images

def normalize_equipment_name(value): return str(value).strip().upper()

initialize_database()

st.set_page_config(page_title="Maintenance Navigator", page_icon="🔧", layout="wide")

st.title("🔧 Maintenance Navigator")
st.caption("Equipment-wise maintenance records and SAP notification history")

tab1, tab2, tab3, tab4 = st.tabs(["📝 Maintenance Entry", "📚 Equipment History", "📊 All Maintenance Records", "📥 SAP Notification Upload"])

# ============================================================
# TAB 1 - MAINTENANCE ENTRY
# ============================================================

with tab1:
    st.header("📝 Maintenance Entry")
    col1, col2 = st.columns(2)

    with col1:
        maintenance_date = st.date_input("Maintenance Date", value=date.today())
        stage = st.selectbox("Stage", ["Stage-I", "Stage-II", "Stage-III", "Stage-IV", "Auxiliary", "Other"])
        equipment_name = st.text_input("Equipment Name", placeholder="Example: CW Pump-1A")
        order_number = st.text_input("Order Number", placeholder="Example: 4500123456")

    with col2:
        work_carried_out = st.text_area("Work Carried Out", placeholder="Describe the maintenance work carried out...", height=220)

    st.divider()
    st.subheader("🔩 Material Consumed")

    if "materials" not in st.session_state: st.session_state.materials = [{"material": "", "uom": "", "qty": 0.0}]

    col_h1, col_h2, col_h3, col_h4 = st.columns([5, 2, 2, 1])
    with col_h1: st.markdown("**Material**")
    with col_h2: st.markdown("**UOM**")
    with col_h3: st.markdown("**Qty**")
    with col_h4: st.markdown("**Action**")

    for i in range(len(st.session_state.materials)):
        col1, col2, col3, col4 = st.columns([5, 2, 2, 1])

        with col1:
            st.session_state.materials[i]["material"] = st.text_input("Material", value=st.session_state.materials[i]["material"], key=f"material_{i}", label_visibility="collapsed", placeholder="Material description")

        with col2:
            st.session_state.materials[i]["uom"] = st.text_input("UOM", value=st.session_state.materials[i]["uom"], key=f"uom_{i}", label_visibility="collapsed", placeholder="Nos / Kg / Mtr")

        with col3:
            st.session_state.materials[i]["qty"] = st.number_input("Qty", min_value=0.0, value=float(st.session_state.materials[i]["qty"]), step=0.01, key=f"qty_{i}", label_visibility="collapsed")

        with col4:
            if i > 0 and st.button("❌", key=f"delete_material_{i}"):
                st.session_state.materials.pop(i)
                st.rerun()

    if st.button("➕ Add Material", key="add_material"):
        st.session_state.materials.append({"material": "", "uom": "", "qty": 0.0})
        st.rerun()

    st.divider()

    uploaded_images = st.file_uploader("📷 Upload Equipment / Maintenance Images", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

    st.divider()

    if st.button("💾 Save Maintenance Record", type="primary", use_container_width=True):

        if not equipment_name.strip():
            st.error("Please enter the Equipment Name.")
            st.stop()

        if not work_carried_out.strip():
            st.error("Please enter the Work Carried Out details.")
            st.stop()

        valid_materials = []

        for material in st.session_state.materials:
            material_name = material["material"].strip()
            material_uom = material["uom"].strip()
            material_qty = float(material["qty"])

            if material_name or material_uom or material_qty > 0:
                if not material_name:
                    st.error("Please enter Material name.")
                    st.stop()

                if not material_uom:
                    st.error(f"Please enter UOM for {material_name}.")
                    st.stop()

                if material_qty <= 0:
                    st.error(f"Please enter valid quantity for {material_name}.")
                    st.stop()

                valid_materials.append({"material": material_name, "uom": material_uom, "qty": material_qty})

        saved_images = save_uploaded_images(uploaded_images, equipment_name.strip()) if uploaded_images else []
        materials_json = json.dumps(valid_materials)
        image_path_string = ";".join(saved_images)

        save_record(str(maintenance_date), stage, equipment_name.strip(), order_number.strip(), work_carried_out.strip(), materials_json, image_path_string)

        st.success(f"Maintenance record saved successfully for {equipment_name.strip()}.")

        st.session_state.materials = [{"material": "", "uom": "", "qty": 0.0}]

# ============================================================
# TAB 2 - EQUIPMENT HISTORY
# ============================================================

with tab2:
    st.header("📚 Equipment-wise History")

    maintenance_records = get_all_records()
    sap_notifications = get_all_notifications()

    equipment_names = set()

    if not maintenance_records.empty:
        equipment_names.update(maintenance_records["Equipment"].dropna().astype(str).str.strip().tolist())

    if not sap_notifications.empty:
        equipment_names.update(sap_notifications["Equipment"].dropna().astype(str).str.strip().tolist())

    equipment_names = sorted([x for x in equipment_names if x])

    if not equipment_names:
        st.info("No equipment data available. Enter maintenance records or upload SAP notifications.")
        st.stop()

    selected_equipment = st.selectbox("🔍 Select Equipment", equipment_names)

    maintenance_history = get_equipment_history(selected_equipment)
    notification_history = get_equipment_notifications(selected_equipment)

    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("🔧 Maintenance Records", len(maintenance_history))

    with col2:
        st.metric("🔔 SAP Notifications", len(notification_history))

    with col3:
        st.metric("📋 Total History", len(maintenance_history) + len(notification_history))

    # --------------------------------------------------------
    # SAP NOTIFICATIONS
    # --------------------------------------------------------

    st.divider()
    st.subheader("🔔 SAP Notification History")

    if notification_history.empty:
        st.info("No SAP notifications found for this equipment.")
    else:
        st.dataframe(notification_history, use_container_width=True, hide_index=True)

        notification_csv = notification_history.to_csv(index=False).encode("utf-8")

        st.download_button("⬇️ Download SAP Notifications", notification_csv, f"{selected_equipment}_SAP_notifications.csv", "text/csv")

    # --------------------------------------------------------
    # MAINTENANCE RECORDS
    # --------------------------------------------------------

    st.divider()
    st.subheader("🔧 Maintenance Records")

    if maintenance_history.empty:
        st.info("No manually entered maintenance records found.")
    else:
        display_history = maintenance_history.drop(columns=["Image"]).copy()
        st.dataframe(display_history, use_container_width=True, hide_index=True)

    # --------------------------------------------------------
    # MATERIAL HISTORY
    # --------------------------------------------------------

    st.divider()
    st.subheader("🔩 Material Consumption History")

    material_found = False

    for _, row in maintenance_history.iterrows():

        materials = parse_materials(row["Materials Consumed"])

        if materials:
            material_found = True
            st.markdown(f"**Date:** {row['Date']} &nbsp;&nbsp; **Order:** {row['Order Number']}")

            material_df = pd.DataFrame(materials)

            if not material_df.empty:
                material_df.columns = ["Material", "UOM", "Qty"]
                st.dataframe(material_df, use_container_width=True, hide_index=True)

    if not material_found:
        st.info("No material consumption recorded.")

    # --------------------------------------------------------
    # IMAGES
    # --------------------------------------------------------

    st.divider()
    st.subheader("📷 Maintenance Images")

    images_found = False

    for _, row in maintenance_history.iterrows():

        image_paths = row["Image"]

        if image_paths:

            for image_path in image_paths.split(";"):

                if image_path and Path(image_path).exists():

                    images_found = True
                    st.image(image_path, caption=f"{row['Date']} — {selected_equipment}", width=400)

    if not images_found:
        st.info("No maintenance images available.")

# ============================================================
# TAB 3 - ALL MAINTENANCE RECORDS
# ============================================================

with tab3:
    st.header("📊 All Maintenance Records")

    all_records = get_all_records()

    if all_records.empty:
        st.info("No maintenance records available.")
    else:

        col1, col2, col3 = st.columns(3)

        with col1:
            selected_stage = st.selectbox("Filter by Stage", ["All"] + sorted(all_records["Stage"].dropna().unique().tolist()))

        with col2:
            start_date = st.date_input("From Date", value=date.today().replace(day=1))

        with col3:
            end_date = st.date_input("To Date", value=date.today())

        filtered = all_records.copy()

        if selected_stage != "All":
            filtered = filtered[filtered["Stage"] == selected_stage]

        filtered["Date"] = pd.to_datetime(filtered["Date"], errors="coerce")
        filtered = filtered[(filtered["Date"] >= pd.Timestamp(start_date)) & (filtered["Date"] <= pd.Timestamp(end_date))]

        st.dataframe(filtered.drop(columns=["Image"]), use_container_width=True, hide_index=True)

        csv_data = filtered.drop(columns=["Image"]).to_csv(index=False).encode("utf-8")

        st.download_button("⬇️ Download Maintenance Records", csv_data, "maintenance_records.csv", "text/csv")

# ============================================================
# TAB 4 - SAP NOTIFICATION UPLOAD
# ============================================================

with tab4:
    st.header("📥 SAP Notification Upload")

    st.info("Upload the Excel file containing SAP notifications for all equipments.")

    uploaded_sap_file = st.file_uploader("Select SAP Notification Excel File", type=["xlsx", "xls"], key="sap_notification_upload")

    if uploaded_sap_file:

        sap_df = pd.read_excel(uploaded_sap_file)

        if sap_df.empty:
            st.error("The uploaded Excel file does not contain any data.")
            st.stop()

        st.success(f"{len(sap_df)} rows found in the uploaded SAP file.")

        st.subheader("Preview SAP Data")
        st.dataframe(sap_df.head(20), use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("🔗 Map SAP Columns")

        st.caption("Select the corresponding column from your SAP Excel file.")

        excel_columns = sap_df.columns.tolist()

        col1, col2 = st.columns(2)

        with col1:

            notification_number_column = st.selectbox("Notification Number", excel_columns, key="notification_number_column")

            notification_date_column = st.selectbox("Notification Date", excel_columns, key="notification_date_column")

            equipment_column = st.selectbox("Equipment Name", excel_columns, key="equipment_column")

        with col2:

            notification_type_column = st.selectbox("Notification Type", ["-- Not Available --"] + excel_columns, key="notification_type_column")

            description_column = st.selectbox("Description", excel_columns, key="description_column")

            status_column = st.selectbox("Status", ["-- Not Available --"] + excel_columns, key="status_column")

        st.divider()

        if st.button("📥 Import SAP Notifications", type="primary", use_container_width=True):

            mapped_df = pd.DataFrame()

            mapped_df["notification_number"] = sap_df[notification_number_column].fillna("").astype(str).str.strip()
            mapped_df["notification_date"] = sap_df[notification_date_column].fillna("").astype(str).str.strip()
            mapped_df["equipment_name"] = sap_df[equipment_column].fillna("").astype(str).str.strip().str.upper()

            if notification_type_column != "-- Not Available --":
                mapped_df["notification_type"] = sap_df[notification_type_column].fillna("").astype(str).str.strip()
            else:
                mapped_df["notification_type"] = ""

            mapped_df["description"] = sap_df[description_column].fillna("").astype(str).str.strip()

            if status_column != "-- Not Available --":
                mapped_df["status"] = sap_df[status_column].fillna("").astype(str).str.strip()
            else:
                mapped_df["status"] = ""

            mapped_df = mapped_df[mapped_df["equipment_name"] != ""]

            if mapped_df.empty:
                st.error("No valid equipment records were found in the selected Equipment column.")
                st.stop()

            save_sap_notifications(mapped_df)

            st.success(f"{len(mapped_df)} SAP notifications imported successfully.")

            st.rerun()

    st.divider()
    st.subheader("📋 Current SAP Notification Database")

    existing_notifications = get_all_notifications()

    if existing_notifications.empty:
        st.info("No SAP notifications have been imported yet.")
    else:

        st.write(f"Total notifications: **{len(existing_notifications)}**")

        st.dataframe(existing_notifications, use_container_width=True, hide_index=True)

        sap_csv = existing_notifications.to_csv(index=False).encode("utf-8")

        st.download_button("⬇️ Download SAP Notification Database", sap_csv, "SAP_notifications.csv", "text/csv")

# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("🔧 Maintenance Navigator")

st.sidebar.info("""
Modules available:

• Maintenance Entry
• Material Consumption
• Equipment History
• SAP Notifications
• Maintenance Images
• Stage Filtering
• Date Filtering
• Equipment-wise Search
• CSV Download
""")
