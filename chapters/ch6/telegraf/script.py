def parse_line(line: str) -> dict:
    """
    Parse a line of InfluxDB Line Protocol and return a dictionary with the
    measurement, tags, fields, and optional timestamp.

    Args:
        line (str): Line of InfluxDB Line Protocol to parse

    Returns:
        dict: Dictionary with measurement, tags, fields, and optional time
    """
    # Split the line into main components: measurement+tags, fields, and optional time
    parts = line.split(" ")

    # Extract measurement and tags
    measurement_and_tags = parts[0]
    if "," in measurement_and_tags:
        measurement, tags_str = measurement_and_tags.split(",", 1)
    else:
        measurement = measurement_and_tags
        tags_str = ""

    # Parse tags
    tags = {}
    if tags_str:
        for tag in tags_str.split(","):
            key, value = tag.split("=")
            tags[key] = value

    # Extract and parse fields
    fields_str = parts[1]
    fields = {}
    for field in fields_str.split(","):
        key, value = field.split("=")
        # Determine field type
        if value.startswith('"') and value.endswith('"'):
            fields[key] = value[1:-1]  # String field
        elif "." in value:
            fields[key] = float(value)  # Float field
        else:
            try:
                fields[key] = int(value)  # Integer field
            except ValueError:
                fields[key] = value  # Fallback to string if not an int

    # Extract timestamp if present
    if len(parts) > 2:
        time = int(parts[2])
    else:
        time = None

    return {"measurement": measurement, "tags": tags, "fields": fields, "time": time}
