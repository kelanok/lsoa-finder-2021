from pathlib import Path
import tempfile

import geopandas as gpd
import streamlit as st
from shapely.geometry import Point

APP_DIR = Path(__file__).resolve().parent
DEFAULT_FILE_PATH = APP_DIR / "data.gpkg"
WGS84_CRS = "EPSG:4326"
BNG_CRS = "EPSG:27700"
REQUIRED_COLUMN = "LSOA21CD"


st.set_page_config(page_title="LSOA Finder", layout="wide")
st.title("LSOA Finder")
st.write(
    "Find LSOAs whose population-weighted centroids fall within a chosen radius "
    "of a target latitude and longitude."
)


@st.cache_data(show_spinner="Loading LSOA data...")
def load_data(source_key: str, uploaded_bytes: bytes | None = None) -> gpd.GeoDataFrame:
    if uploaded_bytes is None:
        data = gpd.read_file(source_key)
    else:
        suffix = Path(source_key).suffix or ".gpkg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(uploaded_bytes)
            temp_path = temp_file.name
        data = gpd.read_file(temp_path)

    if data.crs is None:
        raise ValueError("The uploaded file has no coordinate reference system.")

    if data.crs != BNG_CRS:
        data = data.to_crs(BNG_CRS)

    if REQUIRED_COLUMN not in data.columns:
        raise ValueError(f"Required column '{REQUIRED_COLUMN}' was not found.")

    return data[[REQUIRED_COLUMN, "geometry"]].copy()


def find_lsoas(lat: float, lon: float, radius_m: float, lsoa_data_gdf: gpd.GeoDataFrame) -> list[str]:
    site_point = gpd.GeoDataFrame(
        [{"geometry": Point(lon, lat)}],
        crs=WGS84_CRS,
    ).to_crs(BNG_CRS).geometry.iloc[0]

    distances = lsoa_data_gdf.geometry.distance(site_point)
    matches = lsoa_data_gdf.loc[distances <= radius_m, REQUIRED_COLUMN]
    return sorted(matches.unique().tolist())


st.sidebar.header("Inputs")
uploaded_file = st.sidebar.file_uploader(
    "Upload centroid data (optional)",
    type=["gpkg", "geojson"],
    help=(
        "If nothing is uploaded, the app uses the bundled data.gpkg file. "
        "GeoPackage and GeoJSON are supported for Streamlit deployment."
    ),
)
lat_text = st.sidebar.text_input("Target latitude", "52.5844")
lon_text = st.sidebar.text_input("Target longitude", "-2.1320")
radius_m = st.sidebar.number_input("Radius (metres)", min_value=1, value=1500, step=100)

file_label: str | None = None
source_key: str | None = None
uploaded_bytes: bytes | None = None

if uploaded_file is not None:
    source_key = uploaded_file.name
    uploaded_bytes = uploaded_file.getvalue()
    file_label = f"Using uploaded file: `{uploaded_file.name}`"
elif DEFAULT_FILE_PATH.exists():
    source_key = str(DEFAULT_FILE_PATH)
    file_label = f"Using bundled file: `{DEFAULT_FILE_PATH.name}`"
else:
    st.error(
        "No input data is available. Upload a GeoPackage or GeoJSON file, "
        "or add `data.gpkg` to the app root."
    )

if file_label:
    st.sidebar.success(file_label)

if source_key:
    try:
        lsoa_gdf = load_data(source_key, uploaded_bytes)
    except Exception as exc:
        st.error(f"Unable to load the LSOA data: {exc}")
        st.stop()

    if st.sidebar.button("Find LSOAs", type="primary"):
        try:
            lat = float(lat_text)
            lon = float(lon_text)
        except ValueError:
            st.error("Latitude and longitude must both be valid numbers.")
            st.stop()

        with st.spinner("Calculating LSOAs..."):
            lsoa_list = find_lsoas(lat, lon, float(radius_m), lsoa_gdf)

        st.header("Results")
        st.success(f"Found {len(lsoa_list)} matching LSOAs.")

        if lsoa_list:
            results_text = "\n".join(lsoa_list)
            st.text_area("LSOA codes", results_text, height=320)
            st.download_button(
                "Download results",
                data=results_text,
                file_name="lsoa_results.txt",
                mime="text/plain",
            )
        else:
            st.info("No LSOAs were found within the selected radius.")
