# California county boundaries

`ca_counties.geojson` contains the 58 California county polygons used by the
dashboard choropleth. The source is the California Department of Technology's
public [California County Boundaries and Identifiers dataset](https://publish.data.ca.gov/dataset/california-county-boundaries-and-identifiers).

The GeoJSON was queried from the dataset's ArcGIS feature service with only
county features (`CENSUS_PLACE_TYPE = County`), the county name and Census
GEOID attributes, WGS84 coordinates, and generalized geometry. Keeping this
small asset in the repository lets the deployed app render without fetching
boundary data at runtime.
