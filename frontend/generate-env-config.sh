#!/bin/sh
set -e

# Path where Nginx serves static files and where env-config.js will be created
NGINX_ROOT_DIR="/usr/share/nginx/html"
OUTPUT_FILE="$NGINX_ROOT_DIR/env-config.js"

# Create the directory if it doesn't exist (it should for Nginx)
mkdir -p "$NGINX_ROOT_DIR"

echo "window.runtimeVariables = {" > "$OUTPUT_FILE"

# Loop through environment variables
# Using `env` and `while read` for robustness
env | while IFS='=' read -r name value; do
    # Check if the variable starts with your chosen prefix (e.g., BK_APP_)
    if echo "$name" | grep -q "^FINANZE_"; then
        # Extract variable name (without the prefix)
        js_name=$(echo "$name" | sed 's/^FINANZE_//')
        # Escape single quotes and backslashes in value for JavaScript string
        escaped_value=$(echo "$value" | sed -e "s/'/\\\'/g" -e 's/\\/\\\\/g')
        echo "  $js_name: '$escaped_value'," >> "$OUTPUT_FILE"
    fi
done

echo "};" >> "$OUTPUT_FILE"

echo "Runtime environment configuration generated at $OUTPUT_FILE:"
cat "$OUTPUT_FILE" # Log the content for debugging
