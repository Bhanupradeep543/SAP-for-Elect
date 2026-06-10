import pandas as pd
import pickle
from sklearn import preprocessing
from scipy import stats
import numpy as np
import pandas as pd
import seaborn as sb
import matplotlib.pyplot as plt
import streamlit as st
import io
from datetime import datetime
import random 
import base64
import re
st.title("NTPC SAP Notifications Analysis")
uploaded_file = st.file_uploader("Upload your defect data (Excel/CSV)",type=["xlsx", "xls", "csv"])
data = pd.read_excel(uploaded_file)
st.success("File loaded successfully")
data['Basic start date'] = pd.to_datetime(data['Basic start date'], format='%Y%m%d')
st.subheader('Total SAP notifications considered for analysis')
st.subheader(data.shape[0])
st.subheader('Top 20 Repeated equipment notifications')
data=data[data['equipment']!='KORBA STATION COMMON']
repeat_defects = (data.groupby(['equipment']).size().reset_index(name='Count'))
repeated = repeat_defects[repeat_defects['Count'] > 50]
repeated = repeated.sort_values(by=['Count', 'equipment'], ascending=[False, True]).head(20)
st.write(repeated)
COL = "Functional Location"
EQUIP = "equipment"
def is_valid_parent(s):
    hyphens = s.count("-")
    if hyphens < 2 or hyphens > 3:
        return False
    parts = s.split("-")
    third_part = parts[2] if len(parts) >= 3 else ""
    if re.search(r"\d", third_part):
        return False
    return True
def extract_parent(s):
    parts = s.split("-")
    return "-".join(parts[:3]) if len(parts) >= 3 else s
# Extract parent
data["parent"] = data[COL].astype(str).apply(extract_parent)
# Keep only valid parents
df_valid = data[data["parent"].apply(is_valid_parent)]
# Get unique rows for parent → equipment mapping
df_unique = df_valid.drop_duplicates(subset=["parent"])[["parent", EQUIP]]
# Count appearances in the full master dataset
appearance = data.groupby("parent").size().reset_index(name="Total Count")
# Merge with unique mapping
df_final = df_unique.merge(appearance, on="parent", how="left")
# Filter: appearances > 40
df_final = df_final[df_final["Total Count"] > 40]
# Sort descending by appearances
df_final = df_final.sort_values(by="Total Count", ascending=False).reset_index(drop=True)
# Add % column
total_appearances = df_final["Total Count"].sum()
df_final["%"] = (df_final["Total Count"] / total_appearances * 100).round().astype(int)
# Rename column for display
df_final = df_final.rename(columns={"parent": COL})
st.subheader("system wise no.of defects in last 10 years")
st.dataframe(df_final)
# Stage keywords
keywords = {
    "Stage-1": "S1",
    "Stage-2": "S2",
    "Stage-3": "S3"
}
# Empty list to store results
stage_summary = []
# Loop through all stages automatically
for stage_name, keyword in keywords.items():
    # Filter stage-wise data
    data2 = data[data['Functional Location'].astype(str).str.contains(keyword, na=False)]
    # Total defects in that stage
    total_defects = data2.shape[0]
    # Append results
    stage_summary.append({
        "Stage": stage_name,
        "Total Defects": total_defects
    })
# Create dataframe
stage_df = pd.DataFrame(stage_summary)
# Calculate grand total
grand_total = stage_df["Total Defects"].sum()
# Percentage contribution
stage_df["% Contribution"] = (
    stage_df["Total Defects"] / grand_total * 100
).round(0)
# Display output
st.subheader("📊 All Stage-wise Defect Summary")
st.dataframe(stage_df)
fig, ax = plt.subplots(figsize=(7,7))
ax.pie(
    stage_df["Total Defects"],
    labels=stage_df["Stage"],
    autopct='%1.1f%%',
    startangle=90
)
ax.set_title("Stage-wise Defect Distribution")
# Equal aspect ratio
ax.axis('equal')
# Display in Streamlit
st.pyplot(fig)
# Total defects in selected stage
total_stage_defects = data.shape[0]

