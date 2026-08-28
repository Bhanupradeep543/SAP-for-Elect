import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="NTPC Plant System Dashboard",layout="wide")
st.title("NTPC Plant & System Wise Notification Dashboard")

files=st.file_uploader("Upload Plant Notification Excel Files",type=["xlsx"],accept_multiple_files=True)

plant_data={}

if files:
    st.subheader("Enter Plant Names")

    for i,file in enumerate(files):
        plant=st.text_input(f"Enter Plant Name for {file.name}",key=f"plant_{i}")

        if plant:
            df=pd.read_excel(file)

            if "Functional Loc." not in df.columns:
                st.error(f"'Functional Loc.' column not found in {file.name}")
                continue

            floc=df["Functional Loc."].fillna("").astype("string").str.upper()
            df["System"]="Others"
            df.loc[floc.str.contains("CWS",na=False),"System"]="CW System"
            df.loc[floc.str.contains("CLT",na=False),"System"]="CT System"
            df["Plant"]=plant

            plant_data[plant]=df

    if plant_data:

        data=pd.concat(plant_data.values(),ignore_index=True)

        summary=data.groupby(["Plant","System"]).size().unstack(fill_value=0).reset_index()

        for col in ["CW System","CT System","Others"]:
            if col not in summary.columns:
                summary[col]=0

        summary=summary[["Plant","CW System","CT System","Others"]]
        summary.insert(0,"S.No",range(1,len(summary)+1))

        st.subheader("Plant-wise System Notification Summary")

        st.dataframe(summary,use_container_width=True,hide_index=True)

        c1,c2,c3=st.columns(3)

        c1.metric("CW System",int(data["System"].eq("CW System").sum()))
        c2.metric("CT System",int(data["System"].eq("CT System").sum()))
        c3.metric("Others",int(data["System"].eq("Others").sum()))

        chart_data=summary.melt(
            id_vars=["S.No","Plant"],
            value_vars=["CW System","CT System","Others"],
            var_name="System",
            value_name="Notifications"
        )

        fig=px.bar(
            chart_data,
            x="Plant",
            y="Notifications",
            color="System",
            barmode="group",
            text="Notifications"
        )

        fig.update_traces(textposition="outside")
        fig.update_layout(
            xaxis_title="Plant",
            yaxis_title="Number of Notifications",
            legend_title="System"
        )

        st.plotly_chart(fig,use_container_width=True)
