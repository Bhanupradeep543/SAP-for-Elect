import streamlit as st
import sqlite3
import pandas as pd
from datetime import date,datetime
from pathlib import Path
import uuid,json,re

BASE_DIR=Path(__file__).resolve().parent
DB_FILE=BASE_DIR/"maintenance_history.db"
IMAGE_DIR=BASE_DIR/"maintenance_images"
OH_UPLOAD_DIR=BASE_DIR/"oh_records"
IMAGE_DIR.mkdir(exist_ok=True)
OH_UPLOAD_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="Maintenance Navigator",page_icon="🔧",layout="wide")

def get_connection():
    conn=sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def initialize_database():
    conn=get_connection()
    cursor=conn.cursor()

    cursor.execute("""CREATE TABLE IF NOT EXISTS equipment_master(id INTEGER PRIMARY KEY AUTOINCREMENT,equipment_name TEXT UNIQUE NOT NULL,created_at TEXT)""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS maintenance_records(id INTEGER PRIMARY KEY AUTOINCREMENT,maintenance_date TEXT,stage TEXT,maintenance_type TEXT,equipment_name TEXT,order_number TEXT,work_carried_out TEXT,materials_consumed TEXT,image_path TEXT,created_at TEXT)""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS sap_notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,notification_date TEXT,equipment_name TEXT,description TEXT,created_at TEXT)""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS oh_records(id INTEGER PRIMARY KEY AUTOINCREMENT,oh_date TEXT,equipment_name TEXT,order_number TEXT,description TEXT,file_path TEXT,created_at TEXT)""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS local_observations(id INTEGER PRIMARY KEY AUTOINCREMENT,observation_date TEXT,stage TEXT,equipment_name TEXT,defect_description TEXT,severity TEXT,status TEXT,created_at TEXT)""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS spare_master(id INTEGER PRIMARY KEY AUTOINCREMENT,stage TEXT,system_name TEXT,s_no TEXT,material_code TEXT,spare_description TEXT,uom TEXT,quantity REAL,location TEXT,created_at TEXT)""")

    cursor.execute("""CREATE TABLE IF NOT EXISTS spare_equipment_mapping(id INTEGER PRIMARY KEY AUTOINCREMENT,spare_id INTEGER NOT NULL,equipment_name TEXT NOT NULL,created_at TEXT,FOREIGN KEY(spare_id) REFERENCES spare_master(id) ON DELETE CASCADE)""")

    def get_columns(table):
        cursor.execute(f"PRAGMA table_info({table})")
        return [row[1] for row in cursor.fetchall()]

    maintenance_columns=get_columns("maintenance_records")
    for column,column_type in [("maintenance_type","TEXT"),("materials_consumed","TEXT"),("image_path","TEXT"),("created_at","TEXT")]:
        if column not in maintenance_columns:
            cursor.execute(f"ALTER TABLE maintenance_records ADD COLUMN {column} {column_type}")

    sap_columns=get_columns("sap_notifications")
    for column,column_type in [("notification_date","TEXT"),("equipment_name","TEXT"),("description","TEXT"),("created_at","TEXT")]:
        if column not in sap_columns:
            cursor.execute(f"ALTER TABLE sap_notifications ADD COLUMN {column} {column_type}")

    oh_columns=get_columns("oh_records")
    for column,column_type in [("oh_date","TEXT"),("equipment_name","TEXT"),("order_number","TEXT"),("description","TEXT"),("file_path","TEXT"),("created_at","TEXT")]:
        if column not in oh_columns:
            cursor.execute(f"ALTER TABLE oh_records ADD COLUMN {column} {column_type}")

    observation_columns=get_columns("local_observations")
    for column,column_type in [("observation_date","TEXT"),("stage","TEXT"),("equipment_name","TEXT"),("defect_description","TEXT"),("severity","TEXT"),("status","TEXT"),("created_at","TEXT")]:
        if column not in observation_columns:
            cursor.execute(f"ALTER TABLE local_observations ADD COLUMN {column} {column_type}")

    spare_columns=get_columns("spare_master")
    for column,column_type in [("stage","TEXT"),("system_name","TEXT"),("s_no","TEXT"),("material_code","TEXT"),("spare_description","TEXT"),("uom","TEXT"),("quantity","REAL"),("location","TEXT"),("created_at","TEXT")]:
        if column not in spare_columns:
            cursor.execute(f"ALTER TABLE spare_master ADD COLUMN {column} {column_type}")

    mapping_columns=get_columns("spare_equipment_mapping")
    for column,column_type in [("spare_id","INTEGER"),("equipment_name","TEXT"),("created_at","TEXT")]:
        if column not in mapping_columns:
            cursor.execute(f"ALTER TABLE spare_equipment_mapping ADD COLUMN {column} {column_type}")

    cursor.execute("""CREATE INDEX IF NOT EXISTS idx_spare_equipment ON spare_equipment_mapping(equipment_name)""")
    cursor.execute("""CREATE INDEX IF NOT EXISTS idx_spare_stage_system ON spare_master(stage,system_name)""")
    cursor.execute("""CREATE INDEX IF NOT EXISTS idx_maintenance_equipment ON maintenance_records(equipment_name)""")
    cursor.execute("""CREATE INDEX IF NOT EXISTS idx_observation_equipment ON local_observations(equipment_name)""")

    conn.commit()
    conn.close()