# Defect category patterns
defect_patterns = {
    "Gland Leak Related": r"gland|GLAND|Gland|galand|GLD|gld",
    "Vibrational Related": r"Vibration|vibration|VIBRATION|vib|VIB",
    "Bearing/Coupling Abnormalities": r"sound|SOUND|Sound|bearing|BRG|BEARING|Bearing|brng|BRNG|thrust|THRUST|Thrust",
    "NRV Passing": r"nrv|NRV|Nrv",
    "NTS/ module related": r"nts|NTS|Nts|MODULE|module|Module|brkr|BREAKER|Breaker|bkr|FUSES|fuses|Fuses",
    "Valve Issues": r"valve|VALVE|vlv|VLV|Valve|v/v|BFV|bfv",
    "Oil Leakage": r"oil|OIL|Oil",
    "Reverse Rotation/Decoupled": r"reverse|REVERSE|Reverse|Decouple|decouple|DECOUPLE",
    "Pipe Leakages": r"pipe|PIPE|LINE|Line|line|Pipe|hdr|HDR|header|HEADER",
    "Overloading/Tripping": r"overload|OVERLOAD|overload|TRIP|trip|Trip|OL|Overload|O/L|o/l|current|CURRENT|Current|curren",
    "Pressure Related Issues": r"pr low|PR LOW|DEVELOP|develop|Develop|pressure|PRESSURE|devlp",
    "Choking Issues": r"CHOKE|choke|Choke",
    "Jamming Issues": r"JAM|jam"
}
# Summary table
summary = []
for defect_name, pattern in defect_patterns.items():
    defect_data = data[
        data['Description']
        .astype(str)
        .str.contains(pattern, na=False)
    ]
    defect_count = defect_data.shape[0]
    defect_percent = round(
        (defect_count / total_stage_defects) * 100,2)
    summary.append({
        "Defect Category": defect_name,
        "Count": defect_count,
        "% of Total Stage Defects": defect_percent
    })
# Convert to dataframe
summary_df = pd.DataFrame(summary)
# Sort descending
summary_df = summary_df.sort_values(
    by="Count",
    ascending=False
).reset_index(drop=True)
# Display
st.subheader("📊 Defect Summary")

