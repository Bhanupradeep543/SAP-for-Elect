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

            if "Notif.date" not in df.columns:
                st.error(f"'Notif.date' column not found in {file.name}")
                continue

            floc=df["Functional Loc."].fillna("").astype("string").str.upper()
            df["System"]="Others"
            df.loc[floc.str.contains("CWS",na=False),"System"]="CW System"
            df.loc[floc.str.contains("CLT",na=False),"System"]="CT System"

            df["Notif.date"]=pd.to_datetime(df["Notif.date"],errors="coerce")
            df["Year"]=df["Notif.date"].dt.year
            df["Plant"]=plant

            plant_data[plant]=df

    if plant_data:

        data=pd.concat(plant_data.values(),ignore_index=True)

        # Plant-wise system summary
        summary=data.groupby(["Plant","System"]).size().unstack(fill_value=0).reset_index()

        for col in ["CW System","CT System","Others"]:
            if col not in summary.columns:
                summary[col]=0

        summary=summary[["Plant","CW System","CT System","Others"]]
        summary.insert(0,"S.No",range(1,len(summary)+1))

        st.subheader("Plant-wise System Notification Summary")
        st.dataframe(summary,use_container_width=True,hide_index=True)

        # Plant selection
        st.subheader("Detailed Plant Analysis")

        selected_plant=st.selectbox("Select Plant for Year-wise Trend",summary["Plant"].tolist())

        if selected_plant:

            plant_df=data[data["Plant"]==selected_plant].copy()

            trend=plant_df.groupby(["Year","System"]).size().unstack(fill_value=0).reset_index()

            for col in ["CW System","CT System","Others"]:
                if col not in trend.columns:
                    trend[col]=0

            trend=trend[["Year","CW System","CT System","Others"]]
            trend=trend.dropna(subset=["Year"])
            trend["Year"]=trend["Year"].astype(int)

            st.subheader(f"{selected_plant} - Year-wise System Trend")

            st.dataframe(trend,use_container_width=True,hide_index=True)

            trend_chart=trend.melt(
                id_vars="Year",
                value_vars=["CW System","CT System","Others"],
                var_name="System",
                value_name="Notifications"
            )

            fig=px.line(
                trend_chart,
                x="Year",
                y="Notifications",
                color="System",
                markers=True,
                text="Notifications"
            )

            fig.update_traces(textposition="top center")
            fig.update_layout(
                xaxis_title="Year",
                yaxis_title="Number of Notifications",
                legend_title="System",
                xaxis=dict(dtick=1)
            )

            st.plotly_chart(fig,use_container_width=True)
