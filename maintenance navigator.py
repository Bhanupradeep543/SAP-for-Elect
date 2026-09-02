import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
from pathlib import Path
import uuid
import json

DB_FILE = "maintenance_history.db"
IMAGE_DIR = Path("maintenance_images")
IMAGE_DIR.mkdir(exist_ok=True)

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

    conn.commit()
    conn.close()

def save_record(maintenance_date, stage, equipment_name, order_number, work_carried_out, materials_consumed, image_path):

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
        WHERE equipment_name = ?
        ORDER BY maintenance_date DESC, id DESC
    """, conn, params=(equipment_name,))

    conn.close()

    return df

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
        ORDER BY maintenance_date DESC
    """, conn)

    conn.close()

    return df

initialize_database()

st.set_page_config(
    page_title="Maintenance History System",
    page_icon="🔧",
    layout="wide"
)

st.title("🔧 Maintenance History & Decision Support System")
st.caption("Equipment-wise maintenance history recording system")

tab1, tab2, tab3 = st.tabs([
    "📝 Maintenance Entry",
    "📚 Equipment History",
    "📊 All Maintenance Records"
])

with tab1:

    st.header("Enter Maintenance Details")

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

        equipment_name = st.text_input(
            "Equipment Name",
            placeholder="Example: CW Pump-1A"
        )

        order_number = st.text_input(
            "Order Number",
            placeholder="Example: 4500123456"
        )

    with col2:

        work_carried_out = st.text_area(
            "Work Carried Out",
            placeholder="Describe the maintenance work carried out...",
            height=220
        )

    st.divider()

    st.subheader("🔩 Material Consumed")

    if "materials" not in st.session_state:
        st.session_state.materials = [
            {
                "material": "",
                "uom": "",
                "qty": 0.0
            }
        ]

    for i in range(len(st.session_state.materials)):

        col1, col2, col3, col4 = st.columns([5, 2, 2, 1])

        with col1:

            st.session_state.materials[i]["material"] = st.text_input(
                "Material" if i == 0 else "",
                value=st.session_state.materials[i]["material"],
                key=f"material_{i}",
                placeholder="Material description"
            )

        with col2:

            st.session_state.materials[i]["uom"] = st.text_input(
                "UOM" if i == 0 else "",
                value=st.session_state.materials[i]["uom"],
                key=f"uom_{i}",
                placeholder="Nos / Kg / Mtr"
            )

        with col3:

            st.session_state.materials[i]["qty"] = st.number_input(
                "Qty" if i == 0 else "",
                min_value=0.0,
                value=float(st.session_state.materials[i]["qty"]),
                step=0.01,
                key=f"qty_{i}"
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

    uploaded_images = st.file_uploader(
        "📷 Upload Equipment / Maintenance Images",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True
    )

    st.divider()

    if st.button(
        "💾 Save Maintenance Record",
        type="primary",
        use_container_width=True
    ):

        if not equipment_name.strip():

            st.error("Please enter the Equipment Name.")

        elif not work_carried_out.strip():

            st.error("Please enter the Work Carried Out details.")

        else:

            valid_materials = []

            for material in st.session_state.materials:

                if (
                    material["material"].strip()
                    or material["uom"].strip()
                    or material["qty"] > 0
                ):

                    if not material["material"].strip():

                        st.error(
                            "Please enter Material name for all material rows."
                        )

                        st.stop()

                    if not material["uom"].strip():

                        st.error(
                            f"Please enter UOM for {material['material']}."
                        )

                        st.stop()

                    if material["qty"] <= 0:

                        st.error(
                            f"Please enter valid quantity for {material['material']}."
                        )

                        st.stop()

                    valid_materials.append(
                        {
                            "material": material["material"].strip(),
                            "uom": material["uom"].strip(),
                            "qty": material["qty"]
                        }
                    )

            saved_images = []

            if uploaded_images:

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
                        str(uuid.uuid4())[:8]
                        + "_"
                        + uploaded_file.name
                    )

                    image_path = (
                        equipment_folder /
                        unique_name
                    )

                    with open(
                        image_path,
                        "wb"
                    ) as f:

                        f.write(
                            uploaded_file.getbuffer()
                        )

                    saved_images.append(
                        str(image_path)
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
                equipment_name.strip(),
                order_number.strip(),
                work_carried_out.strip(),
                materials_json,
                image_path_string
            )

            st.success(
                f"Maintenance record saved successfully for {equipment_name}."
            )

            st.session_state.materials = [
                {
                    "material": "",
                    "uom": "",
                    "qty": 0.0
                }
            ]

with tab2:

    st.header("📚 Equipment-wise Maintenance History")

    all_records = get_all_records()

    if all_records.empty:

        st.info(
            "No maintenance records available yet."
        )

    else:

        equipment_list = sorted(
            all_records["Equipment"]
            .dropna()
            .unique()
            .tolist()
        )

        selected_equipment = st.selectbox(
            "Select Equipment",
            equipment_list
        )

        history = get_equipment_history(
            selected_equipment
        )

        if not history.empty:

            st.subheader(
                f"Maintenance History — {selected_equipment}"
            )

            st.metric(
                "Total Maintenance Records",
                len(history)
            )

            display_history = history.drop(
                columns=["Image"]
            ).copy()

            st.dataframe(
                display_history,
                use_container_width=True,
                hide_index=True
            )

            st.subheader(
                "🔩 Material Consumption History"
            )

            for _, row in history.iterrows():

                try:

                    materials = json.loads(
                        row["Materials Consumed"]
                    )

                except:

                    materials = []

                if materials:

                    st.markdown(
                        f"**Date:** {row['Date']} | "
                        f"**Order:** {row['Order Number']}"
                    )

                    material_df = pd.DataFrame(
                        materials
                    )

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

            st.subheader(
                "📷 Maintenance Images"
            )

            for _, row in history.iterrows():

                image_paths = row["Image"]

                if image_paths:

                    for image_path in image_paths.split(";"):

                        if (
                            image_path
                            and Path(image_path).exists()
                        ):

                            st.image(
                                image_path,
                                caption=(
                                    f"{row['Date']} — "
                                    f"{selected_equipment}"
                                ),
                                width=400
                            )

with tab3:

    st.header("📊 All Maintenance Records")

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
                ["All"] +
                sorted(
                    all_records["Stage"]
                    .dropna()
                    .unique()
                    .tolist()
                )
            )

        with col2:

            start_date = st.date_input(
                "From Date",
                value=date.today().replace(day=1)
            )

        with col3:

            end_date = st.date_input(
                "To Date",
                value=date.today()
            )

        filtered = all_records.copy()

        if selected_stage != "All":

            filtered = filtered[
                filtered["Stage"] == selected_stage
            ]

        filtered["Date"] = pd.to_datetime(
            filtered["Date"]
        )

        filtered = filtered[
            (filtered["Date"] >= pd.Timestamp(start_date))
            &
            (filtered["Date"] <= pd.Timestamp(end_date))
        ]

        st.dataframe(
            filtered.drop(
                columns=["Image"]
            ),
            use_container_width=True,
            hide_index=True
        )

        csv_data = filtered.drop(
            columns=["Image"]
        ).to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            "⬇️ Download Maintenance Records",
            data=csv_data,
            file_name="maintenance_records.csv",
            mime="text/csv"
        )

st.sidebar.title("System Information")

st.sidebar.info(
    """
    Maintenance History System

    Records maintained:

    • Date
    • Stage
    • Equipment
    • Order Number
    • Work Carried Out
    • Material
    • UOM
    • Quantity
    • Maintenance Images
    """
)
