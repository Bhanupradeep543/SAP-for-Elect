import streamlit as st
import pandas as pd

st.set_page_config(page_title="NTPC Plant Notification Analysis",layout="wide")
st.title("NTPC Plant Notification Analysis")

files=st.file_uploader("Upload Plant Notification Excel Files",type=["xlsx"],accept_multiple_files=True)

plant_data={}
if files:
    st.subheader("Enter Plant Names")
    for i,file in enumerate(files):
        plant=st.text_input(f"Plant name for {file.name}",key=f"plant_{i}")
        if plant:
            df=pd.read_excel(file)
            plant_data[plant]=df

    if len(plant_data)>=2:
        st.subheader("Common Equipment Across All Plants")
        
        equipment_col=st.selectbox(
            "Select Equipment Column",
            list(next(iter(plant_data.values())).columns)
        )

        equipment_sets=[]
        for plant,df in plant_data.items():
            if equipment_col in df.columns:
                equipment_sets.append(set(df[equipment_col].dropna().astype(str).str.strip()))

        if equipment_sets:
            common_equipment=set.intersection(*equipment_sets)
            if common_equipment:
                common_df=pd.DataFrame({"Common Equipment":sorted(common_equipment)})
                st.dataframe(common_df,use_container_width=True)
                st.success(f"{len(common_equipment)} common equipment found.")
            else:
                st.warning("No common equipment found across all plants.")
