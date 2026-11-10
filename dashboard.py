
import streamlit as st
import pandas as pd
import requests

API_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Reusable Asset Management",
    page_icon="📦",
    layout="wide"
)


def api_get(endpoint, params=None):
    try:
        response = requests.get(
            f"{API_URL}{endpoint}",
            params=params,
            timeout=10
        )
        response.raise_for_status()
        return response.json()

    except requests.RequestException as error:
        st.error(f"API connection error: {error}")
        return None


# MAIN HEADER

st.title("📦 Reusable Asset Lifecycle Management")

st.caption(
    "Asset tracking | Reverse logistics | "
    "Custody management | Exception monitoring"
)

st.sidebar.title("Navigation")

page = st.sidebar.radio(
    "Choose a module",
    [
        "Dashboard",
        "Asset Search",
        "Custody History",
        "Exception Monitoring",
        "Analytics"
    ]
)


# DASHBOARD

if page == "Dashboard":

    st.header("Operations Overview")

    data = api_get("/analytics")

    if data:

        col1, col2, col3 = st.columns(3)

        col1.metric("Total Assets", data["total_assets"])
        col2.metric("Total Shipments", data["total_shipments"])
        col3.metric(
            "Custody Events",
            data["total_custody_events"]
        )

        st.subheader("Asset Status")

        status_data = pd.DataFrame(
            data["asset_status_breakdown"]
        )

        if not status_data.empty:
            st.bar_chart(
                status_data.set_index("current_status")["total"]
            )

        st.subheader("Inspection Results")

        inspection_data = pd.DataFrame(
            data["inspection_result_breakdown"]
        )

        if not inspection_data.empty:
            st.bar_chart(
                inspection_data.set_index("result")["total"]
            )


# ASSET SEARCH

elif page == "Asset Search":

    st.header("🔎 Search an Asset")

    asset_id = st.text_input(
        "Enter Asset ID",
        placeholder="ASSET-0000001"
    )

    if st.button("Search Asset"):

        if asset_id.strip():

            asset = api_get(
                f"/assets/{asset_id.strip()}"
            )

            if asset:
                st.success("Asset found!")
                st.json(asset)

        else:
            st.warning("Please enter an Asset ID.")


# CUSTODY HISTORY

elif page == "Custody History":

    st.header("📍 Asset Custody History")

    asset_id = st.text_input(
        "Enter Asset ID",
        placeholder="ASSET-0000001"
    )

    if st.button("View History"):

        if asset_id.strip():

            history = api_get(
                f"/assets/{asset_id.strip()}/history"
            )

            if history:

                st.metric(
                    "Total Events",
                    history["event_count"]
                )

                events = pd.DataFrame(history["history"])

                if not events.empty:

                    st.dataframe(
                        events,
                        use_container_width=True
                    )

                else:
                    st.info("No custody history found.")

        else:
            st.warning("Please enter an Asset ID.")


# EXCEPTION MONITORING

elif page == "Exception Monitoring":

    st.header("🚨 Logistics Exception Monitoring")

    if st.button("🔄 Refresh Exceptions"):
        st.rerun()

    data = api_get("/exceptions")

    if data:

        exceptions = data.get("exceptions", [])

        st.subheader("Exception Summary")

        col1, col2 = st.columns(2)

        col1.metric(
            "Total Exceptions",
            data.get("total_exceptions", 0)
        )

        col2.metric(
            "Affected Assets",
            len(set(
                item["asset_id"] for item in exceptions
            ))
        )

        if exceptions:

            st.divider()

            exception_types = sorted({
                item["type"] for item in exceptions
            })

            selected_type = st.selectbox(
                "Filter by Exception Type",
                ["All"] + exception_types
            )

            if selected_type == "All":
                filtered = exceptions
            else:
                filtered = [
                    item for item in exceptions
                    if item["type"] == selected_type
                ]

            st.subheader(
                f"Detected Exceptions ({len(filtered)})"
            )

            for index, item in enumerate(filtered, start=1):

                with st.container(border=True):

                    st.markdown(
                        f"### {index}. {item['type'].replace('_', ' ')}"
                    )

                    st.write(
                        f"**Asset ID:** {item['asset_id']}"
                    )

                    st.write(
                        f"**Record ID:** {item['record_id']}"
                    )

                    st.warning(
                        f"Recommended Decision: {item['decision']}"
                    )

                    with st.expander("View Investigation Details"):

                        details = item.get("details", {})

                        st.json(details)

            st.divider()

            st.subheader("Exception Records Table")

            summary_rows = []

            for item in filtered:

                summary_rows.append({
                    "Exception Type": item["type"],
                    "Record ID": item["record_id"],
                    "Asset ID": item["asset_id"],
                    "Recommended Decision": item["decision"]
                })

            st.dataframe(
                pd.DataFrame(summary_rows),
                use_container_width=True,
                hide_index=True
            )

            csv_data = pd.DataFrame(summary_rows).to_csv(
                index=False
            ).encode("utf-8")

            st.download_button(
                "📥 Download Exception Report",
                data=csv_data,
                file_name="exception_report.csv",
                mime="text/csv"
            )

        else:
            st.success("No exceptions detected.")


# ANALYTICS

elif page == "Analytics":

    st.header("📊 Logistics Analytics")

    data = api_get("/analytics")

    if data:

        st.subheader("Asset Status Breakdown")

        st.dataframe(
            pd.DataFrame(data["asset_status_breakdown"]),
            use_container_width=True
        )

        st.subheader("Inspection Result Breakdown")

        st.dataframe(
            pd.DataFrame(data["inspection_result_breakdown"]),
            use_container_width=True
        )

        st.info(
            "These metrics are calculated from the SQLite database."
        )


# SIDEBAR FOOTER

st.sidebar.divider()

st.sidebar.caption("Reusable Asset Lifecycle System")
st.sidebar.caption("Powered by Python + FastAPI + SQLite")
