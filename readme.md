# GPX Cycle Times

## Instructions

To use the `GPX Cycle Times.py` script, follow the steps below:

1. Ensure you have Python and the required dependencies installed. You can install the dependencies using:
    ```sh
    pip install -r requirements.txt
    ```

2. Run the script with the required arguments:
    ```sh
    python "GPX Cycle Times.py" <gpx_file> [--output_prefix <prefix>]
    ```

### Command-Line Arguments

- `<gpx_file>`: Path to the GPX file (required).
- `--output_prefix`: Prefix for output files (optional, default is 'output').

### Example Usage

1. Basic usage with a GPX file:
    ```sh
    python "GPX Cycle Times.py" example_route.gpx
    ```

2. Usage with a specified output prefix:
    ```sh
    python "GPX Cycle Times.py" example_route.gpx --output_prefix my_output
    ```

This will generate the following output files:
- `my_output_cycle_summary.csv`: Summary of detected cycles.
- `my_output_points_with_cycles.csv`: Detailed points with cycle IDs.
- `my_output_gantt_cycles.png`: Gantt chart of haul cycles.
- `my_output_speed_time.png`: Speed vs. time chart.
- `my_output_map_cycles.png`: Map view of haul cycles.

// ...existing code...
