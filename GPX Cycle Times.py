import gpxpy
import gpxpy.gpx
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from geopy.distance import geodesic
import datetime

# --------------------------------------------------
# USER CONFIGURATION
# --------------------------------------------------

GPX_FILE = 'example_route.gpx'  # Path to your GPX file

# Define approximate centers and radii for start/end zones (in meters)
# (Change these to match your real loading and dumping points)
START_ZONE_CENTER = (40.0000, -105.0000)  # (lat, lon)
START_ZONE_RADIUS = 100  # meters

END_ZONE_CENTER = (40.0010, -105.0020)  # (lat, lon)
END_ZONE_RADIUS = 100  # meters

# Whether to display plots interactively
SHOW_PLOTS = True

# --------------------------------------------------
# 1. Parse GPX into DataFrame
# --------------------------------------------------

def parse_gpx_to_df(gpx_file):
    """
    Parse a GPX file and return a Pandas DataFrame
    with columns: time, lat, lon, distance_from_prev, cumulative_distance
    """
    with open(gpx_file, 'r') as f:
        gpx = gpxpy.parse(f)
    
    data = []
    prev_point = None
    cumulative_distance = 0.0
    
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                # Extract fields
                time = point.time  # datetime object
                lat = point.latitude
                lon = point.longitude
                
                # Distance from previous point
                if prev_point is not None:
                    dist = geodesic((prev_point.latitude, prev_point.longitude), (lat, lon)).meters
                else:
                    dist = 0.0
                
                cumulative_distance += dist
                
                data.append({
                    'time': time,
                    'lat': lat,
                    'lon': lon,
                    'distance_from_prev_m': dist,
                    'cumulative_distance_m': cumulative_distance
                })
                prev_point = point
    
    df = pd.DataFrame(data)
    # Ensure chronological order
    df.sort_values(by='time', inplace=True)
    df.reset_index(drop=True, inplace=True)
    
    # Calculate time deltas and speed if desired
    df['time_delta_s'] = df['time'].diff().dt.total_seconds().fillna(0)
    df['speed_m_s'] = df['distance_from_prev_m'] / df['time_delta_s'].replace(0, np.nan)
    df['speed_m_s'].fillna(0, inplace=True)
    df['speed_km_h'] = df['speed_m_s'] * 3.6
    
    return df

# --------------------------------------------------
# 2. Define helper functions for zone checks
# --------------------------------------------------

def is_in_zone(lat, lon, zone_center, radius_m):
    """
    Return True if (lat, lon) is within `radius_m` meters of zone_center.
    """
    point_dist = geodesic((lat, lon), zone_center).meters
    return point_dist <= radius_m

# --------------------------------------------------
# 3. Cycle Detection
# --------------------------------------------------

def detect_cycles(df, start_center, start_radius, end_center, end_radius):
    """
    Adds a 'cycle_id' column to df indicating which cycle each point belongs to.
    Logic: A cycle starts when the truck enters the start zone and ends when
    the truck next enters the end zone.
    
    If the truck repeatedly goes from start -> end -> start -> end, you'll get
    multiple cycles. If it doesn't follow that pattern, you might need a more
    sophisticated approach.
    """
    cycle_id = 0
    in_cycle = False
    current_cycle = np.nan
    
    cycle_ids = []
    
    for idx, row in df.iterrows():
        lat, lon = row['lat'], row['lon']
        
        if not in_cycle:
            # Check if we are in the start zone => cycle begins
            if is_in_zone(lat, lon, start_center, start_radius):
                cycle_id += 1
                in_cycle = True
                current_cycle = cycle_id
        else:
            # We are in a cycle, check if we reached the end zone => cycle ends
            if is_in_zone(lat, lon, end_center, end_radius):
                in_cycle = False
                current_cycle = np.nan
        
        cycle_ids.append(current_cycle)
    
    df['cycle_id'] = cycle_ids
    return df

# --------------------------------------------------
# 4. Summarize cycles
# --------------------------------------------------

def summarize_cycles(df):
    """
    Create a summary DataFrame with one row per cycle:
    cycle_id, start_time, end_time, duration_min, distance_m
    """
    cycle_summaries = []
    for c_id in sorted(df['cycle_id'].dropna().unique()):
        cycle_points = df[df['cycle_id'] == c_id]
        if len(cycle_points) == 0:
            continue
        start_time = cycle_points['time'].iloc[0]
        end_time = cycle_points['time'].iloc[-1]
        duration = (end_time - start_time).total_seconds() / 60.0  # in minutes
        
        # Distance can be the difference between final and initial cumulative distance
        distance_m = (cycle_points['cumulative_distance_m'].iloc[-1] - 
                      cycle_points['cumulative_distance_m'].iloc[0])
        
        cycle_summaries.append({
            'cycle_id': c_id,
            'start_time': start_time,
            'end_time': end_time,
            'duration_min': duration,
            'distance_m': distance_m
        })
    
    summary_df = pd.DataFrame(cycle_summaries)
    return summary_df

