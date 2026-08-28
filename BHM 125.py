
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="NTPC Equipment Comparison",layout="wide")
st.title("NTPC Multi-Plant Equipment Notification Analysis")

DESC_COL="Description"
FL_COL="Functional Loc."
DATE_COL="Notif.date"

files=st.file_uploader("Upload Plant Excel Files",type=["xlsx"],accept_multiple_files=True)

if files:
    st.subheader("1. Assign Plant Names")
    plant_data={}
    for i,file in enumerate(files):
        plant=st.text_input(f"Plant name for {file.name}",key=f"plant_{i}")
        if plant:
            df=pd.read_excel(file); df["Plant"]=plant; plant_data[plant]=df

    if plant_data:
        st.subheader("2. Common Equipment")
        equipment=st.text_input("Enter common equipment name",placeholder="Example: Cooling Water Pump")

        if equipment:
            st.write("Enter Functional Location of this equipment in each plant:")
            fl_locations={plant:st.text_input(f"{plant} - Functional Location",key=f"fl_{plant}") for plant in plant_data}

            if all(fl_locations.values()):
                result=[]
                for plant,df in plant_data.items():
                    fl=fl_locations[plant].upper(); eq_data=df[df[FL_COL].astype(str).str.upper().str.contains(fl,na=False)].copy(); result.append(eq_data)

                data=pd.concat(result,ignore_index=True)

                st.subheader(f"3. {equipment} Dashboard")

                def classify(x):
                    x=str(x).lower()
                    if any(k in x for k in ["gland leak","gland leakage","packing leak"]): return "Gland Leak"
                    if any(k in x for k in ["vibration","vibrational"]): return "Vibration"
                    if any(k in x for k in ["jam","jamming","stuck"]): return "Jamming"
                    if any(k in x for k in ["abnormal sound","noise","abnormal noise"]): return "Abnormal Sound"
                    if any(k in x for k in ["leak","leakage"]): return "Other Leakage"
                    if any(k in x for k in ["temperature","heating","overheat"]): return "High Temperature"
                    if any(k in x for k in ["pressure","low pressure","high pressure"]): return "Pressure Issue"
                    return "Others"

                data["Defect Category"]=data[DESC_COL].apply(classify)

                categories=["Gland Leak","Vibration","Jamming","Abnormal Sound","Other Leakage","High Temperature","Pressure Issue","Others"]

                dashboard=data.groupby(["Plant","Defect Category"]).size().unstack(fill_value=0).reset_index()

                for c in categories:
                    if c not in dashboard.columns: dashboard[c]=0

                dashboard=dashboard[["Plant"]+categories]; dashboard.insert(0,"S.No",range(1,len(dashboard)+1))

                st.subheader("Plant-wise Defect Category Summary")
                st.dataframe(dashboard,use_container_width=True,hide_index=True)

                total=data.groupby("Plant").size().reset_index(name="Total Notifications")
                st.subheader("Total Notifications")
                st.dataframe(total,use_container_width=True,hide_index=True)

                chart_data=dashboard.melt(id_vars=["S.No","Plant"],value_vars=categories,var_name="Defect Category",value_name="Notifications")

                fig=px.bar(chart_data,x="Plant",y="Notifications",color="Defect Category",barmode="group",text="Notifications")
                fig.update_traces(textposition="outside")
                fig.update_layout(xaxis_title="Plant",yaxis_title="Number of Notifications",legend_title="Defect Category")
                st.plotly_chart(fig,use_container_width=True)

                st.subheader("Overall Defect Category Comparison")
                category_total=data["Defect Category"].value_counts().reset_index()
                category_total.columns=["Defect Category","Notifications"]

                fig2=px.bar(category_total,x="Defect Category",y="Notifications",text="Notifications")
                fig2.update_traces(textposition="outside")
                st.plotly_chart(fig2,use_container_width=True)

                with st.expander("View Detailed Notifications"):
                    st.dataframe(data,use_container_width=True,hide_index=True)
