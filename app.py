import streamlit as st
import geopandas as gpd
from shapely.geometry import Point
import os # Import the os module to check for files

# --- Page Setup ---
st.set_page_config(page_title="LSOA Finder", layout="wide")
st.title("LSOA Finder 🗺️")
st.write("Find LSOAs where the population-weighted centroid falls within a given radius.")

# --- File Configuration ---
# The default local file to look for
DEFAULT_FILE_NAME = "data.gpkg"

# --- Caching the Data Loader ---
@st.cache_data
def load_data(file_path_or_buffer):
    """
    Loads and pre-processes the GeoPackage file.
    The input can be a file path (str) or an uploaded file buffer.
    """
    st.write("Cache miss: Loading and processing LSOA data... (this runs once)")
    
    BNG_CRS = "EPSG:27700"
    
    try:
        # gpd.read_file() can handle both file paths and uploaded file objects
        gpd_df = gpd.read_file(file_path_or_buffer)
        
        # Ensure data is in the correct CRS
        if gpd_df.crs != BNG_CRS:
            gpd_df = gpd_df.to_crs(BNG_CRS)
            
        # Check for required column
        if 'LSOA21CD' not in gpd_df.columns:
            st.error("Error: 'LSOA21CD' column not found in the file.")
            return None
            
        return gpd_df
        
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return None

# --- Core Logic Function ---
def find_lsoas(lat, lon, radius_km, lsoa_data_gdf):
    """Finds LSOAs using the pre-loaded GeoDataFrame."""
    
    WGS_CRS = "EPSG:4326"
    BNG_CRS = "EPSG:27700"
    
    lsoa_centroids_gdf = lsoa_data_gdf.copy()

    # Create and transform the target point
    site_point_geom = Point(lon, lat)
    site_point_gdf = gpd.GeoDataFrame([{'geometry': site_point_geom}], crs=WGS_CRS)
    site_point_in_bng = site_point_gdf.to_crs(BNG_CRS)
    site_point = site_point_in_bng.geometry.iloc[0]

    # Calculate distances
    radius_meters = radius_km * 1000.0
    lsoa_centroids_gdf['distance'] = lsoa_centroids_gdf.geometry.distance(site_point)

    # Filter
    matching_lsoas = lsoa_centroids_gdf[
        lsoa_centroids_gdf['distance'] <= radius_meters
    ]

    return sorted(list(matching_lsoas['LSOA21CD'].unique()))

# --- Sidebar Inputs ---
st.sidebar.header("Inputs")

# 1. File Uploader (now optional)
uploaded_file = st.sidebar.file_uploader(
    "Upload File (Optional)", 
    type=["gpkg", "shp", "geojson"],
    help=f"If no file is uploaded, the app will automatically use '{DEFAULT_FILE_NAME}' if it's in the same directory."
)

# 2. Coordinates and Radius
lat = st.sidebar.text_input("Target Latitude", "52.5844")
lon = st.sidebar.text_input("Target Longitude", "-2.1320")
radius_m = st.sidebar.number_input("Radius (in metres)", min_value=1, value=1500, step=100)

# --- Main App Logic: Determine which file to load ---

file_to_load = None
data_source_message = ""

if uploaded_file is not None:
    # Priority 1: User uploaded a file
    file_to_load = uploaded_file
    data_source_message = f"Using uploaded file: `{uploaded_file.name}`"
elif os.path.exists(DEFAULT_FILE_NAME):
    # Priority 2: Default file exists
    file_to_load = DEFAULT_FILE_NAME
    data_source_message = f"Using default file: `{DEFAULT_FILE_NAME}`"
else:
    # State 3: No data
    st.info(f"Please upload your LSOA Centroids file, or place `{DEFAULT_FILE_NAME}` in the app's directory to begin.")


# --- Run the App if we have data ---
if file_to_load is not None:
    st.sidebar.success(data_source_message)
    
    # Load data (will be cached based on the file source)
    lsoa_gdf = load_data(file_to_load)
    
    if lsoa_gdf is not None:
        
        # 3. Run Button
        if st.sidebar.button("Find LSOAs"):
            try:
                # Validate inputs
                lat_f = float(lat)
                lon_f = float(lon)
                radius_km_f = float(radius_m) / 1000.0

                # Run calculation
                with st.spinner("Calculating..."):
                    lsoa_list = find_lsoas(lat_f, lon_f, radius_km_f, lsoa_gdf)

                # Display Results
                st.header("Results")
                st.success(f"Found {len(lsoa_list)} LSOAs with centroids in the radius.")
                
                # Put results in a neat text area
                results_text = "\n".join(lsoa_list)
                st.text_area("LSOA Codes", results_text, height=300)

            except ValueError:
                st.error("Invalid Input: Latitude and Longitude must be valid numbers.")
            except Exception as e:
                st.error(f"An error occurred: {e}")