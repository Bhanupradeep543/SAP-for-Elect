import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="NTPC Plant System Dashboard",layout="wide")
st.title("NTPC Plant & System Wise Notification Dashboard")

files=st.file_uploader("Upload Plant Notification Excel Files",type=["xlsx"],accept_multiple_files=True)

plant_data={}

if files:
    st.subheader("Plant Names")
    for i,file in enumerate(files):
        plant=st.text_input(f"Enter Plant Name for {file.name}",key=f"plant_{i}")
        if plant:
            df=pd.read_excel(file)
            if "Functional Loc." not in df.columns:
                st.error(f"'Functional Loc.' column not found in {file.name}")
                continue
            df["System"]=df["Functional Loc."].astype(str).str.upper().apply(lambda x:"CW System" if "CWS" in x else ("CT System" if "CLT" in x else "Other"))
            df["Plant"]=plant
            plant_data[plant]=df

    if plant_data:
        data=pd.concat(plant_data.values(),ignore_index=True)

        st.subheader("Plant & System Wise Dashboard")

        c1,c2,c3=st.columns(3)
        c1.metric("Total Notifications",len(data))
        c2.metric("CW System",len(data[data["System"]=="CW System"]))
        c3.metric("CT System",len(data[data["System"]=="CT System"]))

        summary=data.groupby(["Plant","System"]).size().reset_index(name="Notifications")

        st.subheader("Plant-wise System Summary")
        st.dataframe(summary,use_container_width=True)

        fig=px.bar(summary,x="Plant",y="Notifications",color="System",barmode="group",text="Notifications")
        st.plotly_chart(fig,use_container_width=True)

        st.subheader("System-wise Plant Comparison")
        system_summary=data[data["System"].isin(["CW System","CT System"])].groupby(["System","Plant"]).size().reset_index(name="Notifications")

        fig2=px.bar(system_summary,x="Plant",y="Notifications",color="System",barmode="group",text="Notifications")
        st.plotly_chart(fig2,use_container_width=True)

        st.subheader("System Distribution")
        system_count=data[data["System"].isin(["CW System","CT System"])].groupby("System").size().reset_index(name="Notifications")
        fig3=px.pie(system_count,names="System",values="Notifications",hole=0.4)
        st.plotly_chart(fig3,use_container_width=True)