initialize_database()

def clean_text(value):
    return "" if pd.isna(value) else str(value).strip()

def find_column(df,keywords):
    if isinstance(keywords,str):
        keywords=[keywords]
    for c in df.columns:
        for k in keywords:
            if k.lower() in str(c).strip().lower():
                return c
    return None

def get_equipment_list():
    conn=get_connection()
    df=pd.read_sql_query("SELECT equipment_name FROM equipment_master ORDER BY equipment_name",conn)
    conn.close()
    return [] if df.empty else df["equipment_name"].dropna().astype(str).tolist()

def import_new_sap_data(equipment_list,notification_df):
    conn=get_connection()
    try:
        cursor=conn.cursor()

        equipment_list=sorted(set(clean_text(x) for x in equipment_list if clean_text(x)))

        cursor.execute("DELETE FROM equipment_master")

        cursor.executemany("INSERT INTO equipment_master(equipment_name,created_at) VALUES(?,?)",[(x,datetime.now().isoformat()) for x in equipment_list])

        cursor.execute("DELETE FROM sap_notifications")

        rows=[(clean_text(r["equipment_name"]),clean_text(r["notification_date"]),clean_text(r["description"]),datetime.now().isoformat()) for _,r in notification_df.iterrows() if clean_text(r["equipment_name"])]

        if rows:
            cursor.executemany("INSERT INTO sap_notifications(equipment_name,notification_date,description,created_at) VALUES(?,?,?,?)",rows)

        conn.commit()
        return len(equipment_list),len(rows)

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

