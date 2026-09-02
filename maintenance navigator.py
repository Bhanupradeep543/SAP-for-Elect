import streamlit as st
import sqlite3
import pandas as pd
from datetime import date,datetime
from pathlib import Path
import uuid,json,re

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR=Path(__file__).resolve().parent
DB_FILE=BASE_DIR/"maintenance_history.db"
IMAGE_DIR=BASE_DIR/"maintenance_images"
OH_UPLOAD_DIR=BASE_DIR/"oh_records"
IMAGE_DIR.mkdir(exist_ok=True)
OH_UPLOAD_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="Maintenance Navigator",page_icon="🔧",layout="wide")

# ============================================================
# DATABASE
# ============================================================

def get_connection():
    conn=sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def initialize_database():
    conn=get_connection(); cursor=conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS equipment_master(id INTEGER PRIMARY KEY AUTOINCREMENT,equipment_name TEXT UNIQUE NOT NULL,created_at TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS maintenance_records(id INTEGER PRIMARY KEY AUTOINCREMENT,maintenance_date TEXT,stage TEXT,maintenance_type TEXT,equipment_name TEXT,order_number TEXT,work_carried_out TEXT,materials_consumed TEXT,image_path TEXT,created_at TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS sap_notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,notification_date TEXT,equipment_name TEXT,description TEXT,created_at TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS oh_records(id INTEGER PRIMARY KEY AUTOINCREMENT,oh_date TEXT,equipment_name TEXT,order_number TEXT,description TEXT,file_path TEXT,created_at TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS spare_master(id INTEGER PRIMARY KEY AUTOINCREMENT,stage TEXT,system_name TEXT,s_no TEXT,material_code TEXT,spare_description TEXT,uom TEXT,quantity REAL,location TEXT,created_at TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS spare_equipment_mapping(id INTEGER PRIMARY KEY AUTOINCREMENT,spare_id INTEGER NOT NULL,equipment_name TEXT NOT NULL,created_at TEXT,FOREIGN KEY(spare_id) REFERENCES spare_master(id) ON DELETE CASCADE)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS local_observations(id INTEGER PRIMARY KEY AUTOINCREMENT,observation_date TEXT,stage TEXT,equipment_name TEXT,defect_description TEXT,severity TEXT,status TEXT,created_at TEXT)""")

    def cols(table):
        cursor.execute(f"PRAGMA table_info({table})")
        return [r[1] for r in cursor.fetchall()]

    mc=cols("maintenance_records")
    for col,typ in [("maintenance_type","TEXT"),("materials_consumed","TEXT"),("image_path","TEXT"),("created_at","TEXT")]:
        if col not in mc: cursor.execute(f"ALTER TABLE maintenance_records ADD COLUMN {col} {typ}")

    sc=cols("sap_notifications")
    for col,typ in [("notification_date","TEXT"),("equipment_name","TEXT"),("description","TEXT"),("created_at","TEXT")]:
        if col not in sc: cursor.execute(f"ALTER TABLE sap_notifications ADD COLUMN {col} {typ}")

    oc=cols("local_observations")
    if "status" not in oc: cursor.execute("ALTER TABLE local_observations ADD COLUMN status TEXT")

    conn.commit(); conn.close()

initialize_database()

# ============================================================
# COMMON FUNCTIONS
# ============================================================

def clean_text(value):
    return "" if pd.isna(value) else str(value).strip()

def find_column(df,keywords):
    if isinstance(keywords,str): keywords=[keywords]
    for c in df.columns:
        for k in keywords:
            if k.lower() in str(c).strip().lower(): return c
    return None

def get_equipment_list():
    conn=get_connection(); df=pd.read_sql_query("SELECT equipment_name FROM equipment_master ORDER BY equipment_name",conn); conn.close()
    return [] if df.empty else df["equipment_name"].dropna().astype(str).tolist()

# ============================================================
# SAP MASTER
# ============================================================

def import_new_sap_data(equipment_list,notification_df):
    conn=get_connection()
    try:
        cursor=conn.cursor(); cursor.execute("DELETE FROM equipment_master"); equipment_list=sorted(set(clean_text(x) for x in equipment_list if clean_text(x)))
        cursor.executemany("INSERT INTO equipment_master(equipment_name,created_at) VALUES(?,?)",[(x,datetime.now().isoformat()) for x in equipment_list])
        cursor.execute("DELETE FROM sap_notifications")
        rows=[(clean_text(r["equipment_name"]),clean_text(r["notification_date"]),clean_text(r["description"]),datetime.now().isoformat()) for _,r in notification_df.iterrows() if clean_text(r["equipment_name"])]
        cursor.executemany("INSERT INTO sap_notifications(notification_date,equipment_name,description,created_at) VALUES(?,?,?,?)",rows)
        conn.commit(); return len(equipment_list),len(rows)
    except Exception:
        conn.rollback(); raise
    finally: conn.close()

# ============================================================
# MAINTENANCE
# ============================================================

def save_record(maintenance_date,stage,maintenance_type,equipment_name,order_number,work_carried_out,materials,image_paths):
    conn=get_connection(); conn.execute("""INSERT INTO maintenance_records(maintenance_date,stage,maintenance_type,equipment_name,order_number,work_carried_out,materials_consumed,image_path,created_at) VALUES(?,?,?,?,?,?,?,?,?)""",(str(maintenance_date),stage,maintenance_type,equipment_name,order_number,work_carried_out,json.dumps(materials),json.dumps(image_paths),datetime.now().isoformat())); conn.commit(); conn.close()

def get_maintenance_record(record_id):
    conn=get_connection(); df=pd.read_sql_query("SELECT * FROM maintenance_records WHERE id=?",conn,params=(record_id,)); conn.close(); return None if df.empty else df.iloc[0].to_dict()

def update_maintenance_record(record_id,maintenance_date,stage,maintenance_type,equipment_name,order_number,work_carried_out,materials,image_paths):
    conn=get_connection(); conn.execute("""UPDATE maintenance_records SET maintenance_date=?,stage=?,maintenance_type=?,equipment_name=?,order_number=?,work_carried_out=?,materials_consumed=?,image_path=? WHERE id=?""",(str(maintenance_date),stage,maintenance_type,equipment_name,order_number,work_carried_out,json.dumps(materials),json.dumps(image_paths),record_id)); conn.commit(); conn.close()

def get_equipment_history(equipment):
    conn=get_connection(); df=pd.read_sql_query("""SELECT id,maintenance_date AS Date,stage AS Stage,maintenance_type AS Type,order_number AS "Order Number",work_carried_out AS "Work Carried Out" FROM maintenance_records WHERE equipment_name=? ORDER BY maintenance_date DESC""",conn,params=(equipment,)); conn.close(); return df

def get_all_records():
    conn=get_connection(); df=pd.read_sql_query("""SELECT id,maintenance_date AS Date,stage AS Stage,maintenance_type AS Type,equipment_name AS Equipment,order_number AS "Order Number",work_carried_out AS "Work Carried Out" FROM maintenance_records ORDER BY maintenance_date DESC""",conn); conn.close(); return df

def save_uploaded_images(files,equipment):
    if not files:return []
    folder=IMAGE_DIR/re.sub(r"[^A-Za-z0-9_-]","_",equipment); folder.mkdir(exist_ok=True); paths=[]
    for f in files:
        p=folder/(datetime.now().strftime("%Y%m%d_%H%M%S_")+str(uuid.uuid4())[:8]+Path(f.name).suffix)
        with open(p,"wb") as out: out.write(f.getbuffer())
        paths.append(str(p))
    return paths

# ============================================================
# SAP / OH
# ============================================================

def get_equipment_notifications(equipment):
    conn=get_connection(); df=pd.read_sql_query("""SELECT notification_date AS Date,description AS Notification FROM sap_notifications WHERE equipment_name=? ORDER BY notification_date DESC""",conn,params=(equipment,)); conn.close(); return df

def save_oh_records(df):
    ec=find_column(df,"equipment"); dc=find_column(df,"date"); desc=find_column(df,["description","work"]); oc=find_column(df,"order")
    if not ec: raise ValueError("Equipment column could not be identified.")
    if not dc: raise ValueError("Date column could not be identified.")
    rows=[]
    for _,r in df.iterrows():
        eq=clean_text(r[ec])
        if eq: rows.append((clean_text(r[dc]),eq,clean_text(r[oc]) if oc else "",clean_text(r[desc]) if desc else "",datetime.now().isoformat()))
    conn=get_connection(); conn.executemany("INSERT INTO oh_records(oh_date,equipment_name,order_number,description,created_at) VALUES(?,?,?,?,?)",rows); conn.commit(); conn.close(); return len(rows)

def get_oh_records(equipment):
    conn=get_connection(); df=pd.read_sql_query("""SELECT oh_date AS Date,order_number AS "Order Number",description AS Description FROM oh_records WHERE equipment_name=? ORDER BY oh_date DESC""",conn,params=(equipment,)); conn.close(); return df

# ============================================================
# LOCAL OBSERVATIONS
# ============================================================

def save_local_observation(observation_date,stage,equipment,description,severity,status):
    conn=get_connection(); conn.execute("""INSERT INTO local_observations(observation_date,stage,equipment_name,defect_description,severity,status,created_at) VALUES(?,?,?,?,?,?,?)""",(str(observation_date),stage,equipment,description,severity,status,datetime.now().isoformat())); conn.commit(); conn.close()

def get_local_observations(equipment=None):
    conn=get_connection()
    if equipment:
        df=pd.read_sql_query("""SELECT id,observation_date AS Date,stage AS Stage,defect_description AS "Defect Description",severity AS Severity,status AS Status FROM local_observations WHERE equipment_name=? ORDER BY observation_date DESC""",conn,params=(equipment,))
    else:
        df=pd.read_sql_query("""SELECT id,observation_date AS Date,stage AS Stage,equipment_name AS Equipment,defect_description AS "Defect Description",severity AS Severity,status AS Status FROM local_observations ORDER BY observation_date DESC""",conn)
    conn.close(); return df

def update_observation_status(observation_id,status):
    conn=get_connection(); conn.execute("UPDATE local_observations SET status=? WHERE id=?",(status,observation_id)); conn.commit(); conn.close()

# ============================================================
# SPARES
# ============================================================

def upload_spare_master(df,stage,system):
    sn=find_column(df,["s.no","s no","serial"]); mc=find_column(df,["material code","material","spare"]); dc=find_column(df,"description"); uc=find_column(df,["uom","unit"]); qc=find_column(df,["qty","quantity"]); lc=find_column(df,"location")
    if not mc: raise ValueError("Material Code column could not be identified.")
    conn=get_connection(); cursor=conn.cursor(); rows=[]
    for _,r in df.iterrows():
        material=clean_text(r[mc])
        if not material: continue
        try: qty=float(r[qc]) if qc and not pd.isna(r[qc]) else 0
        except: qty=0
        rows.append((stage,system,clean_text(r[sn]) if sn else "",material,clean_text(r[dc]) if dc else "",clean_text(r[uc]) if uc else "",qty,clean_text(r[lc]) if lc else "",datetime.now().isoformat()))
    cursor.executemany("""INSERT INTO spare_master(stage,system_name,s_no,material_code,spare_description,uom,quantity,location,created_at) VALUES(?,?,?,?,?,?,?,?,?)""",rows); conn.commit(); conn.close(); return len(rows)

def get_spare_stage_list():
    conn=get_connection(); df=pd.read_sql_query("SELECT DISTINCT stage FROM spare_master WHERE stage<>'' ORDER BY stage",conn); conn.close(); return df["stage"].tolist() if not df.empty else []

def get_spare_system_list(stage=None):
    conn=get_connection()
    if stage: df=pd.read_sql_query("SELECT DISTINCT system_name FROM spare_master WHERE stage=? AND system_name<>'' ORDER BY system_name",conn,params=(stage,))
    else: df=pd.read_sql_query("SELECT DISTINCT system_name FROM spare_master WHERE system_name<>'' ORDER BY system_name",conn)
    conn.close(); return df["system_name"].tolist() if not df.empty else []

def get_spares_by_stage_system(stage,system):
    conn=get_connection(); df=pd.read_sql_query("""SELECT id,s_no AS "S.No",material_code AS "Material Code",spare_description AS Description,uom AS UOM,quantity AS Qty,location AS Location FROM spare_master WHERE stage=? AND system_name=? ORDER BY id""",conn,params=(stage,system)); conn.close(); return df

def get_spares():
    conn=get_connection(); df=pd.read_sql_query("""SELECT id,stage AS Stage,system_name AS System,"""+"""s_no AS "S.No",material_code AS "Material Code",spare_description AS Description,uom AS UOM,quantity AS Qty,location AS Location FROM spare_master ORDER BY stage,system_name,material_code""",conn); conn.close(); return df

def link_spare_to_equipment(spare_id,equipment_list):
    conn=get_connection(); conn.execute("DELETE FROM spare_equipment_mapping WHERE spare_id=?",(spare_id,)); conn.executemany("INSERT INTO spare_equipment_mapping(spare_id,equipment_name,created_at) VALUES(?,?,?)",[(spare_id,e,datetime.now().isoformat()) for e in equipment_list]); conn.commit(); conn.close()

def get_equipment_spares(equipment):
    conn=get_connection(); df=pd.read_sql_query("""SELECT s.stage AS Stage,s.system_name AS System,s.s_no AS "S.No",s.material_code AS "Material Code",s.spare_description AS Description,s.uom AS UOM,s.quantity AS Qty,s.location AS Location FROM spare_master s INNER JOIN spare_equipment_mapping m ON s.id=m.spare_id WHERE m.equipment_name=? ORDER BY s.stage,s.system_name,s.material_code""",conn,params=(equipment,)); conn.close(); return df

# ============================================================
# SIDEBAR
# ============================================================

equipment_list=get_equipment_list()
st.sidebar.title("🔧 Maintenance Navigator")
st.sidebar.info(f"Current Equipment Master: {len(equipment_list)} equipment")

# ============================================================
# TABS
# ============================================================

tab1,tab2,tab3,tab4,tab5,tab6,tab7=st.tabs(["🛠 Maintenance Entry","📋 Equipment History","📊 All Maintenance Records","📥 SAP Notification Upload","🔄 OH Record Upload","🔩 Spare List","🔎 Local Observations"])

# ============================================================
# TAB 1 - MAINTENANCE ENTRY
# ============================================================

with tab1:
    st.header("Maintenance Entry")
    equipment_list=get_equipment_list()
    if not equipment_list: st.warning("No equipment master is available. Please upload the SAP Excel first.")
    else:
        maintenance_date=st.date_input("Maintenance Date",value=date.today())
        stage=st.selectbox("Stage",["Stage-1","Stage-2","Stage-3","Other"],key="maintenance_stage")
        maintenance_type=st.selectbox("Maintenance Type",["Defect","PM","OH"],key="maintenance_type")
        equipment_name=st.selectbox("Equipment",equipment_list,key="maintenance_equipment")
        order_number=st.text_input("Order Number")
        work_carried_out=st.text_area("Work Carried Out")
        st.subheader("Materials Consumed")
        if "materials" not in st.session_state: st.session_state.materials=[{"Material":"","UOM":"","Qty":0.0}]
        for i,m in enumerate(st.session_state.materials):
            c1,c2,c3,c4=st.columns([3,2,1.5,1])
            with c1: m["Material"]=st.text_input("Material",m["Material"],key=f"mat_{i}")
            with c2: m["UOM"]=st.text_input("UOM",m["UOM"],key=f"uom_{i}")
            with c3: m["Qty"]=st.number_input("Qty",min_value=0.0,value=float(m["Qty"]),key=f"qty_{i}")
            with c4:
                if st.button("❌",key=f"delmat_{i}"): st.session_state.materials.pop(i); st.rerun()
        if st.button("➕ Add Material"): st.session_state.materials.append({"Material":"","UOM":"","Qty":0.0}); st.rerun()
        uploaded_images=st.file_uploader("Maintenance Images",type=["jpg","jpeg","png"],accept_multiple_files=True,key="maintenance_images")
        if st.button("💾 Save Maintenance Record",type="primary"):
            if not work_carried_out.strip(): st.error("Please enter the work carried out.")
            else:
                paths=save_uploaded_images(uploaded_images,equipment_name); save_record(maintenance_date,stage,maintenance_type,equipment_name,order_number,work_carried_out,st.session_state.materials,paths); st.session_state.materials=[{"Material":"","UOM":"","Qty":0.0}]; st.success("Maintenance record saved successfully."); st.rerun()

# ============================================================
# TAB 2 - EQUIPMENT HISTORY
# ============================================================

with tab2:
    st.header("Equipment History")
    equipment_list=get_equipment_list()
    if not equipment_list: st.warning("No equipment list is available. Please upload SAP Excel.")
    else:
        selected_equipment=st.selectbox("Select Equipment",equipment_list,key="history_equipment")

        st.subheader("🛠 Maintenance History")
        history_df=get_equipment_history(selected_equipment)
        if history_df.empty: st.info("No manual maintenance records available.")
        else:
            for _,row in history_df.iterrows():
                c1,c2,c3,c4,c5,c6=st.columns([1.2,1.2,1.2,1.5,4,1])
                c1.write(row["Date"]); c2.write(row["Stage"]); c3.write(row["Type"]); c4.write(row["Order Number"]); c5.write(row["Work Carried Out"])
                if c6.button("✏️ Edit",key=f"edit_{row['id']}"): st.session_state.edit_record_id=int(row["id"]); st.rerun()

        # ----------------------------------------------------
        # EDIT MAINTENANCE
        # ----------------------------------------------------

        if "edit_record_id" in st.session_state:
            rid=st.session_state.edit_record_id; record=get_maintenance_record(rid)
            if record:
                st.divider(); st.subheader(f"✏️ Edit Maintenance Record #{rid}")
                try: edit_date=datetime.strptime(str(record.get("maintenance_date")),"%Y-%m-%d").date()
                except: edit_date=date.today()
                edit_date=st.date_input("Maintenance Date",edit_date,key=f"edate_{rid}")
                stages=["Stage-1","Stage-2","Stage-3","Other"]; current_stage=record.get("stage") or "Stage-1"; current_stage=current_stage if current_stage in stages else stages[0]; edit_stage=st.selectbox("Stage",stages,index=stages.index(current_stage),key=f"estage_{rid}")
                types=["Defect","PM","OH"]; current_type=record.get("maintenance_type") or "Defect"; current_type=current_type if current_type in types else types[0]; edit_type=st.selectbox("Maintenance Type",types,index=types.index(current_type),key=f"etype_{rid}")
                equipment_options=get_equipment_list(); current_equipment=record.get("equipment_name")
                if current_equipment and current_equipment not in equipment_options: equipment_options.append(current_equipment)
                edit_equipment=st.selectbox("Equipment",equipment_options,index=equipment_options.index(current_equipment),key=f"eequipment_{rid}")
                edit_order=st.text_input("Order Number",record.get("order_number") or "",key=f"eorder_{rid}")
                edit_work=st.text_area("Work Carried Out",record.get("work_carried_out") or "",key=f"ework_{rid}")
                try: existing_materials=json.loads(record.get("materials_consumed") or "[]")
                except: existing_materials=[]
                if "edit_materials" not in st.session_state: st.session_state.edit_materials=existing_materials or [{"Material":"","UOM":"","Qty":0.0}]
                st.subheader("Materials Consumed")
                for i,m in enumerate(st.session_state.edit_materials):
                    c1,c2,c3,c4=st.columns([3,2,1.5,1]); m["Material"]=c1.text_input("Material",m.get("Material",""),key=f"emat_{rid}_{i}"); m["UOM"]=c2.text_input("UOM",m.get("UOM",""),key=f"euom_{rid}_{i}"); m["Qty"]=c3.number_input("Qty",min_value=0.0,value=float(m.get("Qty",0)),key=f"eqty_{rid}_{i}")
                    if c4.button("❌",key=f"edel_{rid}_{i}"): st.session_state.edit_materials.pop(i); st.rerun()
                if st.button("➕ Add Material",key=f"eadd_{rid}"): st.session_state.edit_materials.append({"Material":"","UOM":"","Qty":0.0}); st.rerun()
                try: existing_images=json.loads(record.get("image_path") or "[]")
                except: existing_images=[]
                if existing_images:
                    st.subheader("Existing Images")
                    for p in existing_images:
                        if Path(p).exists(): st.image(p,width=250)
                new_images=st.file_uploader("Add New Images",type=["jpg","jpeg","png"],accept_multiple_files=True,key=f"eimages_{rid}")
                csave,ccancel=st.columns(2)
                if csave.button("💾 Update Record",type="primary",key=f"update_{rid}"):
                    new_paths=save_uploaded_images(new_images,edit_equipment); update_maintenance_record(rid,edit_date,edit_stage,edit_type,edit_equipment,edit_order,edit_work,st.session_state.edit_materials,existing_images+new_paths); del st.session_state.edit_record_id; st.session_state.pop("edit_materials",None); st.success("Maintenance record updated successfully."); st.rerun()
                if ccancel.button("Cancel",key=f"cancel_{rid}"): del st.session_state.edit_record_id; st.session_state.pop("edit_materials",None); st.rerun()

        # ----------------------------------------------------
        # LOCAL OBSERVATIONS
        # ----------------------------------------------------

        st.divider(); st.subheader("🔎 Local Observations")
        observation_df=get_local_observations(selected_equipment)
        if observation_df.empty: st.info("No local observations available for this equipment.")
        else:
            for _,row in observation_df.iterrows():
                c1,c2,c3,c4,c5=st.columns([1.2,1.2,4,1.5,2])
                c1.write(row["Date"]); c2.write(row["Stage"]); c3.write(row["Defect Description"]); c4.write(row["Severity"])
                new_status=c5.selectbox("Status",["Pending","Work Completed"],index=0 if row["Status"]!="Work Completed" else 1,key=f"histstatus_{row['id']}")
                if new_status!=row["Status"]: update_observation_status(int(row["id"]),new_status); st.rerun()

        # ----------------------------------------------------
        # SAP
        # ----------------------------------------------------

        st.divider(); st.subheader("📢 SAP Notifications")
        notification_df=get_equipment_notifications(selected_equipment)
        if notification_df.empty: st.info("No SAP notifications available.")
        else: st.dataframe(notification_df,use_container_width=True,hide_index=True)

        # ----------------------------------------------------
        # OH
        # ----------------------------------------------------

        st.divider(); st.subheader("🔄 OH Records")
        oh_df=get_oh_records(selected_equipment)
        if oh_df.empty: st.info("No OH records available.")
        else: st.dataframe(oh_df,use_container_width=True,hide_index=True)

        # ----------------------------------------------------
        # SPARES
        # ----------------------------------------------------

        st.divider(); st.subheader("🔩 Linked Spares")
        equipment_spares=get_equipment_spares(selected_equipment)
        if equipment_spares.empty: st.info("No spares linked to this equipment.")
        else: st.dataframe(equipment_spares,use_container_width=True,hide_index=True)

# ============================================================
# TAB 3 - ALL MAINTENANCE RECORDS
# ============================================================

with tab3:
    st.header("All Maintenance Records")
    all_records=get_all_records()
    if all_records.empty: st.info("No maintenance records available.")
    else: st.dataframe(all_records,use_container_width=True,hide_index=True)

# ============================================================
# TAB 4 - SAP UPLOAD
# ============================================================

with tab4:
    st.header("SAP Notification Upload")
    st.info("A new SAP Excel completely replaces the current Equipment Master and SAP Notification History. Manual Maintenance, Local Observations, OH Records and Spare data are retained.")
    sap_file=st.file_uploader("Upload SAP Notification Excel",type=["xlsx","xls"],key="sap_upload")
    if sap_file:
        try:
            df=pd.read_excel(sap_file); ec=find_column(df,"equipment"); dc=find_column(df,"description"); dt=find_column(df,"date")
            if not ec: st.error("Equipment column could not be identified.")
            elif not dc: st.error("Description column could not be identified.")
            elif not dt: st.error("Date column could not be identified.")
            else:
                notification_df=pd.DataFrame({"equipment_name":df[ec].apply(clean_text),"notification_date":df[dt].apply(clean_text),"description":df[dc].apply(clean_text)})
                notification_df=notification_df[notification_df["equipment_name"]!=""]; new_equipment=sorted(notification_df["equipment_name"].unique().tolist())
                st.success(f"Excel processed successfully. {len(new_equipment)} equipment identified.")
                if st.button("🔄 Replace Master With This Excel",type="primary"):
                    ecnt,ncnt=import_new_sap_data(new_equipment,notification_df); st.session_state.pop("history_equipment",None); st.success(f"Equipment Master replaced successfully. {ecnt} equipment and {ncnt} SAP notifications imported."); st.rerun()
        except Exception as e: st.error(f"Error processing Excel: {e}")

# ============================================================
# TAB 5 - OH UPLOAD
# ============================================================

with tab5:
    st.header("🔄 OH Record Upload")
    st.info("Upload the OH Excel file. Equipment, Date, Description and Order columns are identified automatically.")
    oh_file=st.file_uploader("Upload OH Excel",type=["xlsx","xls"],key="oh_upload")
    if oh_file:
        try:
            oh_df=pd.read_excel(oh_file); ec=find_column(oh_df,"equipment"); dc=find_column(oh_df,"date")
            if not ec: st.error("Equipment column could not be identified.")
            elif not dc: st.error("Date column could not be identified.")
            elif st.button("📥 Import OH Records",type="primary"):
                count=save_oh_records(oh_df); st.success(f"{count} OH records imported successfully."); st.rerun()
        except Exception as e: st.error(f"Error processing OH Excel: {e}")

# ============================================================
# TAB 6 - SPARE LIST
# ============================================================

with tab6:
    st.header("🔩 Spare List")
    st.subheader("Upload Spare List")
    st.info("Excel columns expected: S.No, Material Code, Description, UOM, Qty and Location.")
    spare_stage=st.selectbox("Stage",["Stage-1","Stage-2","Stage-3","Other"],key="spare_stage_upload")
    spare_system=st.text_input("System",placeholder="Enter system name, e.g. CW System / CT System / Boiler Feed Pump System",key="spare_system_upload")
    spare_file=st.file_uploader("Upload Spare List Excel",type=["xlsx","xls"],key="spare_upload")
    if spare_file and spare_system.strip():
        try:
            spare_excel_df=pd.read_excel(spare_file)
            st.success(f"Spare Excel loaded: {len(spare_excel_df)} rows.")
            if st.button("📥 Import Spare List",type="primary"):
                count=upload_spare_master(spare_excel_df,spare_stage,spare_system.strip()); st.success(f"{count} spare records imported for {spare_stage} → {spare_system}."); st.rerun()
        except Exception as e: st.error(f"Error processing Spare Excel: {e}")

    st.divider()
    st.subheader("View Spares by Stage and System")
    available_stages=get_spare_stage_list()
    if available_stages:
        view_stage=st.selectbox("Select Stage",available_stages,key="view_spare_stage")
        available_systems=get_spare_system_list(view_stage)
        if available_systems:
            view_system=st.selectbox("Select System",available_systems,key="view_spare_system")
            selected_spares=get_spares_by_stage_system(view_stage,view_system)
            if selected_spares.empty: st.info("No spare data available.")
            else: st.dataframe(selected_spares.drop(columns=["id"]),use_container_width=True,hide_index=True)

            st.divider()
            st.subheader("Link Spares to Equipment")
            equipment_list=get_equipment_list()
            if not selected_spares.empty and equipment_list:
                spare_options={f"{r['Material Code']} - {r['Description']}":int(r["id"]) for _,r in selected_spares.iterrows()}
                selected_spare_label=st.selectbox("Select Spare",list(spare_options.keys()),key="link_spare")
                selected_spare_id=spare_options[selected_spare_label]
                selected_equipment=st.multiselect("Select Equipment",equipment_list,key="spare_equipment_link")
                if st.button("🔗 Link Spare to Equipment",type="primary"):
                    if not selected_equipment: st.error("Please select at least one equipment.")
                    else: link_spare_to_equipment(selected_spare_id,selected_equipment); st.success("Spare linked successfully."); st.rerun()
        else: st.info("No system data available for the selected stage.")
    else: st.info("No spare lists have been uploaded yet.")

# ============================================================
# TAB 7 - LOCAL OBSERVATIONS
# ============================================================

with tab7:
    st.header("🔎 Local Observations")
    equipment_list=get_equipment_list()
    if not equipment_list:
        st.warning("No equipment master is available. Please upload the SAP Excel first.")
    else:
        st.subheader("Enter New Observation")
        observation_date=st.date_input("Observation Date",value=date.today(),key="obs_date")
        observation_stage=st.selectbox("Stage",["Stage-1","Stage-2","Stage-3","Other"],key="obs_stage")
        observation_equipment=st.selectbox("Equipment",equipment_list,key="obs_equipment")
        defect_description=st.text_area("Defect Description",placeholder="Enter observed defect / abnormality...",key="obs_description")
        severity=st.selectbox("Severity",["Low","Medium","High"],key="obs_severity")
        status=st.selectbox("Status",["Pending","Work Completed"],key="obs_status")
        if st.button("💾 Save Observation",type="primary"):
            if not defect_description.strip(): st.error("Please enter the defect description.")
            else:
                save_local_observation(observation_date,observation_stage,observation_equipment,defect_description,severity,status); st.success("Local observation saved successfully."); st.rerun()

        st.divider()
        st.subheader("📋 Total Local Observations")
        all_observations=get_local_observations()
        if all_observations.empty: st.info("No local observations have been entered.")
        else:
            st.dataframe(all_observations.drop(columns=["id"]),use_container_width=True,hide_index=True)

            st.subheader("Update Observation Status")
            observation_options={f"{r['Date']} | {r['Equipment']} | {r['Defect Description']}":int(r["id"]) for _,r in all_observations.iterrows()}
            selected_observation=st.selectbox("Select Observation",list(observation_options.keys()),key="status_observation")
            selected_observation_id=observation_options[selected_observation]
            selected_status=st.selectbox("Change Status",["Pending","Work Completed"],key="change_observation_status")
            if st.button("🔄 Update Status",type="primary"):
                update_observation_status(selected_observation_id,selected_status); st.success("Observation status updated successfully."); st.rerun()
