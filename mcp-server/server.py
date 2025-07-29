import uvicorn
from mcp.server import create_app
from pathlib import Path

# Get the absolute path to the directory containing this script
script_dir = Path(__file__).parent.resolve()

# Construct the absolute path to the config.yaml file
config_path = script_dir / "config.yaml"

# Create the FastAPI application
app = create_app(config_path=str(config_path))

if __name__ == "__main__":
    # Run the server using uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