def save_record(maintenance_date,stage,maintenance_type,equipment_name,order_number,work_carried_out,materials,image_paths):
    conn=get_connection()
    conn.execute("""INSERT INTO maintenance_records(maintenance_date,stage,maintenance_type,equipment_name,order_number,work_carried_out,materials_consumed,image_path,created_at) VALUES(?,?,?,?,?,?,?,?,?)""",(str(maintenance_date),stage,maintenance_type,equipment_name,order_number,work_carried_out,json.dumps(materials),json.dumps(image_paths),datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_maintenance_record(record_id):
    conn=get_connection()
    df=pd.read_sql_query("SELECT * FROM maintenance_records WHERE id=?",conn,params=(record_id,))
    conn.close()
    return None if df.empty else df.iloc[0].to_dict()

def update_maintenance_record(record_id,maintenance_date,stage,maintenance_type,equipment_name,order_number,work_carried_out,materials,image_paths):
    conn=get_connection()
    conn.execute("""UPDATE maintenance_records SET maintenance_date=?,stage=?,maintenance_type=?,equipment_name=?,order_number=?,work_carried_out=?,materials_consumed=?,image_path=? WHERE id=?""",(str(maintenance_date),stage,maintenance_type,equipment_name,order_number,work_carried_out,json.dumps(materials),json.dumps(image_paths),record_id))
    conn.commit()
    conn.close()

def get_equipment_history(equipment):
    conn=get_connection()
    df=pd.read_sql_query("""SELECT id,maintenance_date AS Date,stage AS Stage,maintenance_type AS Type,order_number AS "Order Number",work_carried_out AS "Work Carried Out" FROM maintenance_records WHERE equipment_name=? ORDER BY maintenance_date DESC""",conn,params=(equipment,))
    conn.close()
    return df

def get_all_records():
    conn=get_connection()
    df=pd.read_sql_query("""SELECT id,maintenance_date AS Date,stage AS Stage,maintenance_type AS Type,equipment_name AS Equipment,order_number AS "Order Number",work_carried_out AS "Work Carried Out" FROM maintenance_records ORDER BY maintenance_date DESC""",conn)
    conn.close()
    return df

def save_uploaded_images(files,equipment):
    if not files:
        return []

    folder=IMAGE_DIR/re.sub(r"[^A-Za-z0-9_-]","_",equipment)
    folder.mkdir(exist_ok=True)

    paths=[]

    for f in files:
        p=folder/(datetime.now().strftime("%Y%m%d_%H%M%S_")+str(uuid.uuid4())[:8]+Path(f.name).suffix)

        with open(p,"wb") as out:
            out.write(f.getbuffer())

        paths.append(str(p))

    return paths

def get_equipment_notifications(equipment):
    conn=get_connection()
    df=pd.read_sql_query("""SELECT notification_date AS Date,description AS Notification FROM sap_notifications WHERE equipment_name=? ORDER BY notification_date DESC""",conn,params=(equipment,))
    conn.close()
    return df

def save_oh_records(df):
    ec=find_column(df,"equipment")
    dc=find_column(df,"date")
    desc=find_column(df,["description","work"])
    oc=find_column(df,"order")

    if not ec:
        raise ValueError("Equipment column could not be identified.")

    if not dc:
        raise ValueError("Date column could not be identified.")

    rows=[]

    for _,r in df.iterrows():
        eq=clean_text(r[ec])

        if eq:
            rows.append((clean_text(r[dc]),eq,clean_text(r[oc]) if oc else "",clean_text(r[desc]) if desc else "",datetime.now().isoformat()))

    conn=get_connection()

    if rows:
        conn.executemany("""INSERT INTO oh_records(oh_date,equipment_name,order_number,description,created_at) VALUES(?,?,?,?,?)""",rows)

    conn.commit()
    conn.close()

    return len(rows)

def get_oh_records(equipment):
    conn=get_connection()
    df=pd.read_sql_query("""SELECT oh_date AS Date,order_number AS "Order Number",description AS Description FROM oh_records WHERE equipment_name=? ORDER BY oh_date DESC""",conn,params=(equipment,))
    conn.close()
    return df

def save_local_observation(observation_date,stage,equipment,description,severity,status):
    conn=get_connection()
    conn.execute("""INSERT INTO local_observations(observation_date,stage,equipment_name,defect_description,severity,status,created_at) VALUES(?,?,?,?,?,?,?)""",(str(observation_date),stage,equipment,description,severity,status,datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_local_observations(equipment=None):
    conn=get_connection()

    if equipment:
        df=pd.read_sql_query("""SELECT id,observation_date AS Date,stage AS Stage,defect_description AS "Defect Description",severity AS Severity,status AS Status FROM local_observations WHERE equipment_name=? ORDER BY observation_date DESC""",conn,params=(equipment,))
    else:
        df=pd.read_sql_query("""SELECT id,observation_date AS Date,stage AS Stage,equipment_name AS Equipment,defect_description AS "Defect Description",severity AS Severity,status AS Status FROM local_observations ORDER BY observation_date DESC""",conn)

    conn.close()
    return df

def update_observation_status(observation_id,status):
    conn=get_connection()
    conn.execute("UPDATE local_observations SET status=? WHERE id=?",(status,observation_id))
    conn.commit()
    conn.close()

def upload_spare_master(df,stage,system):
    sn=find_column(df,["s.no","s no","serial"])
    mc=find_column(df,["material code","material","spare"])
    dc=find_column(df,"description")
    uc=find_column(df,["uom","unit"])
    qc=find_column(df,["qty","quantity"])
    lc=find_column(df,"location")

    if not mc:
        raise ValueError("Material Code column could not be identified.")

    conn=get_connection()
    cursor=conn.cursor()
    rows=[]

    for _,r in df.iterrows():
        material=clean_text(r[mc])

        if not material:
            continue

        try:
            qty=float(r[qc]) if qc and not pd.isna(r[qc]) else 0
        except:
            qty=0

        rows.append((stage,system,clean_text(r[sn]) if sn else "",material,clean_text(r[dc]) if dc else "",clean_text(r[uc]) if uc else "",qty,clean_text(r[lc]) if lc else "",datetime.now().isoformat()))

    if rows:
        cursor.executemany("""INSERT INTO spare_master(stage,system_name,s_no,material_code,spare_description,uom,quantity,location,created_at) VALUES(?,?,?,?,?,?,?,?,?)""",rows)

    conn.commit()
    conn.close()

    return len(rows)

def get_spare_stage_list():
    conn=get_connection()
    df=pd.read_sql_query("SELECT DISTINCT stage FROM spare_master WHERE stage<>'' ORDER BY stage",conn)
    conn.close()
    return df["stage"].tolist() if not df.empty else []

def get_spare_system_list(stage=None):
    conn=get_connection()

    if stage:
        df=pd.read_sql_query("SELECT DISTINCT system_name FROM spare_master WHERE stage=? AND system_name<>'' ORDER BY system_name",conn,params=(stage,))
    else:
        df=pd.read_sql_query("SELECT DISTINCT system_name FROM spare_master WHERE system_name<>'' ORDER BY system_name",conn)

    conn.close()
    return df["system_name"].tolist() if not df.empty else []

def get_spares_by_stage_system(stage,system):
    conn=get_connection()

    df=pd.read_sql_query("""SELECT id,s_no AS "S.No",material_code AS "Material Code",spare_description AS Description,uom AS UOM,quantity AS Qty,location AS Location FROM spare_master WHERE stage=? AND system_name=? ORDER BY id""",conn,params=(stage,system))

    conn.close()
    return df

def get_spares():
    conn=get_connection()

    df=pd.read_sql_query("""SELECT id,stage AS Stage,system_name AS System,s_no AS "S.No",material_code AS "Material Code",spare_description AS Description,uom AS UOM,quantity AS Qty,location AS Location FROM spare_master ORDER BY stage,system_name,material_code""",conn)

    conn.close()
    return df

def link_spare_to_equipment(spare_id,equipment_list):
    conn=get_connection()

    conn.execute("DELETE FROM spare_equipment_mapping WHERE spare_id=?",(spare_id,))

    if equipment_list:
        conn.executemany("INSERT INTO spare_equipment_mapping(spare_id,equipment_name,created_at) VALUES(?,?,?)",[(spare_id,e,datetime.now().isoformat()) for e in equipment_list])

    conn.commit()
    conn.close()

def get_equipment_spares(equipment):
    conn=get_connection()

    try:
        query="""SELECT s.stage AS Stage,s.system_name AS System,s.s_no AS "S.No",s.material_code AS "Material Code",s.spare_description AS Description,s.uom AS UOM,s.quantity AS Qty,s.location AS Location FROM spare_master s INNER JOIN spare_equipment_mapping m ON s.id=m.spare_id WHERE m.equipment_name=? ORDER BY s.stage,s.system_name,s.material_code"""

        df=pd.read_sql_query(query,conn,params=(equipment,))

        return df

    except Exception:
        return pd.DataFrame(columns=["Stage","System","S.No","Material Code","Description","UOM","Qty","Location"])

    finally:
        conn.close()

def get_spare_linked_equipment(spare_id):
    conn=get_connection()

    df=pd.read_sql_query("SELECT equipment_name FROM spare_equipment_mapping WHERE spare_id=? ORDER BY equipment_name",conn,params=(spare_id,))

    conn.close()

    return df["equipment_name"].tolist() if not df.empty else []

def parse_json_list(value):
    try:
        result=json.loads(value) if value else []
        return result if isinstance(result,list) else []
    except:
        return []

def materials_editor(prefix,initial=None):
    if initial is None:
        initial=[{"Material":"","UOM":"","Qty":0.0}]

    if f"{prefix}_materials" not in st.session_state:
        st.session_state[f"{prefix}_materials"]=initial

    materials=st.session_state[f"{prefix}_materials"]

    st.write("### Materials Consumed")

    for i,row in enumerate(materials):
        c1,c2,c3,c4=st.columns([4,2,2,1])

        materials[i]["Material"]=c1.text_input("Material",value=row.get("Material",""),key=f"{prefix}_mat_{i}")

        materials[i]["UOM"]=c2.text_input("UOM",value=row.get("UOM",""),key=f"{prefix}_uom_{i}")

        materials[i]["Qty"]=c3.number_input("Qty",min_value=0.0,value=float(row.get("Qty",0)),step=1.0,key=f"{prefix}_qty_{i}")

        if c4.button("🗑️",key=f"{prefix}_del_{i}"):

            if len(materials)>1:
                materials.pop(i)
                st.session_state[f"{prefix}_materials"]=materials
                st.rerun()

    if st.button("➕ Add Material",key=f"{prefix}_add"):
        materials.append({"Material":"","UOM":"","Qty":0.0})
        st.session_state[f"{prefix}_materials"]=materials
        st.rerun()

    return materials

tab1,tab2,tab3,tab4,tab5,tab6,tab7=st.tabs(["🛠 Maintenance Entry","📋 Equipment History","📊 All Maintenance Records","📥 SAP Notification Upload","🔄 OH Record Upload","🔩 Spare List","🔎 Local Observations"])

with tab1:

    st.header("Maintenance Entry")

    equipment_list=get_equipment_list()

    if not equipment_list:
        st.warning("No equipment master is available. Please upload the latest SAP Excel first.")
    else:

        maintenance_date=st.date_input("Maintenance Date",value=date.today(),key="new_maintenance_date")

        c1,c2=st.columns(2)

        stage=c1.selectbox("Stage",["Stage-1","Stage-2","Stage-3","Other"],key="new_stage")

        maintenance_type=c2.selectbox("Maintenance Type",["Defect","PM","OH"],key="new_type")

        equipment=st.selectbox("Equipment",equipment_list,key="new_equipment")

        order_number=st.text_input("Order Number",key="new_order")

        work_carried_out=st.text_area("Work Carried Out",height=120,key="new_work")

        materials=materials_editor("new")

        uploaded_images=st.file_uploader("Maintenance Images",type=["jpg","jpeg","png"],accept_multiple_files=True,key="new_images")

        if st.button("💾 Save Maintenance Record",type="primary"):

            image_paths=save_uploaded_images(uploaded_images,equipment)

            clean_materials=[m for m in materials if m.get("Material","").strip()]

            save_record(maintenance_date,stage,maintenance_type,equipment,order_number,work_carried_out,clean_materials,image_paths)

            st.success("Maintenance record saved successfully.")

            st.session_state["new_materials"]=[{"Material":"","UOM":"","Qty":0.0}]

            st.rerun()

with tab2:

    st.header("Equipment History")

    equipment_list=get_equipment_list()

    if not equipment_list:
        st.warning("No equipment master available. Please upload the latest SAP Excel.")
    else:

        selected_equipment=st.selectbox("Select Equipment",equipment_list,key="history_equipment")

        st.subheader("🛠 Manual Maintenance History")

        history=get_equipment_history(selected_equipment)

        if history.empty:
            st.info("No manual maintenance records found for this equipment.")
        else:

            for _,record in history.iterrows():

                record_id=int(record["id"])

                c1,c2,c3,c4,c5,c6=st.columns([1,1.2,1,1.2,4,1])

                c1.write(str(record["Date"]))
                c2.write(str(record["Stage"]))
                c3.write(str(record["Type"]))
                c4.write(str(record["Order Number"]))
                c5.write(str(record["Work Carried Out"])[:100])

                if c6.button("✏️ Edit",key=f"edit_{record_id}"):

                    st.session_state["editing_record_id"]=record_id
                    st.rerun()

            if "editing_record_id" in st.session_state:

                record_id=st.session_state["editing_record_id"]
                record=get_maintenance_record(record_id)

                if record:

                    st.divider()
                    st.subheader("✏️ Edit Maintenance Record")

                    try:
                        edit_date=datetime.strptime(str(record.get("maintenance_date")), "%Y-%m-%d").date()
                    except:
                        edit_date=date.today()

                    old_materials=parse_json_list(record.get("materials_consumed"))
                    old_images=parse_json_list(record.get("image_path"))

                    e_date=st.date_input("Maintenance Date",value=edit_date,key=f"edit_date_{record_id}")

                    ec1,ec2=st.columns(2)

                    e_stage=ec1.selectbox("Stage",["Stage-1","Stage-2","Stage-3","Other"],index=["Stage-1","Stage-2","Stage-3","Other"].index(record.get("stage")) if record.get("stage") in ["Stage-1","Stage-2","Stage-3","Other"] else 0,key=f"edit_stage_{record_id}")

                    e_type=ec2.selectbox("Maintenance Type",["Defect","PM","OH"],index=["Defect","PM","OH"].index(record.get("maintenance_type")) if record.get("maintenance_type") in ["Defect","PM","OH"] else 0,key=f"edit_type_{record_id}")

                    edit_equipment_list=sorted(set(equipment_list+[clean_text(record.get("equipment_name"))]))

                    e_equipment=st.selectbox("Equipment",edit_equipment_list,index=edit_equipment_list.index(record.get("equipment_name")) if record.get("equipment_name") in edit_equipment_list else 0,key=f"edit_equipment_{record_id}")

                    e_order=st.text_input("Order Number",value=clean_text(record.get("order_number")),key=f"edit_order_{record_id}")

                    e_work=st.text_area("Work Carried Out",value=clean_text(record.get("work_carried_out")),height=120,key=f"edit_work_{record_id}")

                    e_materials=materials_editor(f"edit_{record_id}",old_materials if old_materials else [{"Material":"","UOM":"","Qty":0.0}])

                    st.write("### Existing Images")

                    if old_images:
                        for img in old_images:
                            if Path(img).exists():
                                st.image(img,width=180)

                    new_images=st.file_uploader("Add New Images",type=["jpg","jpeg","png"],accept_multiple_files=True,key=f"edit_images_{record_id}")

                    csave,cancel=st.columns(2)

                    if csave.button("💾 Update Record",type="primary",key=f"update_{record_id}"):

                        added_images=save_uploaded_images(new_images,e_equipment)

                        final_images=old_images+added_images

                        clean_materials=[m for m in e_materials if m.get("Material","").strip()]

                        update_maintenance_record(record_id,e_date,e_stage,e_type,e_equipment,e_order,e_work,clean_materials,final_images)

                        del st.session_state["editing_record_id"]

                        st.success("Maintenance record updated successfully.")
                        st.rerun()

                    if cancel.button("❌ Cancel",key=f"cancel_{record_id}"):

                        del st.session_state["editing_record_id"]
                        st.rerun()

        st.divider()

        st.subheader("🔎 Local Observations")

        observations=get_local_observations(selected_equipment)

        if observations.empty:
            st.info("No local observations found.")
        else:

            for _,obs in observations.iterrows():

                oid=int(obs["id"])

                c1,c2,c3,c4,c5,c6=st.columns([1,1,3,1,1.5,1.5])

                c1.write(str(obs["Date"]))
                c2.write(str(obs["Stage"]))
                c3.write(str(obs["Defect Description"]))
                c4.write(str(obs["Severity"]))

                current_status=str(obs["Status"]) if clean_text(obs["Status"]) else "Pending"

                status_options=["Pending","Work Completed"]

                status_index=status_options.index(current_status) if current_status in status_options else 0

                new_status=c5.selectbox("Status",status_options,index=status_index,key=f"history_obs_status_{oid}")

                if new_status!=current_status:
                    update_observation_status(oid,new_status)
                    st.rerun()

        st.divider()

        st.subheader("📢 SAP Notifications")

        notifications=get_equipment_notifications(selected_equipment)

        if notifications.empty:
            st.info("No SAP notifications found.")
        else:
            st.dataframe(notifications,use_container_width=True,hide_index=True)

        st.divider()

        st.subheader("🔄 OH Records")

        oh_history=get_oh_records(selected_equipment)

        if oh_history.empty:
            st.info("No OH records found.")
        else:
            st.dataframe(oh_history,use_container_width=True,hide_index=True)

        st.divider()

        st.subheader("🔩 Linked Spares")

        equipment_spares=get_equipment_spares(selected_equipment)

        if equipment_spares.empty:
            st.info("No spares linked to this equipment.")
        else:
            st.dataframe(equipment_spares,use_container_width=True,hide_index=True)

with tab3:

    st.header("All Maintenance Records")

    all_records=get_all_records()

    if all_records.empty:
        st.info("No maintenance records available.")
    else:
        st.dataframe(all_records,use_container_width=True,hide_index=True)

with tab4:

    st.header("SAP Notification Upload")

    st.info("Upload the latest SAP Excel. The equipment master and SAP notification history will be completely replaced by this file. Existing manual maintenance records will remain unchanged.")

    sap_file=st.file_uploader("Upload SAP Excel",type=["xlsx","xls"],key="sap_upload")

    if sap_file:

        try:

            sap_df=pd.read_excel(sap_file)

            equipment_col=find_column(sap_df,"equipment")
            description_col=find_column(sap_df,"description")
            date_col=find_column(sap_df,"date")

            if not equipment_col:
                st.error("Equipment column could not be identified.")
            elif not description_col:
                st.error("Description column could not be identified.")
            elif not date_col:
                st.error("Date column could not be identified.")
            else:

                equipment_values=[clean_text(x) for x in sap_df[equipment_col].tolist() if clean_text(x)]

                notification_df=pd.DataFrame({"equipment_name":sap_df[equipment_col].apply(clean_text),"notification_date":sap_df[date_col].apply(clean_text),"description":sap_df[description_col].apply(clean_text)})

                st.success(f"Excel loaded successfully. {len(set(equipment_values))} equipment records identified.")

                if st.button("🔄 Replace Master With This Excel",type="primary"):

                    eq_count,notification_count=import_new_sap_data(equipment_values,notification_df)

                    st.success(f"Equipment master replaced successfully: {eq_count} equipment | {notification_count} SAP notifications.")

                    st.rerun()

        except Exception as e:
            st.error(f"Unable to process the SAP Excel: {e}")

with tab5:

    st.header("OH Record Upload")

    st.info("Upload OH Excel. Equipment, Date, Description/Work and Order columns are detected automatically.")

    oh_file=st.file_uploader("Upload OH Excel",type=["xlsx","xls"],key="oh_upload")

    if oh_file:

        try:

            oh_df=pd.read_excel(oh_file)

            if st.button("📥 Import OH Records",type="primary"):

                count=save_oh_records(oh_df)

                st.success(f"{count} OH records imported successfully.")

                st.rerun()

        except Exception as e:
            st.error(f"Unable to process OH Excel: {e}")

with tab6:

    st.header("🔩 Spare List")

    st.subheader("Upload Spare List")

    stage_options=["Stage-1","Stage-2","Stage-3","Other"]

    spare_stage=st.selectbox("Stage",stage_options,key="spare_upload_stage")

    spare_system=st.text_input("System",placeholder="Enter system name, e.g. CW System",key="spare_upload_system")

    spare_file=st.file_uploader("Upload Spare Excel",type=["xlsx","xls"],key="spare_upload_file")

    if spare_file and spare_system.strip():

        try:

            spare_df=pd.read_excel(spare_file)

            st.success("Spare Excel loaded successfully.")

            if st.button("📥 Import Spare List",type="primary"):

                count=upload_spare_master(spare_df,spare_stage,spare_system.strip())

                st.success(f"{count} spare records imported successfully.")

                st.rerun()

        except Exception as e:
            st.error(f"Unable to process Spare Excel: {e}")

    st.divider()

    st.subheader("View Spare List")

    available_stages=get_spare_stage_list()

    if available_stages:

        view_stage=st.selectbox("Select Stage",available_stages,key="view_spare_stage")

        available_systems=get_spare_system_list(view_stage)

        if available_systems:

            view_system=st.selectbox("Select System",available_systems,key="view_spare_system")

            spare_view=get_spares_by_stage_system(view_stage,view_system)

            if not spare_view.empty:

                st.dataframe(spare_view.drop(columns=["id"]),use_container_width=True,hide_index=True)

                st.divider()

                st.subheader("🔗 Link Spare to Equipment")

                spare_options={f'{row["Material Code"]} | {row["Description"]}':int(row["id"]) for _,row in spare_view.iterrows()}

                selected_spare_label=st.selectbox("Select Spare",list(spare_options.keys()),key="selected_spare")

                selected_spare_id=spare_options[selected_spare_label]

                equipment_list=get_equipment_list()

                if equipment_list:

                    already_linked=get_spare_linked_equipment(selected_spare_id)

                    selected_equipment_for_spare=st.multiselect("Select Equipment",equipment_list,default=[x for x in already_linked if x in equipment_list],key=f"spare_equipment_{selected_spare_id}")

                    if st.button("🔗 Link Spare to Selected Equipment",type="primary"):

                        link_spare_to_equipment(selected_spare_id,selected_equipment_for_spare)

                        st.success("Spare-equipment mapping updated successfully.")

                        st.rerun()

                else:
                    st.warning("No equipment master available. Upload SAP Excel first.")

            else:
                st.info("No spares found for the selected Stage and System.")

        else:
            st.info("No systems available for the selected stage.")

    else:
        st.info("No spare list has been uploaded yet.")

    st.divider()

    st.subheader("📋 Complete Spare Master")

    all_spares=get_spares()

    if all_spares.empty:
        st.info("No spare records available.")
    else:
        st.dataframe(all_spares.drop(columns=["id"]),use_container_width=True,hide_index=True)

with tab7:

    st.header("🔎 Local Observations")

    equipment_list=get_equipment_list()

    if not equipment_list:

        st.warning("No equipment master is available. Please upload the latest SAP Excel first.")

    else:

        st.subheader("Enter New Observation")

        observation_date=st.date_input("Observation Date",value=date.today(),key="obs_date")

        c1,c2=st.columns(2)

        observation_stage=c1.selectbox("Stage",["Stage-1","Stage-2","Stage-3","Other"],key="obs_stage")

        observation_equipment=c2.selectbox("Equipment",equipment_list,key="obs_equipment")

        defect_description=st.text_area("Defect Description",height=100,key="obs_description")

        c1,c2=st.columns(2)

        severity=c1.selectbox("Severity",["Low","Medium","High"],key="obs_severity")

        status=c2.selectbox("Status",["Pending","Work Completed"],key="obs_status")

        if st.button("💾 Save Observation",type="primary"):

            if not defect_description.strip():
                st.error("Please enter the defect description.")
            else:

                save_local_observation(observation_date,observation_stage,observation_equipment,defect_description,severity,status)

                st.success("Observation saved successfully.")

                st.rerun()

        st.divider()

        st.subheader("📋 Total Local Observations")

        all_observations=get_local_observations()

        if all_observations.empty:

            st.info("No local observations available.")

        else:

            st.dataframe(all_observations.drop(columns=["id"]),use_container_width=True,hide_index=True)

            st.divider()

            st.subheader("✏️ Update Observation Status")

            observation_options={f'{row["Date"]} | {row["Equipment"]} | {row["Defect Description"][:60]}':int(row["id"]) for _,row in all_observations.iterrows()}

            selected_observation=st.selectbox("Select Observation",list(observation_options.keys()),key="status_update_observation")

            selected_observation_id=observation_options[selected_observation]

            selected_row=all_observations[all_observations["id"]==selected_observation_id].iloc[0]

            status_options=["Pending","Work Completed"]

            current_status=str(selected_row["Status"]) if clean_text(selected_row["Status"]) else "Pending"

            status_index=status_options.index(current_status) if current_status in status_options else 0

            updated_status=st.selectbox("New Status",status_options,index=status_index,key="updated_observation_status")

            if st.button("🔄 Update Status",type="primary"):

                update_observation_status(selected_observation_id,updated_status)

                st.success("Observation status updated successfully.")

                st.rerun()