# --------------------------------------------------
# 5. Plotting
# --------------------------------------------------

def plot_cycle_gantt(cycle_summary, filename='gantt_cycles.png'):
    """
    Plot a Gantt-style chart for the cycles with start and end times.
    """
    if cycle_summary.empty:
        print("No cycles found, skipping Gantt chart.")
        return
    
    # Sort cycles by start time
    cycle_summary.sort_values('start_time', inplace=True)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    y_positions = range(len(cycle_summary))  # one bar per cycle
    
    for y, (_, row) in zip(y_positions, cycle_summary.iterrows()):
        start = row['start_time']
        end = row['end_time']
        ax.barh(y, (end - start).total_seconds()/60, left=start, 
                height=0.4, align='center', color='skyblue', edgecolor='black')
        # Add label
        ax.text(end, y, f"Cycle {int(row['cycle_id'])}\n{row['duration_min']:.1f} min",
                va='center', ha='left', fontsize=8)
    
    ax.set_xlabel("Time")
    ax.set_ylabel("Cycle ID")
    ax.set_yticks(y_positions)
    ax.set_yticklabels([f"Cycle {int(cid)}" for cid in cycle_summary['cycle_id']])
    
    # Format x-axis as datetime
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    fig.autofmt_xdate()
    
    plt.title("Gantt Chart of Haul Cycles")
    plt.tight_layout()
    plt.savefig(filename, dpi=150)
    print(f"Gantt chart saved as {filename}")
    if SHOW_PLOTS:
        plt.show()
    else:
        plt.close()

def plot_speed_time(df, filename='speed_time.png'):
    """
    Plot speed over time, color-coded by cycle_id.
    """
    if 'cycle_id' not in df.columns or df['cycle_id'].dropna().empty:
        print("No valid cycle data for speed-time plot.")
        return
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # We'll create segments by cycle
    for c_id in sorted(df['cycle_id'].dropna().unique()):
        cycle_points = df[df['cycle_id'] == c_id]
        ax.plot(cycle_points['time'], cycle_points['speed_km_h'], label=f"Cycle {int(c_id)}")
    
    ax.set_xlabel("Time")
    ax.set_ylabel("Speed (km/h)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    fig.autofmt_xdate()
    plt.title("Speed vs. Time by Cycle")
    plt.legend()
    plt.tight_layout()
    plt.savefig(filename, dpi=150)
    print(f"Speed vs Time chart saved as {filename}")
    if SHOW_PLOTS:
        plt.show()
    else:
        plt.close()

def plot_map_view(df, filename='map_cycles.png'):
    """
    Very basic lat/lon scatter plot color-coded by cycle_id.
    This is not a true GIS map, but can give a quick sense of route.
    """
    if 'cycle_id' not in df.columns or df['cycle_id'].dropna().empty:
        print("No valid cycle data for map plot.")
        return
    
    fig, ax = plt.subplots(figsize=(8, 8))
    
    # We will scatter-plot each cycle with a different color
    for c_id in sorted(df['cycle_id'].dropna().unique()):
        cycle_points = df[df['cycle_id'] == c_id]
        ax.plot(cycle_points['lon'], cycle_points['lat'], marker='o', label=f"Cycle {int(c_id)}")
    
    # Mark the start/end zones
    ax.scatter(START_ZONE_CENTER[1], START_ZONE_CENTER[0],
               color='green', marker='*', s=200, label='Start Zone')
    ax.scatter(END_ZONE_CENTER[1], END_ZONE_CENTER[0],
               color='red', marker='*', s=200, label='End Zone')
    
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    plt.title("Map of Haul Cycles (Lat/Lon)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(filename, dpi=150)
    print(f"Map view saved as {filename}")
    if SHOW_PLOTS:
        plt.show()
    else:
        plt.close()

# --------------------------------------------------
# Main Execution
# --------------------------------------------------
def main():
    # 1. Parse GPX
    df = parse_gpx_to_df(GPX_FILE)
    print(f"Loaded {len(df)} points from {GPX_FILE}.")

    # 2. Detect cycles
    df = detect_cycles(df, START_ZONE_CENTER, START_ZONE_RADIUS,
                       END_ZONE_CENTER, END_ZONE_RADIUS)
    
    # 3. Summarize cycles
    cycle_summary = summarize_cycles(df)
    print("Cycle Summary:")
    print(cycle_summary)
    
    # 4. (Optional) Save summary to CSV or Excel
    cycle_summary.to_csv('cycle_summary.csv', index=False)
    df.to_csv('points_with_cycles.csv', index=False)
    
    # 5. Plot outputs
    plot_cycle_gantt(cycle_summary, filename='gantt_cycles.png')
    plot_speed_time(df, filename='speed_time.png')
    plot_map_view(df, filename='map_cycles.png')

if __name__ == '__main__':
    main()