st.dataframe(summary_df)
keywords = {"Stage-1": "S1COM","Stage-2": "S2COM","Stage-3": "S3COM" }
st.subheader("Select the stage for detailed Analysis:")
selected = st.multiselect("select:",list(keywords.keys()))
if selected:
 selected_keywords = [keywords[s] for s in selected]
 for k in selected_keywords:
  data2=data[data['Functional Loc.'].str.contains(k)]
  st.subheader("Total defects in the selected stage")
  st.write(data2.shape[0])
  repeat_defects = (data2.groupby(['equipment']).size().reset_index(name='Count'))     
  repeated = repeat_defects[repeat_defects['Count'] > 10]
  repeated = repeated.sort_values(by=['Count', 'equipment'], ascending=[False, True]).head(10)
  st.subheader("TOP 10 repeated defects in the selected stage")
  df = pd.DataFrame(repeated)
  multiplier = 520
  df['each notification interval in terms of weeks'] = ((multiplier)/df['Count']).round().astype(int)
  st.write(df)
   
  data3=data2[data2['Description'].str.contains('nts|NTS|Nts|MODULE|module|Module|brkr|BREAKER|Breaker|bkr|FUSES|fuses|Fuses')]
  data3["Year"] = data3['Notif.date'].dt.year
  st.write("no.of NTS/module related in the selected stage",data3.shape[0])
  yearly_count = data3.groupby("Year")['Notif.date'].count().reset_index()
  yearly_count.rename(columns={'Notif.date': "NTS/ module related"}, inplace=True)
  st.subheader("📅 Year-wise NTS/ module related")
  st.bar_chart(data=yearly_count, x="Year", y="NTS/ module related")      
     
  data4=data2[data2['Description'].str.contains('Vibration|vibration|VIBRATION|vib|VIB')]
  data4["Year"] = data4['Notif.date'].dt.year
  st.write("no.of vibrational issues in the selected stage",data4.shape[0])
  yearly_count = data4.groupby("Year")['Notif.date'].count().reset_index()
  yearly_count.rename(columns={'Notif.date': "vibrational issues"}, inplace=True)
  st.subheader("📅 Year-wise vibrational issues")
  st.bar_chart(data=yearly_count, x="Year", y="vibrational issues")    
   
  data5=data2[data2['Description'].str.contains('sound|SOUND|Sound|bearing|BEARING|Bearing|brng|BRNG|thrust|THRUST|Thrust')]
  data5["Year"] = data5['Notif.date'].dt.year
  st.write("no.of bearing/coupling issues in the selected stage",data5.shape[0])
  yearly_count = data5.groupby("Year")['Notif.date'].count().reset_index()
  yearly_count.rename(columns={'Notif.date': "bearing/coupling issues"}, inplace=True)
  st.subheader("📅 Year-wise bearing/coupling issues")
  st.bar_chart(data=yearly_count, x="Year", y="bearing/coupling issues") 
     
  data6=data2[data2['Description'].str.contains('nrv|NRV|Nrv')]
  data6["Year"] = data6['Notif.date'].dt.year
  st.write("no.of NRV passing issues in the selected stage",data6.shape[0])
  yearly_count = data6.groupby("Year")['Notif.date'].count().reset_index()
  yearly_count.rename(columns={'Notif.date': "NRV passing"}, inplace=True)
  st.subheader("📅 Year-wise NRV passings")
  st.bar_chart(data=yearly_count, x="Year", y="NRV passing")
 
  data7=data2[data2['Description'].str.contains('valve|VALVE|vlv|VLV|Valve|v/v|BFV|bfv')]
  data7["Year"] = data7['Notif.date'].dt.year
  st.write("no.of valve issues in the selected stage",data7.shape[0])
  yearly_count = data7.groupby("Year")['Notif.date'].count().reset_index()
  yearly_count.rename(columns={'Notif.date': "Valve issues"}, inplace=True)
  st.subheader("📅 Year-wise Valve issues")
  st.bar_chart(data=yearly_count, x="Year", y="Valve issues")

  data8=data2[data2['Description'].str.contains('oil|OIL|Oil')]
  data8["Year"] = data8['Notif.date'].dt.year
  st.write("no.of oil leak/ oil top up issues in the selected stage",data8.shape[0])
  yearly_count = data8.groupby("Year")['Notif.date'].count().reset_index()
  yearly_count.rename(columns={'Notif.date': "Oil leaks/ oil top up issues"}, inplace=True)
  st.subheader("📅 Year-wise Oil leaks/ oil top up issues")
  st.bar_chart(data=yearly_count, x="Year", y="Oil leaks/ oil top up issues")

  data9=data2[data2['Description'].str.contains('reverse|REVERSE|Reverse|Decouple|decouple|DECOUPLE')]
  data9["Year"] = data9['Notif.date'].dt.year
  st.write("no.of pump/Fan shaft Decoupled/reverse rotational issues in the selected stage",data9.shape[0])
  yearly_count = data9.groupby("Year")['Notif.date'].count().reset_index()
  yearly_count.rename(columns={'Notif.date': "pump/Fan shaft jam/reverse rotational issues"}, inplace=True)
  st.subheader("📅 Year-wise pump/Fan shaft Decoupled/reverse rotational issues")
  st.bar_chart(data=yearly_count, x="Year", y="pump/Fan shaft jam/reverse rotational issues")
     
  data10=data2[data2['Description'].str.contains('pipe|PIPE|LINE|Line|line|Pipe|hdr|HDR|header|HEADER')]
  data10["Year"] = data10['Notif.date'].dt.year
  st.write("no.of Pipe leakage issues in the selected stage",data10.shape[0])
  yearly_count = data9.groupby("Year")['Notif.date'].count().reset_index()
  yearly_count.rename(columns={'Notif.date': "Pipe leakage issues"}, inplace=True)
  st.subheader("📅 Year-wise Pipe leakage issues")
  st.bar_chart(data=yearly_count, x="Year", y="Pipe leakage issues")
  
  data11=data2[data2['Description'].str.contains('overload|OVERLOAD|OL|Overload|O/L|o/l|current|CURRENT|Current|curren')]
  data11["Year"] = data11['Notif.date'].dt.year
  st.write("no.of Over loading/ tripping issues in the selected stage",data11.shape[0])
  yearly_count = data11.groupby("Year")['Notif.date'].count().reset_index()
  yearly_count.rename(columns={'Notif.date': "Over loading/ tripping issues"}, inplace=True)
  st.subheader("📅 Year-wise Over loading/ tripping issues")
  st.bar_chart(data=yearly_count, x="Year", y="Over loading/ tripping issues")

  data12=data2[data2['Description'].str.contains('pr low|PR LOW|DEVELOP|develop|Develop|pressure|PRESSURE|devlp')]
  data12["Year"] = data12['Notif.date'].dt.year
  st.write("no.of Pressure Related Issues in the selected stage",data12.shape[0])
  yearly_count = data12.groupby("Year")['Notif.date'].count().reset_index()
  yearly_count.rename(columns={'Notif.date': "Pressure Related Issues"}, inplace=True)
  st.subheader("📅 Year-wise Pressure Related Issues")
  st.bar_chart(data=yearly_count, x="Year", y="Pressure Related Issues")

  data13=data2[data2['Description'].str.contains('CHOKE|choke|Choke')]
  data13["Year"] = data13['Notif.date'].dt.year
  st.write("no.of Line/ CT Nozzles chokage issues in the selected stage",data13.shape[0])
  yearly_count = data13.groupby("Year")['Notif.date'].count().reset_index()
  yearly_count.rename(columns={'Notif.date': "Line/ CT Nozzles chokage issues"}, inplace=True)
  st.subheader("📅 Year-wise Line/ CT Nozzles chokage issues")
  st.bar_chart(data=yearly_count, x="Year", y="Line/ CT Nozzles chokage issues")

  data14=data2[data2['Description'].str.contains('JAM|jam')]
  data14["Year"] = data14['Notif.date'].dt.year
  st.write("no.of valve/pump/gearbox jamming issues in the selected stage",data14.shape[0])
  yearly_count = data13.groupby("Year")['Notif.date'].count().reset_index()
  yearly_count.rename(columns={'Notif.date': "valve/pump/gearbox jamming issues"}, inplace=True)
  st.subheader("📅 Year-wise valve/pump/gearbox jamming issues")
  st.bar_chart(data=yearly_count, x="Year", y="valve/pump/gearbox jamming issues")
  

  tc=data3.shape[0]+data4.shape[0]+data5.shape[0]+data6.shape[0]+data7.shape[0]+data8.shape[0]+data9.shape[0]+data10.shape[0]+data11.shape[0]+data12.shape[0]+data13.shape[0]+data14.shape[0]
  per=(tc/data2.shape[0])*100
  per=int(per)
  st.write("% of notifications divided into various categories",per)
     
  date_col = "Notif.date"
  equip_col = "equipment"
  # Convert to datetime
  data2[date_col] = pd.to_datetime(data2[date_col], errors='coerce')
  data2 = data2.dropna(subset=[date_col, equip_col])
  # Convert equipment name to string to avoid dtype mismatch
  data2[equip_col] = data2[equip_col].astype(str)
  # Equipment frequency table
  equip_count = data2[equip_col].value_counts().reset_index()
  equip_count.columns = [equip_col, 'Defect_Count']
  # Show equipment list with counts
  st.subheader("⚙️ Equipment-wise defect count in selected stage")
  st.dataframe(equip_count)
  
selected_equips = st.multiselect("Select equipment(s) to forecast:",options=equip_count[equip_count['Defect_Count'] > 0][equip_col].tolist(),
help="You can select multiple equipments for prediction.")
forecast_results = []
if selected_equips:
 for eq in selected_equips:
  eq_data = data2[data2[equip_col] == eq].sort_values(by=date_col)
  eq_dates = eq_data[date_col].dropna().sort_values()
  if len(eq_dates) > 1:
  # Calculate gaps between defects
   gaps = eq_dates.diff().dt.days.dropna()
   avg_gap = gaps.mean()
   last_date = eq_dates.max()
   next_pred_date = last_date + pd.Timedelta(days=avg_gap)
   forecast_results.append({"Equipment": eq,"Total_Defects": len(eq_dates),"Average_Gap_(days)": round(avg_gap, 1),
   "Last_Defect_Date": last_date.date(),"Predicted_Next_Defect": next_pred_date.date()})
   if forecast_results:
    result = pd.DataFrame(forecast_results)
st.subheader("📅 Forecasted Next Defect Dates")
st.dataframe(result) 


